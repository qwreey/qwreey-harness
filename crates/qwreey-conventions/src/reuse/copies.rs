//! 사본 검사(python reuse-check 의 C1 `check_copies`, `check_regions` 와 C2 `source_copies`, `canon_regions_touched`).
//!
//! C1 은 편집한 파일의 표시가 원본과 같은지 본다(파일은 바이트, 값은 원소 목록, 영역은 정본에서 만든 줄).
//! C2 는 편집한 파일이 원본인 사본 목록을 알린다(묶음은 원소가 바뀐 때만, 정본 영역은 그 안의 줄을 고친 때만).
//! `<저장소>:<경로>` 표시는 현재 저장소 옆의 같은 이름 폴더, 없으면 이 기기에서 일한 저장소에서 찾는다([`Siblings`]).

use std::collections::{BTreeSet, HashMap};
use std::sync::LazyLock;

use harness_hook::known_repos;
use harness_hook::py::fs;
use harness_hook::py::path::{basename, dirname, join, normpath};
use harness_hook::py::re::Regex;
use harness_hook::py::surrogate::unit_of;

use crate::context::Context;
use crate::edit::Added;
use crate::halt::{Halt, Result};
use crate::lex::{Family, family};
use crate::reuse::files::ext_of;
use crate::reuse::index::{Entry, Index};
use crate::reuse::judge::shown;
use crate::reuse::regions::{self, Region, body, expected, is_canon, parse_regions};
use crate::reuse::sets::{Mark, MarkKind, StringSet, extract};

/// 영역 사본이 어긋날 때 덧붙이는 말(python `SYNC_HINT`).
const SYNC_HINT: &str = "Edit the canon region, then sync the copies (python3 -I tools/sync-copies.py --apply where the repo has it).";

static SIBLING_FORM: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"^[\w.-]+:[^/\\]").expect("constant pattern"));

/// C1 결과(그림자 기록의 `status`).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Status {
    Ok,
    Unresolved,
    Differs,
    /// 형제 저장소가 이 기계에 없다(기록만 한다).
    Sibling,
}

impl Status {
    /// 그림자 기록의 글.
    pub fn code(self) -> &'static str {
        match self {
            Status::Ok => "ok",
            Status::Unresolved => "unresolved",
            Status::Differs => "differs",
            Status::Sibling => "sibling",
        }
    }
}

/// 표시 하나의 C1 결과(python `(줄, 알림 또는 None, 결과, 대상, 새로 건드렸나)`).
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct CopyCheck {
    pub line: i64,
    /// 알림 글. 없으면 기록만 한다.
    pub notice: Option<String>,
    pub status: Status,
    pub target: String,
    /// 이번 편집이 이 표시나 그 묶음, 영역을 건드렸나.
    pub touched: bool,
}

impl CopyCheck {
    fn new(
        line: i64,
        notice: Option<String>,
        status: Status,
        target: &str,
        touched: bool,
    ) -> CopyCheck {
        CopyCheck {
            line,
            notice,
            status,
            target: target.to_owned(),
            touched,
        }
    }
}

/// `<저장소>:<경로>` 의 저장소 이름 -> 폴더 후보(python `sibling_repos`, 한 실행 동안 기억한다).
pub struct Siblings<'c> {
    ctx: &'c Context,
    root: String,
    found: HashMap<String, Vec<String>>,
}

/// [`Siblings::resolve`] 의 결과(python `resolve` 의 `(경로, 형제 저장소가 없나, 덧붙일 말)`).
pub struct Resolved {
    pub path: Option<String>,
    pub sibling_missing: bool,
    pub note: String,
}

impl<'c> Siblings<'c> {
    /// 저장소 `root` 에서 보는 형제 저장소 찾기.
    pub fn new(ctx: &'c Context, root: &str) -> Siblings<'c> {
        Siblings {
            ctx,
            root: root.to_owned(),
            found: HashMap::new(),
        }
    }

    /// python `sibling_repos(root, name)`: 옆 폴더 하나, 없으면 이 기기의 같은 이름 저장소 전부(경로순).
    fn repos(&mut self, name: &str) -> &[String] {
        if !self.found.contains_key(name) {
            // A folder beside this repo (the main repo for a worktree) wins
            let main = known_repos::repo_root(&self.root).unwrap_or_else(|| self.root.clone());
            let beside = join(dirname(&normpath(&main)), name);
            let list = if fs::is_dir(&beside) {
                vec![beside]
            } else {
                // 수집 실패는 "못 찾음": 훅은 편집을 막지 않는다
                known_repos::repos(&self.ctx.env, self.ctx.plugin_dir())
                    .unwrap_or_default()
                    .into_iter()
                    .filter(|r| basename(r) == name)
                    .collect()
            };
            self.found.insert(name.to_owned(), list);
        }
        &self.found[name]
    }

    /// python `resolve(root, target)`: 표시 대상의 경로. 같은 이름 저장소가 여럿이면 그 경로가 있는 첫 후보와 견주고 그렇다고 적는다.
    pub fn resolve(&mut self, target: &str) -> Resolved {
        if SIBLING_FORM.match_start(target).is_some()
            && let Some((repo, path)) = target.split_once(':')
            && !repo.contains('/')
        {
            // Candidates by repo name; the first that has the path
            let cands = self.repos(repo).to_vec();
            let Some(first) = cands.first() else {
                return Resolved {
                    path: None,
                    sibling_missing: true,
                    note: String::new(),
                };
            };
            let pick = cands
                .iter()
                .find(|c| fs::exists(&join(c, path)))
                .unwrap_or(first);

            let note = if cands.len() > 1 {
                format!(
                    " ({} repos named {repo} on this machine; compared with {pick}.)",
                    cands.len()
                )
            } else {
                String::new()
            };
            return Resolved {
                path: Some(join(pick, path)),
                sibling_missing: false,
                note,
            };
        }

        // A repo-relative path
        let local = match target.strip_prefix("./") {
            Some(_) => target.trim_start_matches(['.', '/']),
            None => target,
        };
        Resolved {
            path: Some(join(&self.root, local)),
            sibling_missing: false,
            note: String::new(),
        }
    }
}

// python sets_of_file: 색인에 있으면 그 묶음, 아니면 파일을 읽는다(못 읽으면 None)
fn sets_of_file(root: &str, rel_or_abs: &str, index: &Index) -> Option<Vec<StringSet>> {
    if let Some(e) = index.get(rel_or_abs) {
        return Some(e.sets.clone());
    }
    let p = if rel_or_abs.starts_with('/') {
        rel_or_abs.to_owned()
    } else {
        join(root, rel_or_abs)
    };
    let text = fs::read_text(&p).ok()?;
    Some(extract(&text, family(&ext_of(&p)).unwrap_or(Family::C)).0)
}

/// python `check_copies(root, rel, text, own_entry, ents, added_lines)`: `@copy-of` 표시들(영역 사본 빼고).
pub fn check_copies(
    siblings: &mut Siblings<'_>,
    rel: &str,
    text: &str,
    own: &Entry,
    index: &Index,
    added: &Added,
) -> Result<Vec<CopyCheck>> {
    let mut res = Vec::new();
    for m in &own.marks {
        if m.kind == MarkKind::Region || (m.target == rel && m.kind == MarkKind::File) {
            continue;
        }
        let tgt = m.target.as_str();
        let r = siblings.resolve(tgt);
        let Some(path) = r.path.filter(|_| !r.sibling_missing) else {
            res.push(CopyCheck::new(m.line, None, Status::Sibling, tgt, false));
            continue;
        };
        let which = r.note;

        // A file copy is compared byte for byte
        if m.kind == MarkKind::File {
            res.push(check_file(rel, m, &path, text, &which, added)?);
            continue;
        }

        // A value copy is compared by its members
        let name = m.name.as_deref().unwrap_or("");
        let key = format!("{tgt}#{name}");
        let mine = own
            .sets
            .iter()
            .find(|s| s.copy_of.as_deref() == Some(key.as_str()));
        let src_sets = if fs::exists(&path) {
            sets_of_file(
                &siblings.root,
                if index.contains(tgt) { tgt } else { &path },
                index,
            )
        } else {
            None
        };
        let src = src_sets
            .as_ref()
            .and_then(|v| v.iter().find(|s| s.name == name));

        // Missing source, differing members, or the same
        let touched = mine.is_some_and(|s| added.contains(&line_index(s.line)))
            || added.contains(&line_index(m.line));
        res.push(match (src, mine) {
            (None, _) => CopyCheck::new(
                m.line,
                Some(format!("{rel}:{}: @copy-of {key} does not resolve (no such file or name). Fix the copy or the mark.{which}", m.line)),
                Status::Unresolved,
                tgt,
                touched,
            ),
            (Some(src), Some(mine)) if mine.words != src.words => {
                let a: BTreeSet<&str> = src.members().difference(&mine.members()).copied().collect();
                let b: BTreeSet<&str> = mine.members().difference(&src.members()).copied().collect();
                let (a, b): (Vec<&str>, Vec<&str>) = (a.into_iter().collect(), b.into_iter().collect());
                CopyCheck::new(
                    m.line,
                    Some(format!(
                        "{rel}:{}: @copy-of {key} differs: missing {}, extra {}. Fix the copy or the mark.{which}",
                        m.line,
                        none_if_empty(&shown(&a)),
                        none_if_empty(&shown(&b)),
                    )),
                    Status::Differs,
                    tgt,
                    touched,
                )
            }
            _ => CopyCheck::new(m.line, None, Status::Ok, tgt, false),
        });
    }
    Ok(res)
}

// 파일 사본: 원본 바이트와 이 글의 UTF-8 이 같은가
fn check_file(
    rel: &str,
    m: &Mark,
    path: &str,
    text: &str,
    which: &str,
    added: &Added,
) -> Result<CopyCheck> {
    let tgt = m.target.as_str();
    if fs::os_path(path).is_none() {
        return Err(Halt::PyError(
            "open() of a path with NUL or a lone surrogate",
        ));
    }

    // python 은 OSError 만 잡는다
    let Ok(source) = fs::read_bytes(path) else {
        let notice = format!(
            "{rel}:{}: @copy-of {tgt} does not resolve. Fix the copy or the mark.{which}",
            m.line
        );
        return Ok(CopyCheck::new(
            m.line,
            Some(notice),
            Status::Unresolved,
            tgt,
            true,
        ));
    };
    if text.chars().any(|c| unit_of(c).is_some()) {
        return Err(Halt::PyError("text.encode() of a lone surrogate"));
    }
    if source == text.as_bytes() {
        return Ok(CopyCheck::new(m.line, None, Status::Ok, tgt, false));
    }
    let notice = format!(
        "{rel}:{}: @copy-of {tgt} differs from this copy. Edit the source, then copy it over.{which}",
        m.line
    );
    Ok(CopyCheck::new(
        m.line,
        Some(notice),
        Status::Differs,
        tgt,
        !added.is_empty(),
    ))
}

// 1 기반 줄 -> 추가한 줄 집합의 0 기반 번호(음수나 0 줄은 집합에 없다)
fn line_index(line: i64) -> usize {
    usize::try_from(line - 1).unwrap_or(usize::MAX)
}

fn none_if_empty(text: &str) -> &str {
    if text.is_empty() { "none" } else { text }
}

/// python `check_regions(root, rel, path, text, added_lines)`: 영역 사본들. 정본 영역은 건너뛴다.
pub fn check_regions(
    root: &str,
    rel: &str,
    path: &str,
    text: &str,
    added: &Added,
) -> Result<Vec<CopyCheck>> {
    if !text.contains("@start-replace") && !text.contains("@end-replace") {
        return Ok(Vec::new());
    }
    let parsed = parse_regions(text);
    let mut res = Vec::new();
    for e in &parsed.errors {
        let notice = format!(
            "{rel}:{}: copy marker: {}. Fix the marker.",
            e.line,
            e.message()?
        );
        let touched = added.contains(&(e.line - 1));
        res.push(CopyCheck::new(
            e.line as i64,
            Some(notice),
            Status::Unresolved,
            "",
            touched,
        ));
    }

    let lines: Vec<&str> = text.split('\n').collect();
    for r in &parsed.regions {
        if is_canon(r, path, &[root])? {
            continue;
        }
        res.push(check_region(root, rel, path, &lines, r, added)?);
    }
    Ok(res)
}

fn check_region(
    root: &str,
    rel: &str,
    path: &str,
    lines: &[&str],
    r: &Region,
    added: &Added,
) -> Result<CopyCheck> {
    let tgt = format!("{}#{}", r.path, r.name);
    let line = r.line as i64;
    let touched = added.iter().any(|&k| r.start <= k && k <= r.end);

    // 형제 저장소가 이 기계에 없다
    let top: Vec<&str> = r.path.split('/').collect();
    if top[0] == ".." && top.len() > 1 && !fs::is_dir(&join(&join(root, ".."), top[1])) {
        return Ok(CopyCheck::new(line, None, Status::Sibling, &tgt, false));
    }

    let want = match expected(r, path, &[root])? {
        Ok(want) => want,
        Err(regions::MarkError(e)) => {
            let notice = format!(
                "{rel}:{line}: @start-replace {tgt} does not resolve ({e}). Fix the copy or the mark."
            );
            return Ok(CopyCheck::new(
                line,
                Some(notice),
                Status::Unresolved,
                &tgt,
                touched,
            ));
        }
    };
    if want
        .iter()
        .map(String::as_str)
        .eq(body(lines, r).iter().copied())
    {
        return Ok(CopyCheck::new(line, None, Status::Ok, &tgt, false));
    }
    let notice = format!("{rel}:{line}: @start-replace {tgt} differs from its canon. {SYNC_HINT}");
    Ok(CopyCheck::new(
        line,
        Some(notice),
        Status::Differs,
        &tgt,
        touched,
    ))
}

/// python `canon_regions_touched(rel, path, text, added_lines, root)`: 추가한 줄이 든 정본 영역의 이름.
pub fn canon_regions_touched(
    path: &str,
    text: &str,
    added: &Added,
    root: &str,
) -> Result<BTreeSet<String>> {
    let mut out = BTreeSet::new();
    if !text.contains("@start-replace") {
        return Ok(out);
    }
    for r in parse_regions(text).regions {
        if is_canon(&r, path, &[root])? && added.iter().any(|&k| r.start < k && k < r.end) {
            out.insert(r.name);
        }
    }
    Ok(out)
}

/// C2 하나: 원본 이름, 사본 자리(`rel:줄`)들, 알림 줄.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct SourceCopies {
    pub name: String,
    pub copies: Vec<String>,
    pub line: i64,
}

/// python `source_copies(rel, ents, prev, now, touched_file, touched_regions, now_marks)`.
pub fn source_copies(
    rel: &str,
    index: &Index,
    prev: Option<&[StringSet]>,
    own: &Entry,
    touched_file: bool,
    touched_regions: &BTreeSet<String>,
) -> Vec<SourceCopies> {
    // Copies pointing at this file, by name, in index order
    let mut by: Vec<(Option<String>, Vec<String>)> = Vec::new();
    let mut regions: Vec<(String, Vec<String>)> = Vec::new();
    for (orel, e) in index.iter() {
        for m in &e.marks {
            if orel == rel || m.target.trim_start_matches(['.', '/']) != rel {
                continue;
            }
            let at = format!("{orel}:{}", m.line);
            if m.kind == MarkKind::Region {
                push_group(&mut regions, m.name.clone().unwrap_or_default(), at);
            } else {
                let key = if m.kind == MarkKind::Value {
                    m.name.clone()
                } else {
                    None
                };
                push_group(&mut by, key, at);
            }
        }
    }

    // Region copies of touched canon regions
    let mut out = Vec::new();
    for (name, copies) in regions {
        if touched_regions.contains(&name) {
            let line = own
                .marks
                .iter()
                .find(|m| m.kind == MarkKind::Region && m.name.as_deref() == Some(name.as_str()))
                .map_or(1, |m| m.line);
            out.push(SourceCopies { name, copies, line });
        }
    }

    // File copies when lines were added, value copies when members changed
    for (name, copies) in by {
        let Some(name) = name else {
            if touched_file {
                out.push(SourceCopies {
                    name: basename(rel).to_owned(),
                    copies,
                    line: 1,
                });
            }
            continue;
        };
        let cur = own.sets.iter().find(|s| s.name == name);
        let old = prev.and_then(|p| p.iter().find(|s| s.name == name));
        if let Some(cur) = cur
            && old.is_none_or(|o| o.words != cur.words)
        {
            out.push(SourceCopies {
                line: cur.line,
                name,
                copies,
            });
        }
    }
    out
}

// python `d.setdefault(key, []).append(at)`
fn push_group<K: PartialEq>(groups: &mut Vec<(K, Vec<String>)>, key: K, at: String) {
    match groups.iter_mut().find(|(k, _)| *k == key) {
        Some((_, list)) => list.push(at),
        None => groups.push((key, vec![at])),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 사본 목록은 색인 차례로 모으고, 묶음은 원소가 바뀐 때만 알린다.
    #[test]
    fn source_copies_like_python() {
        let set = |words: &[&str]| StringSet {
            line: 2,
            name: "FORMS".into(),
            flags: 1,
            words: words.iter().map(|w| (*w).to_owned()).collect(),
            copy_of: None,
            dup: None,
        };
        let own = Entry {
            mtime_ns: 0,
            size: 0,
            sets: vec![set(&["a", "b", "c"])],
            marks: vec![],
        };
        let copy = Entry {
            mtime_ns: 0,
            size: 0,
            sets: vec![],
            marks: vec![Mark {
                line: 1,
                target: "./a/src.luau".into(),
                name: Some("FORMS".into()),
                kind: MarkKind::Value,
            }],
        };

        // A source file and one value copy pointing at it
        let mut index = Index::default();
        index.insert("a/src.luau", own.clone());
        index.insert("b/copy.luau", copy);

        // A member change lists the copy; the same members do not
        let changed = [set(&["a", "b"])];
        let got = source_copies(
            "a/src.luau",
            &index,
            Some(&changed),
            &own,
            true,
            &BTreeSet::new(),
        );
        assert_eq!(
            got,
            [SourceCopies {
                name: "FORMS".into(),
                copies: vec!["b/copy.luau:1".into()],
                line: 2
            }]
        );
        let same = [set(&["a", "b", "c"])];
        assert!(
            source_copies(
                "a/src.luau",
                &index,
                Some(&same),
                &own,
                true,
                &BTreeSet::new()
            )
            .is_empty()
        );
    }
}
