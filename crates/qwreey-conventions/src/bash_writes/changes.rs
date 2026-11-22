//! 명령이 바꾼 파일과 그 전 글(python `bash_writes.changes`).
//!
//! - 글을 적어 둔 파일: 지금 글과 다르면 바뀜, 전 글은 적어 둔 것.
//! - 명령 전에 깨끗했는데 지금 porcelain 에 나온 파일: 전 글은 명령 전 HEAD 의 blob.
//! - 명령이 커밋까지 했으면(HEAD 가 바뀜) 두 HEAD 사이에 바뀐 파일도 같은 식.
//! - porcelain 이 한도를 넘었으면(overflow) 명령 전 상태를 모르는 항목은 바뀐 것으로 보지 않는다.
//! - 명령 전에 없던 파일의 전 글은 명령이 이름을 댄 파일의 글과 HEAD blob 을 합친 것이다(mv, cp 로 옮긴 줄을 새 줄로 세지 않게).
//! - worktree 를 다시 쓰는 git 하위 명령이 있으면 이름을 댄 파일만 본다. 그중 지금 글이 이미 git 객체로 있는 파일은 건너뛰고,
//!   나머지는 전 HEAD 와 지금 HEAD 의 blob 도 전 글로 친다.
//! - 같은 세션의 다른 Bash 가 도는 중이면 이름을 댄 파일만 본다.

use std::collections::{BTreeMap, HashSet};
use std::time::Instant;

use harness_hook::py::path::{join, relpath};

use super::files::{self, Reader, Recorded};
use super::repo;
use super::snap::{Snapshot, lookup};
use super::{checked_ext, inside};
use crate::halt::{Halt, Result};
use crate::pyops::str_order;

/// rule 맞춤에 넘기는 바뀐 경로 수(python `TOUCHED_MAX`).
const TOUCHED_MAX: usize = 500;

/// 검사할 파일 하나: 경로, 전 글, 지금 글.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Changed {
    pub path: String,
    pub before: String,
    pub now: String,
}

/// 명령이 바꾼 것(python `changes` 의 세 값).
#[derive(Debug, Default)]
pub struct Changes {
    /// 전 글을 아는 바뀐 파일, 경로순.
    pub items: Vec<Changed>,
    /// 바뀐 모든 경로(rule 맞춤용, 처음 나온 순서, 한도까지).
    pub touched: Vec<String>,
    /// 바뀌었지만 시간이나 글자 한도로 읽지 못한 검사 대상 파일.
    pub unread: Vec<String>,
}

// 지금까지 모은 것: 경로 -> (전 글, 지금 글), 바뀐 경로, 명령 전에 없던 파일
struct Found {
    out: BTreeMap<String, (String, String)>,
    touched: Vec<String>,
    new: HashSet<String>,
}

/// python `changes(snap, deadline, restrict)`. `restrict` 가 참이면(다른 Bash 가 도는 중) 이름을 댄 경로만 본다.
pub fn changes(snap: &Snapshot, deadline: Option<Instant>, restrict: bool) -> Result<Changes> {
    let named: HashSet<&str> = snap.named.iter().map(String::as_str).collect();
    let restrict = restrict || snap.concurrent;
    let texts: Vec<&(String, Recorded)> = snap
        .texts
        .iter()
        .filter(|(p, _)| !restrict || named.contains(p.as_str()))
        .collect();
    let mut read = Reader::new(deadline);
    let mut found = Found {
        out: BTreeMap::new(),
        touched: Vec::new(),
        new: HashSet::new(),
    };

    recorded(snap, &texts, &mut read, &mut found)?;
    if snap.wide && !restrict {
        from_git(snap, &texts, &mut read, &mut found)?;
    }
    if (!found.new.is_empty() || snap.rewrite) && !found.out.is_empty() {
        moved_lines(snap, &texts, &named, &mut found)?;
    }

    // Sorted items, unique touched paths, unread checked files
    let mut items: Vec<Changed> = found
        .out
        .into_iter()
        .map(|(path, (before, now))| Changed { path, before, now })
        .collect();
    items.sort_by(|a, b| str_order(&a.path, &b.path));
    let seen: HashSet<&str> = found.touched.iter().map(String::as_str).collect();
    let unread = read
        .skipped
        .iter()
        .filter(|p| seen.contains(p.as_str()) && checked_ext(p))
        .cloned()
        .collect();
    let mut touched = Vec::new();
    let mut once = HashSet::new();
    for p in &found.touched {
        if once.insert(p.as_str()) {
            touched.push(p.clone());
        }
    }
    touched.truncate(TOUCHED_MAX);
    Ok(Changes {
        items,
        touched,
        unread,
    })
}

// 글을 적어 둔 파일: 지금 글과 견준다. 한도로 못 읽은 파일은 (mtime, 크기)가 바뀌었으면 rule 만 넣는다
fn recorded(
    snap: &Snapshot,
    texts: &[&(String, Recorded)],
    read: &mut Reader,
    found: &mut Found,
) -> Result<()> {
    for (ap, before) in texts {
        if *before == Recorded::Unread {
            if let Some(was) = lookup(&snap.stats, ap)
                && *was != files::stat(ap)?
            {
                found.touched.push(ap.clone());
            }
            continue;
        }

        // Unread now: rules only if it changed on disk
        let now = match read.read(ap)? {
            Recorded::Unread => {
                if let Some(was) = stat_before(snap, ap)?
                    && Some(was) != files::stat(ap)?
                {
                    found.touched.push(ap.clone());
                }
                continue;
            }
            Recorded::Missing => continue,
            Recorded::Text(now) => now,
        };
        if Some(now.as_str()) == before.text() {
            continue;
        }
        found.touched.push(ap.clone());
        found
            .out
            .insert(ap.clone(), (before.text().unwrap_or("").to_owned(), now));
        if *before == Recorded::Missing {
            found.new.insert(ap.clone());
        }
    }
    Ok(())
}

// python `stats.get(ap) or dirty.get(os.path.relpath(ap, root))`: 명령 전의 (mtime, 크기)
fn stat_before(snap: &Snapshot, ap: &str) -> Result<Option<files::FileStat>> {
    if let Some(Some(st)) = lookup(&snap.stats, ap) {
        return Ok(Some(*st));
    }
    let rel = relpath(ap, &snap.root).ok_or(Halt::PyError("os.path.relpath failed"))?;
    Ok(lookup(&snap.dirty, &rel).copied().flatten())
}

// 명령 전에 깨끗했는데 지금 porcelain 에 나온 파일과, 명령이 한 커밋이 바꾼 파일
fn from_git(
    snap: &Snapshot,
    texts: &[&(String, Recorded)],
    read: &mut Reader,
    found: &mut Found,
) -> Result<()> {
    let root = &snap.root;
    let in_texts: HashSet<&str> = texts.iter().map(|(p, _)| p.as_str()).collect();
    let (mut need, mut fresh) = (Vec::new(), Vec::new());
    let mut need_set: HashSet<String> = HashSet::new();

    // Porcelain entries now
    for (rel, xy) in repo::porcelain(root)?.unwrap_or_default() {
        let ap = join(root, &rel);
        if in_texts.contains(ap.as_str()) {
            continue;
        }
        if let Some(was) = lookup(&snap.dirty, &rel) {
            if *was != files::stat(&ap)? {
                found.touched.push(ap);
            }
            continue;
        }
        if snap.overflow || xy.contains('D') {
            continue;
        }
        found.touched.push(ap);
        if checked_ext(&rel) && xy == "??" {
            fresh.push(rel);
        } else if checked_ext(&rel) {
            need_set.insert(rel.clone());
            need.push(rel);
        }
    }

    // The command committed: files between the two HEADs
    let now_head = repo::head(root)?;
    if let (Some(head), Some(now_head)) = (snap.head.as_deref(), now_head.as_deref())
        && !head.is_empty()
        && !now_head.is_empty()
        && now_head != head
        && !snap.overflow
    {
        for rel in repo::diff_names(root, head, now_head)? {
            let ap = join(root, &rel);
            let known = in_texts.contains(ap.as_str())
                || lookup(&snap.dirty, &rel).is_some()
                || need_set.contains(&rel);
            if !rel.is_empty() && !rel.contains('\n') && !known && harness_hook::py::fs::exists(&ap)
            {
                found.touched.push(ap);
                if checked_ext(&rel) {
                    need_set.insert(rel.clone());
                    need.push(rel);
                }
            }
        }
    }

    // Read them; the text before is the old HEAD blob
    let old = if need.is_empty() {
        Some(BTreeMap::new())
    } else {
        repo::blobs(root, snap.head.as_deref(), &need)?
    };
    for rel in need.iter().chain(&fresh) {
        let before = old.as_ref().and_then(|o| o.get(rel));
        if need_set.contains(rel) && before.is_none() {
            continue;
        }
        let ap = join(root, rel);
        if let Recorded::Text(now) = read.read(&ap)? {
            let before = before.cloned().flatten();
            if before.is_none() {
                found.new.insert(ap.clone());
            }
            found.out.insert(ap, (before.unwrap_or_default(), now));
        }
    }
    Ok(())
}

// 옮기거나 베끼거나 되돌린 파일에서 온 줄을 새 줄로 세지 않게 전 글을 넓힌다
fn moved_lines(
    snap: &Snapshot,
    texts: &[&(String, Recorded)],
    named: &HashSet<&str>,
    found: &mut Found,
) -> Result<()> {
    let root = &snap.root;
    let mut rels: Vec<String> = Vec::new();
    for p in &snap.named {
        if inside(p, root) {
            rels.push(relpath(p, root).ok_or(Halt::PyError("os.path.relpath failed"))?);
        }
    }
    rels.sort_by(|a, b| str_order(a, b));
    let head_texts = match snap.head {
        Some(_) => repo::blobs(root, snap.head.as_deref(), &rels)?.unwrap_or_default(),
        None => BTreeMap::new(),
    };
    let in_order = |m: &BTreeMap<String, Option<String>>| -> Vec<String> {
        rels.iter()
            .filter_map(|r| m.get(r).cloned().flatten())
            .collect()
    };

    // New files: everything the command named, now and in HEAD
    if !found.new.is_empty() {
        let mut parts: Vec<String> = texts
            .iter()
            .filter(|(p, _)| named.contains(p.as_str()))
            .filter_map(|(_, t)| t.text().map(str::to_owned))
            .collect();
        parts.extend(in_order(&head_texts));
        let pool = parts.join("\n");
        for ap in &found.new {
            if let Some(slot) = found.out.get_mut(ap) {
                slot.0 = pool.clone();
            }
        }
    }

    // Rewrites: skip files git restored, widen the rest with both HEADs
    if snap.rewrite {
        let mine: Vec<String> = found
            .out
            .keys()
            .filter(|p| named.contains(p.as_str()))
            .cloned()
            .collect();
        for p in repo::in_git(root, &mine)? {
            found.out.remove(&p);
        }
        let now_head = repo::head(root)?;
        let after = match now_head.as_deref() {
            Some(h) if !h.is_empty() && Some(h) != snap.head.as_deref() => {
                repo::blobs(root, Some(h), &rels)?.unwrap_or_default()
            }
            _ => BTreeMap::new(),
        };
        for p in mine {
            let Some(slot) = found.out.get_mut(&p) else {
                continue;
            };
            let rel = relpath(&p, root).ok_or(Halt::PyError("os.path.relpath failed"))?;
            let mut joined = vec![slot.0.clone()];
            joined.extend(
                [head_texts.get(&rel), after.get(&rel)]
                    .into_iter()
                    .filter_map(|t| t.cloned().flatten()),
            );
            slot.0 = joined.join("\n");
        }
    }
    Ok(())
}
