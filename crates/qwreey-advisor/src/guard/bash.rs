//! 리뷰어 Bash 명령 검사(python `auditor-readonly-guard.py` 의 `check_bash`).
//!
//! 휴리스틱이다: 리다이렉션 대상, 쓰기 명령의 경로, 상태를 바꾸는 git 하위 명령, 설치와 네트워크 명령을 본다.
//! 순서도 python 과 같다(리다이렉션 먼저, 그다음 명령 조각마다). 처음 걸린 것이 사유다.

use std::sync::LazyLock;

use harness_hook::py::re::{Flags, Regex};
use harness_hook::py::text::{split_whitespace, strip};

use crate::pylib::pathx::basename;
use crate::pylib::repr::repr_str;
use crate::pylib::shlex::{self, Syntax};

use super::scratch::Scratch;
use super::{Cwd, Verdict};

const WRITE_CMDS: &[&str] = &[
    "rm", "rmdir", "mv", "cp", "ln", "chmod", "chown", "chgrp", "touch", "truncate", "dd",
    "install", "mkdir", "tee", "shred", "unlink", "rsync",
];
const DENY_CMDS: &[&str] = &[
    "curl",
    "wget",
    "scp",
    "ssh",
    "sudo",
    "su",
    "setpriv",
    "nc",
    "npm",
    "pnpm",
    "yarn",
    "pip",
    "pip3",
    "cargo",
    "pesde",
    "wally",
    "rokit",
    "aftman",
    "rojo",
    "studio-sync",
];
const MISE_DENY_SUB: &[&str] = &[
    "install",
    "use",
    "trust",
    "upgrade",
    "uninstall",
    "prune",
    "settings",
    "self-update",
    "set",
    "unuse",
];
const GIT_READ_SUB: &[&str] = &[
    "status",
    "diff",
    "log",
    "show",
    "blame",
    "ls-files",
    "ls-tree",
    "rev-parse",
    "rev-list",
    "grep",
    "cat-file",
    "shortlog",
    "describe",
    "merge-base",
    "name-rev",
    "for-each-ref",
    "show-ref",
    "whatchanged",
    "range-diff",
    "annotate",
    "count-objects",
    "check-ignore",
    "version",
];
const GIT_OPTS_WITH_ARG: &[&str] = &["-C", "-c", "--git-dir", "--work-tree", "--namespace"];
const GIT_BRANCH_READ: &[&str] = &["-a", "-r", "-v", "-vv", "--list", "--show-current"];
const GIT_CONFIG_READ: &[&str] = &["--get", "--list", "-l", "--get-all", "--get-regexp"];
const WRAPPERS: &[&str] = &["env", "nice", "nohup", "time", "command", "exec"];
const SAFE_TARGETS: &[&str] = &["/dev/null", "/dev/stderr", "/dev/stdout"];

fn regex(pattern: &str, flags: Flags) -> Regex {
    Regex::with_flags(pattern, flags).expect("built-in pattern")
}

static INPLACE: LazyLock<Regex> =
    LazyLock::new(|| regex(r"(^|\s)-[a-zA-Z]*i(\s|$|[.=])|--in-place", Flags::NONE));
static REDIR: LazyLock<Regex> = LazyLock::new(|| {
    regex(
        r"(?<![0-9&<])(?:[0-9]?)(>>?|&>>?)\s*([^\s;&|<>]+)",
        Flags::NONE,
    )
});
static SEGMENT_SPLIT: LazyLock<Regex> = LazyLock::new(|| regex(r"\|\||&&|[;|\n]", Flags::NONE));
static HEREDOC: LazyLock<Regex> = LazyLock::new(|| {
    let dotall = Flags {
        dotall: true,
        ..Flags::NONE
    };
    regex(
        "<<-?\\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\\1[^\\n]*\\n(.*?)\\n\\s*\\2\\s*(?=\\n|$)",
        dotall,
    )
});
static QUOTED: LazyLock<Regex> =
    LazyLock::new(|| regex("'[^']*'|\"(?:[^\"\\\\]|\\\\.)*\"", Flags::NONE));

// heredoc 을 그 첫 줄(`cat <<EOF` 까지)만 남긴다
fn strip_heredocs(cmd: &str) -> String {
    HEREDOC.replace_all(cmd, |m| {
        let whole = &cmd[m.start()..m.end()];
        whole.split('\n').next().unwrap_or("").to_owned()
    })
}

/// python `strip_bodies`: heredoc 본문과 따옴표 안 글을 지운다(리다이렉션, 명령으로 보지 않게).
fn strip_bodies(cmd: &str) -> String {
    let no_heredoc = strip_heredocs(cmd);
    QUOTED.replace_all(&no_heredoc, |_| "''".to_owned())
}

/// python `check_bash(cmd, cwd)`.
pub fn check(scratch: &Scratch, cmd: &str, cwd: &Cwd) -> Verdict {
    // 1. Redirect targets must stay in scratch
    let stripped = strip_bodies(cmd);
    for m in REDIR.find_iter(&stripped) {
        let target = m.text(&stripped, 2).unwrap_or("");
        if target.starts_with('&') || SAFE_TARGETS.contains(&target) {
            continue;
        }
        match scratch.contains(target, cwd) {
            Ok(true) => {}
            Ok(false) => {
                return Verdict::Deny(format!(
                    "Redirect target {} is outside the scratch folder",
                    repr_str(target)
                ));
            }
            Err(why) => return Verdict::Crash(why),
        }
    }

    // 2. Each command segment (quotes are shlex's job, so only heredocs go)
    let body = strip_heredocs(cmd);
    for seg in SEGMENT_SPLIT.split(&body) {
        if strip(seg).is_empty() {
            continue;
        }
        let argv = shlex::split(seg, Syntax::SPLIT_COMMENTS)
            .unwrap_or_else(|_| split_whitespace(seg).map(str::to_owned).collect());
        let argv = unwrap_wrappers(argv);
        if let Some(verdict) = check_segment(scratch, &argv, cwd) {
            return verdict;
        }
    }
    Verdict::Pass
}

/// `env VAR=x`, `choom ... --`, `prlimit ... --`, `timeout N`, `nice` 같은 래퍼를 벗긴다.
fn unwrap_wrappers(mut argv: Vec<String>) -> Vec<String> {
    while let Some(first) = argv.first() {
        let a0 = basename(first);
        let assignment = first.contains('=') && !first.starts_with('-');
        argv = if assignment || WRAPPERS.contains(&a0) {
            argv.split_off(1)
        } else if a0 == "timeout" {
            // python: [x for x in argv[1:] if not x.startswith("-")][1:]
            argv.into_iter()
                .skip(1)
                .filter(|x| !x.starts_with('-'))
                .skip(1)
                .collect()
        } else if a0 == "choom"
            || a0 == "prlimit"
            || (a0 == "mise" && argv.get(1).map(String::as_str) == Some("exec"))
        {
            after_double_dash(argv)
        } else {
            break;
        };
    }
    argv
}

// python argv[argv.index("--") + 1:] if "--" in argv else []
fn after_double_dash(mut argv: Vec<String>) -> Vec<String> {
    match argv.iter().position(|a| a == "--") {
        Some(i) => argv.split_off(i + 1),
        None => Vec::new(),
    }
}

// 한 명령 조각의 판정. 통과면 None
fn check_segment(scratch: &Scratch, argv: &[String], cwd: &Cwd) -> Option<Verdict> {
    let (first, args) = argv.split_first()?;
    let a0 = basename(first);

    // Network, packages, toolchain
    if DENY_CMDS.contains(&a0) {
        return Some(Verdict::Deny(format!(
            "`{a0}` is not allowed for reviewers"
        )));
    }
    if a0 == "mise"
        && let Some(sub) = args.first()
        && MISE_DENY_SUB.contains(&sub.as_str())
    {
        return Some(Verdict::Deny(format!("`mise {sub}` changes the toolchain")));
    }

    // Write commands: every path (or the target) inside scratch
    if WRITE_CMDS.contains(&a0) {
        let mut paths: Vec<&str> = args
            .iter()
            .map(String::as_str)
            .filter(|x| !x.starts_with('-'))
            .collect();
        if matches!(a0, "cp" | "install" | "rsync" | "ln") && !paths.is_empty() {
            paths = paths.split_off(paths.len() - 1);
        }
        let mut all_inside = !paths.is_empty();
        for path in paths {
            if !all_inside {
                break;
            }
            match scratch.contains(path, cwd) {
                Ok(inside) => all_inside = inside,
                Err(why) => return Some(Verdict::Crash(why)),
            }
        }
        if !all_inside {
            return Some(Verdict::Deny(format!(
                "A path of `{a0}` is outside the scratch folder"
            )));
        }
    }

    // In-place editors
    if matches!(a0, "sed" | "perl" | "ruby") && INPLACE.is_match(&args.join(" ")) {
        return Some(Verdict::Deny(format!("`{a0} -i` edits files in place")));
    }

    // git: only reading subcommands
    if a0 == "git" {
        return check_git(args);
    }
    None
}

fn check_git(args: &[String]) -> Option<Verdict> {
    // Skip global options, some take a value
    let mut i = 0;
    while i < args.len() && args[i].starts_with('-') {
        i += if GIT_OPTS_WITH_ARG.contains(&args[i].as_str()) {
            2
        } else {
            1
        };
    }
    let sub = args.get(i).map_or("", String::as_str);
    let rest: &[String] = args.get(i + 1..).unwrap_or(&[]);
    let first_rest = rest.first().map(String::as_str);

    // Reading forms of otherwise writing subcommands
    let reads = match sub {
        "branch" => rest.iter().all(|r| GIT_BRANCH_READ.contains(&r.as_str())),
        "stash" => matches!(first_rest, Some("list" | "show")),
        "worktree" => first_rest == Some("list"),
        "config" => rest.iter().any(|r| GIT_CONFIG_READ.contains(&r.as_str())),
        _ => false,
    };
    if reads || GIT_READ_SUB.contains(&sub) {
        return None;
    }
    Some(Verdict::Deny(format!(
        "`git {sub}` can change the work tree, index or refs (read HEAD content with `git show HEAD:<path>`)"
    )))
}

#[cfg(test)]
mod tests {
    use super::*;
    use harness_hook::Env;

    fn verdict(cmd: &str) -> Verdict {
        let scratch = Scratch::new(
            "/tmp/claude-audit".to_owned(),
            &Env::from_pairs([("HOME", "/h")]),
        );
        check(&scratch, cmd, &Cwd::Text("/code/x".to_owned()))
    }

    fn denied(cmd: &str) -> bool {
        matches!(verdict(cmd), Verdict::Deny(_))
    }

    /// 모든 내장 정규식이 읽힌다(LazyLock 의 expect 가 입력과 상관없이 늘 통과한다).
    #[test]
    fn built_in_patterns_compile() {
        for re in [&INPLACE, &REDIR, &SEGMENT_SPLIT, &HEREDOC, &QUOTED] {
            LazyLock::force(re);
        }
    }

    /// 읽기 명령과 스크래치 안 쓰기는 통과하고, 밖으로 쓰는 명령은 막는다.
    #[test]
    fn writes_outside_scratch_are_denied() {
        // Reading and writing inside scratch
        assert_eq!(verdict("git diff HEAD~1 -- src"), Verdict::Pass);
        assert_eq!(
            verdict("mkdir -p /tmp/claude-audit/S1 && echo x > /tmp/claude-audit/S1/a"),
            Verdict::Pass
        );
        assert_eq!(
            verdict("cp src/a /tmp/claude-audit/S1/"),
            Verdict::Pass,
            "cp checks only the target"
        );

        // Writes outside
        assert!(denied("rm -rf src"));
        assert!(
            denied("rm -rf /tmp/claude-audit"),
            "the base itself is not a run folder"
        );
        assert!(denied("echo x >> notes.md"));
        assert!(denied("sed -i s/a/b/ f"));
        assert!(denied("git commit -m x"));
        assert!(
            denied("choom -n 1000 -- cargo build"),
            "wrappers are peeled first"
        );
    }

    /// heredoc 본문과 따옴표 안의 `>` 는 리다이렉션이 아니다.
    #[test]
    fn heredoc_and_quoted_text_are_not_redirects() {
        assert_eq!(verdict("luau - <<'EOF'\nprint(a > b)\nEOF"), Verdict::Pass);
        assert_eq!(verdict("echo 'a > b'"), Verdict::Pass);
        assert_eq!(
            verdict("echo x > out.txt"),
            Verdict::Deny("Redirect target 'out.txt' is outside the scratch folder".to_owned())
        );
    }

    /// git 의 읽는 꼴(branch 목록, stash list, config --get)은 통과한다.
    #[test]
    fn git_reading_forms_pass() {
        assert_eq!(verdict("git -C /x branch -a"), Verdict::Pass);
        assert_eq!(verdict("git stash list"), Verdict::Pass);
        assert_eq!(verdict("git config --get user.name"), Verdict::Pass);
        assert!(denied("git branch new"));
        assert!(denied("git stash"));
    }
}
