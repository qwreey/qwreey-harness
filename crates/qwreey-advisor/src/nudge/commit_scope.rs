//! 한 Bash 명령 안의 `git add ...` 와 `git commit ...` 을 읽어 커밋될 변경의 줄 수를 PreToolUse 시점에 잰다
//! (python `hooks/commit_scope.py`).
//!
//! PreToolUse 는 명령이 돌기 전이라 `git add x && git commit` 꼴에서는 index 가 아직 비어 있다. 그래서 같은 명령이 스테이징할
//! 경로를 읽어 `git diff HEAD -- <경로>` 와 그 아래 추적 안 된 파일의 줄 수로 대신 잰다. 읽을 수 없는 명령(따옴표 오류, `$VAR`,
//! 명령 치환이 든 경로, `add -p`, `--pathspec-from-file`)은 `None` 이고 부르는 쪽이 예전처럼 `--cached` 로 잰다.

use std::collections::{BTreeMap, BTreeSet};
use std::io::Read;
use std::sync::LazyLock;

use crate::fixed_re::Fixed;
use harness_hook::Env;
use harness_hook::py::num::parse_decimal;
use harness_hook::py::path::{expanduser, join, normpath};
use harness_hook::py::re::Flags;
use harness_hook::py::text::{splitlines, strip};

use crate::abort::{Abort, Result};
use crate::git::{self, GitError};
use crate::pylib::fs::os_path;
use crate::pylib::pathx::{basename, relpath};
use crate::pylib::repr::is_digit_str;
use crate::pylib::sha1;
use crate::pylib::shlex::{Lexer, Syntax};

use super::settings::git_abort;

const LEX: Syntax = Syntax {
    punctuation: ";&|<>\n",
    whitespace: " \t\r",
    comments: true,
};
const SEPARATORS: &[&str] = &["&&", "||", ";", "|", "&", "\n", ";;", "|&"];
const HEREDOC_STARTS: &[&str] = &["<<", "<<-", "<<<"];
/// 값을 받는 commit 짧은 옵션.
const COMMIT_VALUE_SHORT: &str = "mFCct";
const COMMIT_VALUE_LONG: &[&str] = &[
    "--message",
    "--file",
    "--reuse-message",
    "--reedit-message",
    "--fixup",
    "--squash",
    "--author",
    "--date",
    "--template",
    "--cleanup",
    "--trailer",
];
const ADD_INTERACTIVE: &[&str] = &["-p", "--patch", "-i", "--interactive", "-e", "--edit"];
/// 저장소 전체 pathspec.
const ALL: &str = ":/";
const MAX_FILE_BYTES: u64 = 2 * 1024 * 1024;
const BINARY_SNIFF: usize = 8192;

// python `$` 는 끝 줄바꿈 앞에서도 맞는다(`>\n` 낱말)
static REDIRECT: LazyLock<Fixed> = LazyLock::new(|| {
    Fixed::with_rust(
        r"^[<>&]*[<>][<>&]*$",
        r"^[<>&]*[<>][<>&]*\n?\z",
        Flags::NONE,
    )
});

/// `git commit` 의 읽은 옵션.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct Commit {
    pub all: bool,
    pub include: bool,
    pub dry: bool,
    pub paths: Vec<String>,
}

/// `git add` 의 읽은 옵션(python 판은 `all` 도 읽지만 재는 데 쓰지 않는다).
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct Add {
    pub dry: bool,
    pub update: bool,
    pub paths: Vec<String>,
}

/// 커밋 디렉터리와 같은 명령의 스테이징 범위(python `plan` 의 dict).
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Plan {
    pub dir: String,
    pub commit: Commit,
    /// (그 add 를 돌린 디렉터리, add). dry-run 인 add 는 뺐다.
    pub adds: Vec<(String, Add)>,
    pub stages: bool,
}

/// python `tokens(cmd)`: heredoc 앞까지의 낱말. 따옴표 오류면 `None`.
fn tokens(cmd: &str) -> Option<Vec<String>> {
    let mut lexer = Lexer::new(cmd, LEX);
    let mut out = Vec::new();
    loop {
        match lexer.next_token() {
            Ok(None) => return Some(out),
            Ok(Some(t)) if HEREDOC_STARTS.contains(&t.as_str()) => return Some(out),
            Ok(Some(t)) => out.push(t),
            Err(_) => return None,
        }
    }
}

/// python `segments(toks)`: 구분자로 나누고 리다이렉트와 그 대상(`2>&1` 의 fd 도)을 뺀다.
fn segments(toks: &[String]) -> Vec<Vec<String>> {
    let mut segs = Vec::new();
    let mut cur: Vec<String> = Vec::new();
    let mut i = 0;
    while i < toks.len() {
        let t = &toks[i];
        if SEPARATORS.contains(&t.as_str()) {
            if !cur.is_empty() {
                segs.push(std::mem::take(&mut cur));
            }
        } else if REDIRECT.match_start(t).is_some() {
            if cur.last().is_some_and(|last| is_digit_str(last)) {
                cur.pop();
            }
            i += 1;
        } else {
            cur.push(t.clone());
        }
        i += 1;
    }
    if !cur.is_empty() {
        segs.push(cur);
    }
    segs
}

/// python `git_sub(seg)`: (-C 경로, 하위 명령, 인자). git 명령이 아니면 하위 명령이 빈 글.
fn git_sub(seg: &[String]) -> (Option<String>, &str, &[String]) {
    if seg.first().is_none_or(|first| basename(first) != "git") {
        return (None, "", &[]);
    }
    let mut cdir: Option<String> = None;
    let mut i = 1;
    while i < seg.len() {
        let t = seg[i].as_str();
        if t == "-C" && i + 1 < seg.len() {
            cdir = Some(match cdir {
                None => seg[i + 1].clone(),
                Some(dir) => join(&dir, &seg[i + 1]),
            });
            i += 2;
        } else if t == "-c" && i + 1 < seg.len() {
            i += 2;
        } else if t.starts_with('-') {
            i += 1;
        } else {
            return (cdir, t, &seg[i + 1..]);
        }
    }
    (cdir, "", &[])
}

fn dynamic(t: &str) -> bool {
    t.contains('$') || t.contains('`')
}

/// python `parse_commit(args)`.
fn parse_commit(args: &[String]) -> Option<Commit> {
    let mut flags: BTreeSet<String> = BTreeSet::new();
    let mut paths = Vec::new();
    let mut after_dd = false;
    let mut i = 0;
    while i < args.len() {
        let t = args[i].as_str();
        if after_dd {
            paths.push(t.to_owned());
        } else if t == "--" {
            after_dd = true;
        } else if t.starts_with("--") {
            let name = t.split('=').next().unwrap_or(t);
            flags.insert(name.to_owned());
            if COMMIT_VALUE_LONG.contains(&name) && !t.contains('=') {
                i += 1;
            }
        } else if t.starts_with('-') && t.chars().count() > 1 {
            // Short flags; one that takes a value ends the cluster
            let shorts: Vec<char> = t.chars().skip(1).collect();
            for (j, &ch) in shorts.iter().enumerate() {
                flags.insert(format!("-{ch}"));
                if COMMIT_VALUE_SHORT.contains(ch) {
                    if j == shorts.len() - 1 {
                        i += 1;
                    }
                    break;
                }
            }
        } else {
            paths.push(t.to_owned());
        }
        i += 1;
    }

    if paths.iter().any(|p| dynamic(p)) {
        return None;
    }
    let has = |names: &[&str]| names.iter().any(|n| flags.contains(*n));
    Some(Commit {
        all: has(&["-a", "--all"]),
        include: has(&["-i", "--include"]),
        dry: has(&["--dry-run"]),
        paths,
    })
}

/// python `parse_add(args)`. 대화형, `--pathspec-from-file`, 동적 경로면 `None`.
fn parse_add(args: &[String]) -> Option<Add> {
    let mut flags: BTreeSet<String> = BTreeSet::new();
    let mut paths = Vec::new();
    let mut after_dd = false;
    for t in args {
        if after_dd {
            paths.push(t.clone());
        } else if t == "--" {
            after_dd = true;
        } else if t.starts_with("--") {
            flags.insert(t.split('=').next().unwrap_or(t).to_owned());
        } else if t.starts_with('-') && t.chars().count() > 1 {
            flags.extend(t.chars().skip(1).map(|ch| format!("-{ch}")));
        } else {
            paths.push(t.clone());
        }
    }

    let has = |names: &[&str]| names.iter().any(|n| flags.contains(*n));
    if has(ADD_INTERACTIVE) || has(&["--pathspec-from-file"]) || paths.iter().any(|p| dynamic(p)) {
        return None;
    }
    Some(Add {
        dry: has(&["-n", "--dry-run"]),
        update: has(&["-u", "--update"]),
        paths,
    })
}

/// python `plan(cmd, cwd)`: 커밋 디렉터리와 같은 명령의 스테이징 범위. 읽을 수 없거나 commit 이 없으면 `None`.
pub fn plan(cmd: &str, cwd: &str, env: &Env) -> Option<Plan> {
    let toks = tokens(cmd)?;
    let mut here = cwd.to_owned();
    let mut adds = Vec::new();
    for seg in segments(&toks) {
        // cd and pushd move the directory later git commands run in
        if seg[0] == "cd" || seg[0] == "pushd" {
            if seg.len() > 2 || (seg.len() == 2 && dynamic(&seg[1])) {
                return None;
            }
            let target = if seg.len() == 2 { seg[1].as_str() } else { "~" };
            here = normpath(&join(&here, &expanduser(target, env)));
            continue;
        }

        // git add stages, git commit ends the plan
        let (cdir, sub, args) = git_sub(&seg);
        let gdir = match cdir.filter(|d| !d.is_empty()) {
            Some(dir) => normpath(&join(&here, &dir)),
            None => here.clone(),
        };
        if sub == "add" || sub == "stage" {
            let add = parse_add(args)?;
            if !add.dry {
                adds.push((gdir, add));
            }
        } else if sub == "commit" {
            let commit = parse_commit(args)?;
            let stages = !adds.is_empty() || !commit.paths.is_empty();
            return Some(Plan {
                dir: gdir,
                commit,
                adds,
                stages,
            });
        }
    }
    None
}

// python commit_scope.git: (returncode, stdout), 띄우지 못하면 (1, "")
fn git_rc(cwd: &str, args: &[&str]) -> Result<(i32, String)> {
    match git::run(cwd, args) {
        Ok(out) => Ok((out.code, out.stdout)),
        Err(GitError::Failed) => Ok((1, String::new())),
        Err(other) => Err(git_abort(other)),
    }
}

fn git_out(cwd: &str, args: &[&str]) -> Result<String> {
    git_rc(cwd, args).map(|(_, out)| out)
}

/// python `numstat(out)`: 파일마다 추가+삭제 줄(바이너리 `-` 는 0). 숫자로 읽지 못하는 숫자 글자는 python 의 ValueError.
pub fn numstat(out: &str) -> Result<BTreeMap<String, i128>> {
    let mut files = BTreeMap::new();
    for (path, lines) in numstat_rows(out)? {
        files.insert(path.to_owned(), lines);
    }
    Ok(files)
}

/// numstat 줄마다의 줄 수(같은 경로가 두 번 나와도 둘 다). python `diff_stat` 의 합에 쓴다.
pub fn numstat_lines(out: &str) -> Result<Vec<i128>> {
    Ok(numstat_rows(out)?.into_iter().map(|(_, n)| n).collect())
}

fn numstat_rows(out: &str) -> Result<Vec<(&str, i128)>> {
    let mut rows = Vec::new();
    for line in splitlines(out) {
        let mut fields = line.split('\t');
        let added = fields.next().unwrap_or("");
        let deleted = fields.next().unwrap_or("");
        let path = fields.next().unwrap_or("");
        let lines = count(added)?
            .checked_add(count(deleted)?)
            .ok_or(Abort("line count overflow"))?;
        rows.push((path, lines));
    }
    Ok(rows)
}

/// 줄 수의 합. i128 을 넘으면(python 만 셀 수 있는 수) 오류다.
pub fn sum<'a>(counts: impl IntoIterator<Item = &'a i128>) -> Result<i128> {
    counts
        .into_iter()
        .try_fold(0i128, |acc, n| acc.checked_add(*n))
        .ok_or(Abort("line count overflow"))
}

// python: int(a) if a.isdigit() else 0
fn count(field: &str) -> Result<i128> {
    if !is_digit_str(field) {
        return Ok(0);
    }
    parse_decimal(field)
        .and_then(|n| i128::try_from(n).ok())
        .ok_or(Abort("numstat count is not a decimal integer"))
}

/// python `count_lines(path)`: 앞 2 MiB 의 줄 수. 바이너리(앞 8 KiB 에 NUL)와 읽지 못한 파일은 0.
fn count_lines(path: &str) -> i128 {
    let Some(os) = os_path(path) else {
        return 0;
    };
    let mut data = Vec::new();
    let read = std::fs::File::open(os).and_then(|f| f.take(MAX_FILE_BYTES).read_to_end(&mut data));
    if read.is_err() || data.is_empty() || data[..data.len().min(BINARY_SNIFF)].contains(&0) {
        return 0;
    }
    let newlines = data.iter().filter(|&&b| b == b'\n').count() as i128;
    newlines + i128::from(!data.ends_with(b"\n"))
}

/// python `specs_of(top, base, paths)`: 명령의 경로를 저장소 루트 기준 pathspec 으로. 저장소 밖이면 버린다.
fn specs_of(top: &str, base: &str, paths: &[String], env: &Env) -> Result<Vec<String>> {
    let mut out = Vec::new();
    for p in paths {
        let full = normpath(&join(base, &expanduser(p, env)));
        let rel = relpath(&full, top).ok_or(Abort("cannot read the current directory"))?;
        if rel == "." {
            out.push(ALL.to_owned());
        } else if !rel.starts_with("..") {
            out.push(format!(":/{rel}"));
        }
    }
    Ok(out)
}

/// python `measure(plan)`: 스테이징 범위까지 더한 커밋 크기(추가+삭제 줄, 내용 해시 16자). 저장소를 못 찾으면 `None`.
pub fn measure(plan: &Plan, env: &Env) -> Result<Option<(i128, String)>> {
    let (rc, out) = git_rc(&plan.dir, &["rev-parse", "--show-toplevel"])?;
    let top = strip(&out).to_owned();
    if rc != 0 || top.is_empty() {
        return Ok(None);
    }

    // Pathspecs the same command stages
    let commit = &plan.commit;
    let mut tracked: BTreeSet<String> = BTreeSet::new();
    let mut untracked: BTreeSet<String> = BTreeSet::new();
    for (dir, add) in &plan.adds {
        let specs = if add.paths.is_empty() {
            vec![ALL.to_owned()]
        } else {
            specs_of(&top, dir, &add.paths, env)?
        };
        if !add.update {
            untracked.extend(specs.iter().cloned());
        }
        tracked.extend(specs);
    }

    // Tracked changes the commit takes
    let mut files: BTreeMap<String, i128> = BTreeMap::new();
    if !commit.paths.is_empty() && !commit.include {
        // `git commit <paths>` commits only those paths
        let only = specs_of(&top, &plan.dir, &commit.paths, env)?;
        if only.is_empty() {
            return Ok(None);
        }
        let mut args = vec!["diff", "HEAD", "--numstat", "--"];
        args.extend(only.iter().map(String::as_str));
        files.extend(numstat(&git_out(&top, &args)?)?);
        untracked = if untracked.is_empty() {
            BTreeSet::new()
        } else {
            only.into_iter().collect()
        };
    } else {
        tracked.extend(specs_of(&top, &plan.dir, &commit.paths, env)?);
        if commit.all || tracked.contains(ALL) {
            files.extend(numstat(&git_out(&top, &["diff", "HEAD", "--numstat"])?)?);
        } else {
            files.extend(numstat(&git_out(
                &top,
                &["diff", "--cached", "--numstat"],
            )?)?);
            if !tracked.is_empty() {
                let mut args = vec!["diff", "HEAD", "--numstat", "--"];
                args.extend(tracked.iter().map(String::as_str));
                files.extend(numstat(&git_out(&top, &args)?)?);
            }
        }
    }

    // Untracked files under the staged paths
    if !untracked.is_empty() {
        let mut args = vec!["ls-files", "--others", "--exclude-standard", "-z", "--"];
        args.extend(untracked.iter().map(String::as_str));
        let names = git_out(&top, &args)?;
        for name in names.split('\0').filter(|n| !n.is_empty()) {
            files.insert(format!("?{name}"), count_lines(&join(&top, name)));
        }
    }

    let total = sum(files.values())?;
    let listing: Vec<String> = files.iter().map(|(k, v)| format!("{k}\t{v}")).collect();
    Ok(Some((
        total,
        sha1::hex_prefix(listing.join("\n").as_bytes(), 16),
    )))
}

#[cfg(test)]
mod tests {
    use super::*;

    /// REDIRECT 는 python 판과 같은 낱말을 리다이렉트로 본다(만든 글 3000개).
    #[test]
    fn redirect_agrees_with_python() {
        // Only whether the token matches is used; the regex side's span also covers the final \n
        let py = harness_hook::py::re::Regex::new(r"^[<>&]*[<>][<>&]*$").expect("python pattern");
        for t in crate::fixed_re::corpus(&[">", "<", "&", "\n", "x", "2"], 3000) {
            let want = py.match_start(&t).is_some();
            assert_eq!(REDIRECT.match_start(&t).is_some(), want, "{t:?}");
        }
    }

    fn env() -> Env {
        Env::from_pairs([("HOME", "/h")])
    }

    fn words(cmd: &str) -> Vec<Vec<String>> {
        segments(&tokens(cmd).expect("lexes"))
    }

    /// 조각 나누기: 구분자, 리다이렉트와 그 대상, `2>&1` 의 fd, heredoc 뒤는 버린다.
    #[test]
    fn segments_drop_redirects() {
        assert_eq!(
            words("git add a 2>&1 >/dev/null && git commit -m x"),
            [vec!["git", "add", "a"], vec!["git", "commit", "-m", "x"]]
        );
        assert_eq!(
            words("cat <<EOF\ngit commit\nEOF"),
            [vec!["cat"]],
            "a heredoc ends the reading"
        );
        assert_eq!(
            tokens("git commit -m 'x"),
            None,
            "an open quote cannot be read"
        );
    }

    /// plan: cd 와 -C 를 따라가고, add 경로와 commit 옵션을 읽는다.
    #[test]
    fn plan_follows_directories() {
        // cd, then git -C, then the commit
        let read = plan(
            "cd sub && git -C ../w add -A b && git commit -qm msg",
            "/r",
            &env(),
        )
        .expect("readable command");
        assert_eq!(read.dir, "/r/sub");
        let staged = Add {
            dry: false,
            update: false,
            paths: vec!["b".to_owned()],
        };
        assert_eq!(read.adds, [("/r/w".to_owned(), staged)]);
        assert!(read.stages);
        assert!(!read.commit.all, "-q and -m are flags, msg is -m's value");

        // Unreadable forms
        assert_eq!(plan("git add -p && git commit", "/r", &env()), None);
        assert_eq!(plan("git add $X && git commit", "/r", &env()), None);
        assert_eq!(plan("cd $D && git commit", "/r", &env()), None);
        assert_eq!(plan("git status", "/r", &env()), None, "no commit, no plan");
    }

    /// commit 짧은 옵션 묶음: 값 옵션이 끝이면 다음 낱말이 값, 가운데면 나머지가 값.
    #[test]
    fn commit_short_value_flags() {
        let args = |s: &str| s.split(' ').map(str::to_owned).collect::<Vec<_>>();
        let c = parse_commit(&args("-am msg path")).expect("plain");
        assert!(c.all);
        assert_eq!(c.paths, ["path"], "msg is the value of -m");
        let c = parse_commit(&args("-mmsg path")).expect("plain");
        assert_eq!(c.paths, ["path"], "the value is glued to -m");
        let c = parse_commit(&args("--dry-run --message=x -- -a")).expect("plain");
        assert!(c.dry && !c.all, "after -- everything is a path");
    }

    /// numstat: 바이너리 `-` 는 0, 같은 경로는 뒤가 이긴다.
    #[test]
    fn numstat_counts() {
        let files = numstat("3\t1\ta.txt\n-\t-\tbin.png\n").expect("ascii digits");
        assert_eq!(files.get("a.txt"), Some(&4));
        assert_eq!(files.get("bin.png"), Some(&0));
        assert!(
            numstat("\u{b2}\t0\tx").is_err(),
            "python isdigit() is true but int() raises"
        );
    }
}
