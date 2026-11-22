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

use harness_hook::py::fs;
use harness_hook::py::path::{join, relpath};

use super::files::{self, FileStat, Reader, Recorded};
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

/// 한 번 훑는 동안의 재료와 모은 것.
struct Scan<'s> {
    snap: &'s Snapshot,
    /// 이번에 견줄 적어 둔 글(다른 Bash 가 돌면 이름을 댄 것만).
    texts: Vec<&'s (String, Recorded)>,
    named: HashSet<&'s str>,
    read: Reader,
    /// 경로 -> (전 글, 지금 글).
    out: BTreeMap<String, (String, String)>,
    touched: Vec<String>,
    /// 명령 전에 없던 파일.
    new: HashSet<String>,
}

/// python `changes(snap, deadline, restrict)`. `restrict` 가 참이면(다른 Bash 가 도는 중) 이름을 댄 경로만 본다.
pub fn changes(snap: &Snapshot, deadline: Option<Instant>, restrict: bool) -> Result<Changes> {
    let named: HashSet<&str> = snap.named.iter().map(String::as_str).collect();
    let restrict = restrict || snap.concurrent;
    let texts = snap
        .texts
        .iter()
        .filter(|(p, _)| !restrict || named.contains(p.as_str()))
        .collect();
    let mut scan = Scan {
        snap,
        texts,
        named,
        read: Reader::new(deadline),
        out: BTreeMap::new(),
        touched: Vec::new(),
        new: HashSet::new(),
    };

    scan.recorded()?;
    if snap.wide && !restrict {
        let mut todo = scan.porcelain_now()?;
        scan.committed(&mut todo)?;
        scan.read_new_and_dirty(&todo)?;
    }
    if (!scan.new.is_empty() || snap.rewrite) && !scan.out.is_empty() {
        scan.widen_moved()?;
    }
    Ok(scan.finish())
}

/// git 에서 찾은, 전 글을 HEAD blob 에서 읽을 파일(`need`)과 추적 안 하던 새 파일(`fresh`).
#[derive(Default)]
struct FromGit {
    need: Vec<String>,
    need_set: HashSet<String>,
    fresh: Vec<String>,
}

impl FromGit {
    fn need(&mut self, rel: String) {
        self.need_set.insert(rel.clone());
        self.need.push(rel);
    }
}

impl Scan<'_> {
    fn change(&mut self, ap: String, before: Option<&str>, now: String) {
        if before.is_none() {
            self.new.insert(ap.clone());
        }
        self.out.insert(ap, (before.unwrap_or("").to_owned(), now));
    }

    // python `stats.get(ap) or dirty.get(os.path.relpath(ap, root))`: 명령 전의 (mtime, 크기)
    fn stat_before(&self, ap: &str) -> Result<Option<FileStat>> {
        if let Some(Some(st)) = lookup(&self.snap.stats, ap) {
            return Ok(Some(*st));
        }
        let rel = relpath(ap, &self.snap.root).ok_or(Halt::PyError("os.path.relpath failed"))?;
        Ok(lookup(&self.snap.dirty, &rel).copied().flatten())
    }

    // 글을 적어 둔 파일: 지금 글과 견준다. 한도로 못 읽은 파일은 (mtime, 크기)가 바뀌었으면 rule 만 넣는다
    fn recorded(&mut self) -> Result<()> {
        let texts = self.texts.clone();
        for (ap, before) in texts {
            if *before == Recorded::Unread {
                if let Some(was) = lookup(&self.snap.stats, ap)
                    && *was != files::stat(ap)?
                {
                    self.touched.push(ap.clone());
                }
                continue;
            }

            // Unread now: rules only if it changed on disk
            let now = match self.read.read(ap)? {
                Recorded::Text(now) => now,
                Recorded::Missing => continue,
                Recorded::Unread => {
                    if let Some(was) = self.stat_before(ap)?
                        && Some(was) != files::stat(ap)?
                    {
                        self.touched.push(ap.clone());
                    }
                    continue;
                }
            };
            if Some(now.as_str()) == before.text() {
                continue;
            }
            self.touched.push(ap.clone());
            let before = match before {
                Recorded::Missing => None,
                other => Some(other.text().unwrap_or("")),
            };
            self.change(ap.clone(), before, now);
        }
        Ok(())
    }

    // 명령 전에 깨끗했는데 지금 porcelain 에 나온 파일. 명령 전 상태를 아는 dirty 파일은 (mtime, 크기)만 견준다
    fn porcelain_now(&mut self) -> Result<FromGit> {
        let snap = self.snap;
        let in_texts: HashSet<&str> = self.texts.iter().map(|(p, _)| p.as_str()).collect();
        let mut todo = FromGit::default();
        for (rel, xy) in repo::porcelain(&snap.root)?.unwrap_or_default() {
            let ap = join(&snap.root, &rel);
            if in_texts.contains(ap.as_str()) {
                continue;
            }
            if let Some(was) = lookup(&snap.dirty, &rel) {
                if *was != files::stat(&ap)? {
                    self.touched.push(ap);
                }
                continue;
            }
            if snap.overflow || xy.contains('D') {
                continue;
            }

            // Clean before the command, changed now
            self.touched.push(ap);
            match (checked_ext(&rel), xy == "??") {
                (true, true) => todo.fresh.push(rel),
                (true, false) => todo.need(rel),
                _ => {}
            }
        }
        Ok(todo)
    }

    // 명령이 커밋까지 했으면 두 HEAD 사이에 바뀐 파일도 HEAD blob 에서 전 글을 읽는다
    fn committed(&mut self, todo: &mut FromGit) -> Result<()> {
        let snap = self.snap;
        let now_head = repo::head(&snap.root)?;
        let (Some(head), Some(now_head)) = (snap.head.as_deref(), now_head.as_deref()) else {
            return Ok(());
        };
        if head.is_empty() || now_head.is_empty() || now_head == head || snap.overflow {
            return Ok(());
        }

        let in_texts: HashSet<&str> = self.texts.iter().map(|(p, _)| p.as_str()).collect();
        for rel in repo::diff_names(&snap.root, head, now_head)? {
            let ap = join(&snap.root, &rel);
            let known = in_texts.contains(ap.as_str())
                || lookup(&snap.dirty, &rel).is_some()
                || todo.need_set.contains(&rel);
            if rel.is_empty() || rel.contains('\n') || known || !fs::exists(&ap) {
                continue;
            }
            self.touched.push(ap);
            if checked_ext(&rel) {
                todo.need(rel);
            }
        }
        Ok(())
    }

    // git 에서 찾은 파일을 읽는다. 전 글은 명령 전 HEAD 의 blob(git 이 실패하면 그 파일들은 건너뛴다)
    fn read_new_and_dirty(&mut self, todo: &FromGit) -> Result<()> {
        let snap = self.snap;
        let old = if todo.need.is_empty() {
            Some(BTreeMap::new())
        } else {
            repo::blobs(&snap.root, snap.head.as_deref(), &todo.need)?
        };
        for rel in todo.need.iter().chain(&todo.fresh) {
            let before = old.as_ref().and_then(|o| o.get(rel));
            if todo.need_set.contains(rel) && before.is_none() {
                continue;
            }
            let ap = join(&snap.root, rel);
            if let Recorded::Text(now) = self.read.read(&ap)? {
                let before = before.cloned().flatten();
                self.change(ap, before.as_deref(), now);
            }
        }
        Ok(())
    }

    // 옮기거나 베끼거나 되돌린 파일에서 온 줄을 새 줄로 세지 않게 전 글을 넓힌다
    fn widen_moved(&mut self) -> Result<()> {
        let snap = self.snap;
        let mut rels: Vec<String> = Vec::new();
        for p in &snap.named {
            if inside(p, &snap.root) {
                rels.push(relpath(p, &snap.root).ok_or(Halt::PyError("os.path.relpath failed"))?);
            }
        }
        rels.sort_by(|a, b| str_order(a, b));
        let head_texts = match snap.head {
            Some(_) => repo::blobs(&snap.root, snap.head.as_deref(), &rels)?.unwrap_or_default(),
            None => BTreeMap::new(),
        };

        if !self.new.is_empty() {
            self.pool_new_files(&rels, &head_texts);
        }
        if snap.rewrite {
            self.widen_rewrites(&rels, &head_texts)?;
        }
        Ok(())
    }

    // 새 파일의 전 글: 명령이 이름을 댄 파일의 글 모두와 그 HEAD blob
    fn pool_new_files(&mut self, rels: &[String], head_texts: &BTreeMap<String, Option<String>>) {
        let mut parts: Vec<&str> = self
            .texts
            .iter()
            .filter(|(p, _)| self.named.contains(p.as_str()))
            .filter_map(|(_, t)| t.text())
            .collect();
        parts.extend(rels.iter().filter_map(|r| head_texts.get(r)?.as_deref()));
        let pool = parts.join("\n");
        for ap in &self.new {
            if let Some(slot) = self.out.get_mut(ap) {
                slot.0 = pool.clone();
            }
        }
    }

    // worktree 를 다시 쓴 명령: git 이 되돌린 파일은 빼고, 나머지는 전 HEAD 와 지금 HEAD 의 blob 도 전 글로 친다
    fn widen_rewrites(
        &mut self,
        rels: &[String],
        head_texts: &BTreeMap<String, Option<String>>,
    ) -> Result<()> {
        let snap = self.snap;
        let mine: Vec<String> = self
            .out
            .keys()
            .filter(|p| self.named.contains(p.as_str()))
            .cloned()
            .collect();
        for p in repo::in_git(&snap.root, &mine)? {
            self.out.remove(&p);
        }

        // The other HEAD, if the command moved it
        let now_head = repo::head(&snap.root)?;
        let after = match now_head.as_deref() {
            Some(h) if !h.is_empty() && Some(h) != snap.head.as_deref() => {
                repo::blobs(&snap.root, Some(h), rels)?.unwrap_or_default()
            }
            _ => BTreeMap::new(),
        };
        for p in mine {
            let Some(slot) = self.out.get_mut(&p) else {
                continue;
            };
            let rel = relpath(&p, &snap.root).ok_or(Halt::PyError("os.path.relpath failed"))?;
            let extra = [head_texts.get(&rel), after.get(&rel)]
                .into_iter()
                .filter_map(|t| t?.as_deref());
            slot.0 = std::iter::once(slot.0.as_str())
                .chain(extra)
                .collect::<Vec<_>>()
                .join("\n");
        }
        Ok(())
    }

    // 경로순 항목, 처음 나온 순서의 바뀐 경로(한도까지), 한도로 못 읽은 검사 대상 파일
    fn finish(self) -> Changes {
        let mut items: Vec<Changed> = self
            .out
            .into_iter()
            .map(|(path, (before, now))| Changed { path, before, now })
            .collect();
        items.sort_by(|a, b| str_order(&a.path, &b.path));

        let seen: HashSet<&str> = self.touched.iter().map(String::as_str).collect();
        let unread = self
            .read
            .skipped
            .iter()
            .filter(|p| seen.contains(p.as_str()) && checked_ext(p))
            .cloned()
            .collect();
        let mut once = HashSet::new();
        let mut touched: Vec<String> = self
            .touched
            .iter()
            .filter(|p| once.insert(p.as_str()))
            .cloned()
            .collect();
        touched.truncate(TOUCHED_MAX);
        Changes {
            items,
            touched,
            unread,
        }
    }
}
