//! Bash 명령 분류(python `wslib.classify_bash`): 어떤 다른 저장소를 쓰는가, 읽는가.
//!
//! 하네스의 bash-bypass-reminder 분류기는 경로를 보지 않고 코드 확장자 리다이렉트와 `sed -i` 만 쓰기로 보므로
//! 경로를 보는 분류기를 따로 둔다. 조각(`&&`, `;`, `|` 등)마다 실제 명령, `cd` 로 바뀐 폴더, 리다이렉트 대상,
//! 낱말 속 경로를 보고, 건드린 다른 저장소마다 읽기 또는 쓰기를 적는다. 쓰기가 하나라도 있으면 처음 쓴 저장소다.

mod redirect;
mod words;

use harness_hook::py::ospath::{basename, isabs};

use crate::context::Context;
use crate::paths::{Base, expand, norm};
use crate::scope::Scope;
use crate::stop::{Result, Stop};
use words::{ABS, INPLACE, INTERP, SCRIPT_WRITE, WRITE_ALL, WRITE_LAST};

/// 다른 저장소를 어떻게 건드리는가.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Kind {
    Read,
    Write,
}

/// 건드린 저장소와 갈래, 처음 나온 순서로(python 의 dict). 쓰기로 적힌 저장소는 읽기로 내리지 않는다.
#[derive(Default)]
struct Found(Vec<(String, Kind)>);

impl Found {
    fn hit(&mut self, repo: Option<String>, kind: Kind) {
        let Some(repo) = repo else { return };
        match self.0.iter_mut().find(|(r, _)| *r == repo) {
            Some((_, Kind::Write)) => {}
            Some((_, slot)) => *slot = kind,
            None => self.0.push((repo, kind)),
        }
    }

    // 처음 쓴 저장소, 없으면 처음 읽은 저장소
    fn verdict(self) -> Option<(Kind, String)> {
        let first_write = self.0.iter().position(|(_, k)| *k == Kind::Write);
        let (repo, kind) = self.0.into_iter().nth(first_write.unwrap_or(0))?;
        Some((kind, repo))
    }
}

/// python `classify_bash(cmd, cwd, scope)`: (갈래, 다른 저장소 루트). 다른 저장소를 건드리지 않으면 `None`.
pub fn classify(
    ctx: &Context,
    cmd: &str,
    cwd: Base,
    scope: &Scope,
) -> Result<Option<(Kind, String)>> {
    let mut found = Found::default();
    let mut cur: Option<String> = match cwd {
        Some("") if scope.project.is_empty() => Some("/".to_owned()),
        Some("") => Some(scope.project.clone()),
        other => other.map(str::to_owned),
    };

    for seg in words::segments(cmd) {
        let words = words::words(seg);
        let head_at = words::head_index(&words);
        if head_at >= words.len() {
            continue;
        }
        let head = basename(&words[head_at]);
        let args = &words[head_at + 1..];

        // `cd` moves the folder later segments run in
        if head == "cd" || head == "pushd" {
            let target = args
                .iter()
                .find(|a| !a.starts_with('-'))
                .map_or("~", String::as_str);
            let moved = norm(ctx, target, cur.as_deref())?;
            found.hit(scope.sibling(&moved)?, Kind::Read);
            cur = Some(moved);
            continue;
        }

        classify_segment(ctx, seg, head, args, cur.as_deref(), scope, &mut found)?;
    }
    Ok(found.verdict())
}

// `cd` 가 아닌 조각 하나: 그 조각이 도는 폴더와 만지는 경로마다 읽기 또는 쓰기
fn classify_segment(
    ctx: &Context,
    seg: &str,
    head: &str,
    args: &[String],
    cur: Base,
    scope: &Scope,
    found: &mut Found,
) -> Result<()> {
    let seg_cwd = segment_cwd(ctx, head, args, cur)?;
    let redirs = redirect::targets(seg);
    let (whole, write_tokens) = writes(seg, head, args, &redirs);

    // Paths the segment touches, first seen first
    let mut touched: Vec<String> = Vec::new();
    for w in touched_words(args, &redirs) {
        if w.contains('/')
            || w.starts_with(['~', '.'])
            || w.starts_with("$HOME")
            || w.starts_with("${HOME}")
            || redirs.contains(&w)
        {
            push_new(&mut touched, norm(ctx, &w, seg_cwd.as_deref())?);
        }
    }
    for m in ABS.find_iter(seg) {
        let text = m.text(seg, 0).unwrap_or("");
        push_new(&mut touched, norm(ctx, text, seg_cwd.as_deref())?);
    }
    let mut written = Vec::new();
    for w in write_tokens.iter().filter(|w| !w.is_empty()) {
        written.push(norm(ctx, w, seg_cwd.as_deref())?);
    }

    // The folder it runs in
    // 명령 전체가 쓰기여도 상대 인자가 있을 때만 그 폴더의 저장소를 쓴다(`cd 형제 && rm /이 저장소/x`)
    let Some(seg_cwd) = seg_cwd else {
        return Err(Stop::Raises("os.path.normcase on a cwd that is not a str"));
    };
    let cwd_repo = scope.sibling(&seg_cwd)?;
    if cwd_repo.is_some() && (!args.is_empty() || !redirs.is_empty()) {
        let relative = |w: &String| !isabs(&expand(ctx, w)) && !w.starts_with('~');
        let rel_args = args.iter().any(|a| !a.starts_with('-') && relative(a));
        let relative_write = write_tokens.iter().any(relative) || (whole && rel_args);
        found.hit(
            cwd_repo,
            if relative_write {
                Kind::Write
            } else {
                Kind::Read
            },
        );
    }

    // Each touched path
    for p in &touched {
        if let Some(repo) = scope.sibling(p)? {
            let write = whole || written.contains(p);
            found.hit(Some(repo), if write { Kind::Write } else { Kind::Read });
        }
    }
    Ok(())
}

// 조각이 도는 폴더: 지금 폴더, git 이면 마지막 `-C <폴더>`(python 은 지금 폴더에서 따로따로 푼다)
fn segment_cwd(ctx: &Context, head: &str, args: &[String], cur: Base) -> Result<Option<String>> {
    let mut seg_cwd = cur.map(str::to_owned);
    if head == "git" && args.len() > 1 {
        for (i, a) in args[..args.len() - 1].iter().enumerate() {
            if a == "-C" {
                seg_cwd = Some(norm(ctx, &args[i + 1], cur)?);
            }
        }
    }
    Ok(seg_cwd)
}

// (명령 전체가 쓰기인가, 쓰는 낱말들): 리다이렉트 대상, 그리고 cp 같은 명령의 마지막 위치 인자
fn writes(seg: &str, head: &str, args: &[String], redirs: &[String]) -> (bool, Vec<String>) {
    let mut tokens = redirs.to_vec();
    let whole = if WRITE_ALL.contains(&head) || INPLACE.is_match(seg) {
        true
    } else if WRITE_LAST.contains(&head) {
        tokens.extend(args.iter().rfind(|a| !a.starts_with('-')).cloned());
        false
    } else if head == "git" {
        words::git_writes(args)
    } else {
        INTERP.contains(&head) && SCRIPT_WRITE.is_match(seg)
    };
    (whole, tokens)
}

// 경로 후보: 인자와 리다이렉트 대상, 그리고 그 낱말 속 절대 경로 꼴
fn touched_words(args: &[String], redirs: &[String]) -> Vec<String> {
    let mut out = Vec::new();
    for w in args.iter().chain(redirs) {
        out.push(w.clone());
        out.extend(
            ABS.find_iter(w)
                .iter()
                .map(|m| m.text(w, 0).unwrap_or("").to_owned()),
        );
    }
    out
}

fn push_new(list: &mut Vec<String>, item: String) {
    if !list.contains(&item) {
        list.push(item);
    }
}
