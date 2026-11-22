//! Bash 명령을 조각과 낱말로(python `wslib._segments`, `_head`, `_git_writes`)와 분류기가 보는 고정 패턴.

use std::sync::LazyLock;

use harness_hook::py::shlex;
use harness_hook::py::text::{split_whitespace, strip};
use harness_hook::rx::Regex;

/// 명령 앞에 붙어 실제 명령을 뒤로 미는 낱말(python `PREFIX`).
const PREFIX: &[&str] = &[
    "(", "{", "time", "nice", "env", "command", "exec", "nohup", "sudo", "choom", "prlimit",
    "timeout", "--", "builtin",
];
/// 스크립트를 받는 인터프리터(python `INTERP`). 명령 글에 쓰기 낱말이 있으면 쓰기다.
pub const INTERP: &[&str] = &[
    "python", "python3", "node", "deno", "bun", "perl", "ruby", "lua", "luau", "lune", "lute",
];
/// 인자 모두를 쓰는 명령(python `WRITE_ALL`).
pub const WRITE_ALL: &[&str] = &[
    "rm", "rmdir", "mv", "touch", "mkdir", "truncate", "chmod", "chown", "shred", "unlink", "tee",
    "patch", "mkfifo",
];
/// 마지막 위치 인자만 쓰는 명령(python `WRITE_LAST`).
pub const WRITE_LAST: &[&str] = &["cp", "install", "ln", "rsync", "scp"];
/// 저장소를 바꾸는 git 하위 명령(python `GIT_WRITE`).
const GIT_WRITE: &[&str] = &[
    "commit",
    "add",
    "rm",
    "mv",
    "checkout",
    "switch",
    "reset",
    "restore",
    "push",
    "merge",
    "rebase",
    "cherry-pick",
    "clean",
    "apply",
    "am",
    "pull",
    "revert",
    "init",
    "clone",
];

static SEGMENT: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"&&|\|\||[;|\n]"));
static ASSIGNMENT: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"[A-Za-z_]\w*=\S*"));
static DURATION: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"[\d.]+[smhd]?"));

/// 제자리 고치기(python `INPLACE`): `sed -i`, `perl -i`, `awk -i inplace`, `git apply`, `dd of=`.
pub static INPLACE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(
        r"\bsed\s+(-\S*\s+)*-\S*i|\bperl\s+(-\S*\s+)*-\S*i|\bawk\s+-i\s+inplace|\bgit\s+apply\b|\bdd\b.*\bof=",
    )
});
/// 스크립트 글의 쓰기 낱말(python `SCRIPT_WRITE`).
pub static SCRIPT_WRITE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(
        r#"['"][wa]\+?b?['"]|write|unlink|rmtree|rename|\.replace\(|copyfile|appendFile|\bmkdir"#,
    )
});
/// 낱말 속의 절대 경로 꼴(python `ABS`): `~`, `$HOME`, `${HOME}`, `/` 로 시작한다.
pub static ABS: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r#"(?:~|\$\{?HOME\}?|/)[^\s'";|&<>()=]*"#));

/// python `_segments(cmd)`: `&&`, `||`, `;`, `|`, 줄바꿈으로 나눈 조각 가운데 공백만이 아닌 것.
pub fn segments(cmd: &str) -> Vec<&str> {
    SEGMENT
        .split(cmd)
        .into_iter()
        .filter(|s| !strip(s).is_empty())
        .collect()
}

/// 조각의 낱말: python `shlex.split`, 따옴표가 닫히지 않으면 `str.split()`. 빈 낱말은 뺀다.
pub fn words(seg: &str) -> Vec<String> {
    let words = match shlex::split(seg) {
        Ok(words) => words,
        Err(_) => split_whitespace(seg).map(str::to_owned).collect(),
    };
    words.into_iter().filter(|w| !w.is_empty()).collect()
}

/// python `_head(words)`: 앞붙이(`sudo`, `VAR=x`, `-n`, `5s`)를 지난 실제 명령의 자리.
pub fn head_index(words: &[String]) -> usize {
    words
        .iter()
        .position(|w| {
            let prefix = PREFIX.contains(&w.as_str())
                || ASSIGNMENT.fullmatch(w).is_some()
                || w.starts_with('-')
                || DURATION.fullmatch(w).is_some();
            !prefix
        })
        .unwrap_or(words.len())
}

/// python `_git_writes(args)`: git 하위 명령이 저장소를 바꾸는가.
pub fn git_writes(args: &[String]) -> bool {
    let Some((sub, rest)) = git_subcommand(args) else {
        return false;
    };
    let first = rest.first().map(String::as_str);
    match sub {
        // Always a write
        _ if GIT_WRITE.contains(&sub) => true,

        // A write only with some arguments
        "stash" => first.is_none_or(|r| {
            matches!(
                r,
                "push" | "pop" | "apply" | "drop" | "save" | "clear" | "branch"
            )
        }),
        "worktree" => first
            .is_some_and(|r| matches!(r, "add" | "remove" | "prune" | "move" | "lock" | "unlock")),
        "branch" | "tag" => rest
            .iter()
            .any(|r| matches!(r.as_str(), "-d" | "-D" | "-m" | "-M" | "-f" | "--delete")),

        // Reads
        _ => false,
    }
}

// 전역 선택지(`-C 폴더`, `-c 키=값` 등)를 지난 첫 낱말과 그 뒤 인자들
fn git_subcommand(args: &[String]) -> Option<(&str, &[String])> {
    let mut i = 0;
    while i < args.len() {
        let a = args[i].as_str();
        if matches!(a, "-C" | "-c" | "--git-dir" | "--work-tree") {
            i += 2;
        } else if a.starts_with('-') {
            i += 1;
        } else {
            return Some((a, &args[i + 1..]));
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 고정 패턴은 python re 와 같은 일치를 낸다.
    #[test]
    fn patterns_agree_with_python() {
        // Pieces near each pattern, and characters where the engines differ
        let pieces = [
            "sed",
            " -i",
            " -n ",
            "perl",
            "awk -i inplace",
            "git apply",
            "dd ",
            "of=",
            "x",
            "'w'",
            "\"ab\"",
            "write",
            ".replace(",
            "mkdir",
            "~",
            "$HOME",
            "${HOME}",
            "/a/b",
            "=",
            ";",
            "|",
            "&&",
            "\n",
            "A_1=",
            "5s",
            "1.5",
            "\u{663}",
            "\u{e9}",
            "\u{a0}",
            "\u{1c}",
            "_x",
        ];

        harness_hook::testkit::assert_agree(
            &[
                ("SEGMENT", &SEGMENT),
                ("ASSIGNMENT", &ASSIGNMENT),
                ("DURATION", &DURATION),
                ("INPLACE", &INPLACE),
                ("SCRIPT_WRITE", &SCRIPT_WRITE),
                ("ABS", &ABS),
            ],
            &pieces,
        );
    }

    /// 앞붙이를 건너뛰고, git 하위 명령의 쓰기를 가른다.
    #[test]
    fn head_and_git() {
        let w = |s: &str| words(s);
        assert_eq!(head_index(&w("sudo FOO=1 nice -n 5 rm x")), 5);
        assert_eq!(head_index(&w("time 2.5s")), 2);
        assert!(git_writes(&w("-C /x commit -m y")));
        assert!(git_writes(&w("stash")));
        assert!(!git_writes(&w("stash list")));
        assert!(git_writes(&w("branch -D x")));
        assert!(!git_writes(&w("log")));
        assert_eq!(
            segments("a && b || c; d | e\n \n"),
            vec!["a ", " b ", " c", " d ", " e"]
        );
    }
}
