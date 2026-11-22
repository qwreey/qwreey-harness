//! Bash 명령 글 읽기(python `bash-bypass-reminder.py` 의 패턴, `heads`, `redirect_targets`, `cmd_paths`).
//!
//! 명령 글은 셸로 풀지 않고 정규식으로 본다. 잘못 짚어도 알림이 한 번 더 나거나 빠질 뿐이다(막지 않는다).

use std::sync::LazyLock;

use harness_hook::py::path::{basename, join, normpath};
use harness_hook::py::re::{Flags, Match};
use harness_hook::py::text::split_whitespace;
use harness_hook::rx::Regex;

use crate::pat::{Look, Pat, before};
use crate::pyops::str_order;

/// 스크립트를 도는 인터프리터(python `INTERP`).
pub const INTERP: &[&str] = &[
    "python", "python3", "node", "deno", "bun", "perl", "ruby", "lua", "luau", "lune", "lute",
];
/// 명령 이름 앞에 오는 낱말(python `PREFIX`).
const PREFIX: &[&str] = &[
    "(", "{", "time", "nice", "env", "command", "exec", "nohup", "sudo", "choom", "prlimit",
    "timeout", "--",
];

/// 제자리 편집(python `INPLACE`).
pub static INPLACE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(
        r"\bsed\s+(-\S*\s+)*-i|\bperl\s+(-\S*\s+)*-\S*p\S*i|\bawk\s+-i\s+inplace|\bpatch\b|\bgit\s+apply\b",
    )
});
/// 인터프리터 스크립트가 쓰기를 한다는 신호(python `SCRIPT_WRITE`, qwreey-workspace 의 같은 이름 패턴과 같다).
pub static SCRIPT_WRITE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(
        r#"['"][wa]\+?b?['"]|write|unlink|rmtree|rename|\.replace\(|copyfile|appendFile|\bmkdir"#,
    )
});

const CODE_EXT: &str =
    r"\.(luau|lua|py|ts|tsx|js|jsx|mjs|cjs|astro|vue|svelte|css|rs|go|json|toml|md|mdx|ya?ml|sh)";
/// 셸 낱말 하나: 따옴표로 묶은 것(공백 포함)이나 공백, 따옴표, 연산자가 없는 덩어리.
const WORD: &str = r#"'[^'\n]*'|"[^"\n]*"|[^\s;|&'"<>()]+"#;

/// `>`, `>>`, `tee` 가 쓰는 곳(python `REDIRECT`). `2>`, `&>`, `=>`, `->` 의 `>` 는 리다이렉트가 아니다.
///
/// python 의 뒤보기 `(?<![0-9&=-])` 는 첫 갈래(`>` 로 시작)에만 붙어 있고 둘째 갈래는 `t` 로 시작하므로, 거른 자리에서 다른 갈래가
/// 맞는 일은 없다([`Look`] 의 조건).
static REDIRECT: LazyLock<Look> = LazyLock::new(|| {
    Look::new(
        &format!(r"(>>?\s*({WORD}))|\btee\s+(?:-a\s+)?({WORD})"),
        |text, m| {
            m.group(1).is_none()
                || before(text, m.start()).is_none_or(|c| !matches!(c, '0'..='9' | '&' | '=' | '-'))
        },
        None,
    )
});
static PATHLIKE: LazyLock<Regex> = LazyLock::new(|| Regex::new(&format!(r"[\w./@-]+{CODE_EXT}\b")));
static CODE_FILE: LazyLock<Regex> =
    LazyLock::new(|| Regex::with_flags(&format!("{CODE_EXT}$"), Flags::IGNORECASE));
static QUOTED: LazyLock<Regex> = LazyLock::new(|| Regex::new(r#"'([^'\n]*)'|"([^"\n]*)""#));
static SEGMENT: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"&&|\|\||[;|\n]"));
static ASSIGN: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"[A-Za-z_]\w*=\S*"));
static DURATION: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"[\d.]+[smhd]?"));

/// python `_unquote(word)`: 같은 따옴표로 앞뒤를 묶은 낱말이면 그 안.
pub fn unquote(word: &str) -> &str {
    let quoted = word.len() >= 2
        && (word.starts_with('\'') && word.ends_with('\'')
            || word.starts_with('"') && word.ends_with('"'));
    if quoted {
        &word[1..word.len() - 1]
    } else {
        word
    }
}

/// python `_abs(path, cwd)`: cwd 기준 절대 경로를 정리한 것.
pub fn absolute(path: &str, cwd: &str) -> String {
    normpath(&if path.starts_with('/') {
        path.to_owned()
    } else {
        join(cwd, path)
    })
}

// REDIRECT 일치의 대상 낱말(python `m.group(1) or m.group(2) or ""`)
fn target_of<'t>(cmd: &'t str, m: &Match) -> &'t str {
    m.text(cmd, 2).or_else(|| m.text(cmd, 3)).unwrap_or("")
}

/// 리다이렉트와 tee 의 대상들(따옴표를 벗긴 것), 코드 파일이 아닌 것도.
pub fn redirected(cmd: &str) -> Vec<String> {
    REDIRECT
        .find_iter(cmd)
        .iter()
        .map(|m| unquote(target_of(cmd, m)).to_owned())
        .collect()
}

/// python `redirect_targets(cmd)`: `>`, `>>`, `tee` 가 쓰는 코드 파일 경로.
pub fn redirect_targets(cmd: &str) -> Vec<String> {
    redirected(cmd)
        .into_iter()
        .filter(|t| CODE_FILE.is_match(t))
        .collect()
}

/// python `cmd_paths(cmd)`: 명령에 든 코드 파일 경로, 글 순서로 정렬한 것. 따옴표로 묶은 것은 공백이 있어도 통째로 하나다.
pub fn cmd_paths(cmd: &str) -> Vec<String> {
    let mut paths: Vec<String> = Vec::new();
    for m in QUOTED.find_iter(cmd) {
        let inner = m.text(cmd, 1).or_else(|| m.text(cmd, 2)).unwrap_or("");
        if CODE_FILE.is_match(inner) && harness_hook::py::text::strip(inner).contains(' ') {
            paths.push(inner.to_owned());
        }
    }

    // Quoted words without a space stay; the rest blank out
    let bare = QUOTED.replace_all(cmd, |m| {
        let whole = m.text(cmd, 0).unwrap_or("");
        if harness_hook::py::text::strip(whole.trim_matches(['\'', '"'])).contains(' ') {
            " ".to_owned()
        } else {
            whole.to_owned()
        }
    });
    paths.extend(
        PATHLIKE
            .find_iter(&bare)
            .iter()
            .filter_map(|m| m.text(&bare, 0).map(str::to_owned)),
    );
    paths.sort_by(|a, b| str_order(a, b));
    paths.dedup();
    paths
}

/// python `heads(cmd)`: 명령 조각마다 실행하는 프로그램 이름(앞의 `env`, `nice`, 변수 대입, 옵션을 건너뛰고, `mise exec` 는 그 뒤).
pub fn heads(cmd: &str) -> Vec<String> {
    let mut out = Vec::new();
    for seg in SEGMENT.split(cmd) {
        let spaced = seg.replace('(', " ( ");
        let words: Vec<&str> = split_whitespace(&spaced).collect();
        let skip = |w: &&str| {
            PREFIX.contains(w)
                || ASSIGN.fullmatch(w).is_some()
                || w.starts_with('-')
                || DURATION.fullmatch(w).is_some()
        };
        let Some(i) = words.iter().position(|w| !skip(w)) else {
            continue;
        };

        // `mise exec [--] <tool>` runs the tool
        let mut head = words[i];
        if head == "mise" && words.get(i + 1) == Some(&"exec") {
            let rest = &words[i + 2..];
            let rest = match rest.iter().position(|w| *w == "--") {
                Some(k) => &rest[k + 1..],
                None => rest,
            };
            head = rest.first().copied().unwrap_or(head);
        }
        out.push(basename(head).to_owned());
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 리다이렉트 대상: `2>`, `=>` 의 `>` 는 빼고, `>>` 와 tee 는 넣는다(python 원래 패턴과 같은 일치).
    #[test]
    fn redirect_like_python() {
        let original = format!(r"(?<![0-9&=-])>>?\s*({WORD})|\btee\s+(?:-a\s+)?({WORD})");
        crate::pat::assert_same(
            &original,
            Flags::NONE,
            &*REDIRECT,
            &[(1, 2), (2, 3)],
            &[
                "echo x > a.py",
                "2>/dev/null >> 'b c.ts'",
                "a=>b",
                "x->y",
                "cat 2>>e.md",
                "tee -a f.sh",
                "1>a 2>b >c",
                "&>x",
            ],
        );
        assert_eq!(
            redirect_targets("echo x > a.py 2> e.log | tee 'q r.ts'"),
            vec!["a.py", "q r.ts"]
        );
    }

    /// 경로는 따옴표 안 공백 경로와 맨 경로를 모아 정렬한다.
    #[test]
    fn command_paths_and_heads() {
        assert_eq!(
            cmd_paths("sed -i x \"src/my file.luau\" b.py a.py 'c.ts'"),
            vec!["a.py", "b.py", "c.ts", "src/my file.luau"]
        );
        assert_eq!(
            heads("FOO=1 nice -n 10 python3 x.py && mise exec -- node y.js | (cd a; git status)"),
            vec!["python3", "node", "cd", "git"]
        );
    }

    /// 고정 패턴이 regex crate 와 py::re 에서 같게 맞는다.
    #[test]
    fn fixed_patterns_agree_with_python() {
        let pieces = [
            "sed",
            " -i",
            " -n",
            "perl",
            " -pi",
            "awk -i inplace",
            "patch",
            "git apply",
            "'w'",
            "\"ab\"",
            "write",
            "a.py",
            "src/",
            ".TS",
            "\n",
            "'",
            "\"",
            "x=1",
            "3.5s",
            "&&",
            "|",
            ";",
            "\u{1c}",
            "한",
        ];
        harness_hook::testkit::assert_agree(
            &[
                ("INPLACE", &*INPLACE),
                ("SCRIPT_WRITE", &*SCRIPT_WRITE),
                ("PATHLIKE", &*PATHLIKE),
                ("CODE_FILE", &*CODE_FILE),
                ("QUOTED", &*QUOTED),
                ("SEGMENT", &*SEGMENT),
                ("ASSIGN", &*ASSIGN),
                ("DURATION", &*DURATION),
            ],
            &pieces,
        );
    }
}
