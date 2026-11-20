//! Bash 명령이 바꿨을 법한 소스 경로(python `bash_paths`).
//!
//! sed -i, perl -pi, patch, 인터프리터 명령이면 명령에 든 소스 경로 전부, 아니면 리다이렉트와 tee 의 대상만 본다.
//! 프로젝트 밖(스크래치 /tmp 등)은 뺀다. 확장자는 기본 툴킷 표의 것만 안다.

use std::sync::LazyLock;

use harness_hook::Env;
use harness_hook::py::path::{basename, join, normpath};
use harness_hook::py::text::split_whitespace;
use harness_hook::rx::Regex;

use super::toolkit::BASH_EXTS;
use crate::halt::Result;
use crate::pat::{Look, Pat, before};

/// 한 번에 보는 경로 수의 한도.
const MAX_PATHS: usize = 8;

/// 명령 첫 세 낱말의 이름이 이것이면 경로를 다루는 명령으로 본다(python `INTERP`).
const INTERP: &[&str] = &[
    "python", "python3", "node", "deno", "bun", "perl", "ruby", "lua", "luau", "lune", "lute",
];

fn code() -> String {
    format!(r"[\w./@-]+\.(?:{})\b", BASH_EXTS.join("|"))
}

static SEGMENT: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"&&|\|\||[;|\n]"));
static INPLACE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"\bsed\s+(-\S*\s+)*-i|\bperl\s+(-\S*\s+)*-\S*p\S*i|\bawk\s+-i\s+inplace|\bpatch\b")
});
// python `(?<![0-9&])>>?...|\btee...`: 뒤보기는 앞 글자 검사로. 두 갈래는 `>` 와 `t` 로 시작해 한 자리에서 겹치지 않는다
static REDIRECT: LazyLock<Look> = LazyLock::new(|| {
    let code = code();
    Look::new(
        &format!(r#">>?\s*['\"]?({code})|\btee\s+(?:-a\s+)?['\"]?({code})"#),
        |t, m| {
            m.group(1).is_none()
                || before(t, m.start()).is_none_or(|c| !c.is_ascii_digit() && c != '&')
        },
        None,
    )
});
// python 은 낱말 머리에서만 시작하게 `(?<![\w./@-])` 를 둔다(긴 낱말에서 되짚지 않으려고). 맞는 곳은 그것 없이도 같다:
// 낱말 안에서 맞는 일치가 있으면 낱말 머리부터도 맞고, 가장 왼쪽이 이긴다. regex crate 는 되짚지 않아 뒤보기가 필요 없다
static BASH_PATH: LazyLock<Regex> = LazyLock::new(|| Regex::new(&code()));

/// python `bash_paths(cmd, cwd)`: 바꿨을 법한 소스 경로(정규화한 절대 경로, 겹치지 않게, 앞의 8개).
///
/// `cwd` 는 입력의 cwd 나 현재 디렉터리다. 글이 아닌 cwd 는 python 이 쓰는 자리(`rstrip`, `join`)에서 그 예외로 끝난다.
pub fn bash_paths(cmd: &str, cwd: &Result<String>, env: &Env) -> Result<Vec<String>> {
    // Paths the command names
    let found: Vec<&str> = if rewrites(cmd) {
        BASH_PATH
            .find_iter(cmd)
            .iter()
            .map(|m| &cmd[m.start()..m.end()])
            .collect()
    } else {
        REDIRECT
            .find_iter(cmd)
            .iter()
            .filter_map(|m| {
                m.text(cmd, 1)
                    .filter(|s| !s.is_empty())
                    .or_else(|| m.text(cmd, 2))
            })
            .collect()
    };

    // The project prefix
    let proj = match env.get_nonempty("CLAUDE_PROJECT_DIR") {
        Some(dir) => dir.to_owned(),
        None => cwd.clone()?,
    };
    let proj = format!("{}/", proj.trim_end_matches('/'));

    // Absolute, inside the project, once each
    let mut out: Vec<String> = Vec::new();
    for p in found {
        let p = if p.starts_with('/') {
            normpath(p)
        } else {
            normpath(&join(&cwd.clone()?, p))
        };
        if !out.contains(&p) && p.starts_with(&proj) {
            out.push(p);
        }
    }
    out.truncate(MAX_PATHS);
    Ok(out)
}

// 파일을 제자리에서 고치는 명령이나 인터프리터가 있는가
fn rewrites(cmd: &str) -> bool {
    if INPLACE.is_match(cmd) {
        return true;
    }
    SEGMENT
        .split(cmd)
        .iter()
        .flat_map(|seg| split_whitespace(seg).take(3))
        .any(|w| INTERP.contains(&basename(w)))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn paths(cmd: &str) -> Vec<String> {
        let env = Env::from_pairs([("CLAUDE_PROJECT_DIR", "/r")]);
        bash_paths(cmd, &Ok("/r".to_owned()), &env).unwrap()
    }

    /// 고치는 명령은 든 경로 전부, 아니면 리다이렉트 대상만 본다.
    #[test]
    fn picks_written_paths() {
        // sed -i names every path; reading commands name none
        assert_eq!(
            paths("sed -i 's/a/b/' src/A.luau x/B.ts"),
            vec!["/r/src/A.luau", "/r/x/B.ts"]
        );
        assert!(paths("grep -n foo src/A.luau | head").is_empty());

        // A redirect target and tee, but not 2> or a path outside the project
        assert_eq!(paths("cat p >> src/A.luau"), vec!["/r/src/A.luau"]);
        assert_eq!(paths("echo x | tee -a 'b/C.py'"), vec!["/r/b/C.py"]);
        assert!(
            paths("cmd 2>err.py").is_empty(),
            "a digit before > is a fd redirect"
        );
        assert!(paths("sed -i s/a/b/ /tmp/A.luau").is_empty());

        // An interpreter word anywhere in the first three words of a segment
        assert_eq!(
            paths("cd x && /usr/bin/python3 - y/A.rs <<'EOF'"),
            vec!["/r/y/A.rs"]
        );
    }

    /// 글이 아닌 cwd 는 쓰는 자리에서만 python 의 예외가 된다.
    #[test]
    fn deferred_cwd_error() {
        // The project dir covers the prefix, an absolute path needs no cwd
        let env = Env::from_pairs([("CLAUDE_PROJECT_DIR", "/r")]);
        let bad = Err(crate::halt::Halt::PyError("cwd is not a string"));
        assert_eq!(
            bash_paths("sed -i x /r/A.lua", &bad, &env).unwrap(),
            vec!["/r/A.lua"]
        );

        // A relative path joins the cwd and raises
        assert!(bash_paths("sed -i x A.lua", &bad, &env).is_err());
    }

    /// 이 모듈의 고정 패턴이 모두 regex crate 로 옮겨지고 엔진이 만들어진다.
    #[test]
    fn fixed_patterns_build() {
        SEGMENT.check();
        INPLACE.check();
        REDIRECT.check();
        BASH_PATH.check();
    }

    /// 뒤보기를 앞 글자 검사로 옮긴 리다이렉트, 뒤보기를 뺀 경로 패턴은 python 패턴과 같은 일치를 낸다.
    #[test]
    fn redirect_and_paths_like_python() {
        // Redirects, tee and in-place paths with the characters around them
        let code = code();
        let texts = [
            "echo x > src/a.py",
            "echo x>>src/a.py",
            "echo x 2>src/a.py",
            "echo x &>src/a.py",
            "a>b.py>c.py",
            "cat x | tee -a 'src/b.ts'",
            "x=1>>>a.luau",
            "sed -i s src/a.py src//b.ts ./c.luau",
            "a.pyx.py b.py@c.ts",
            "x.py-y.ts",
            "@scope/pkg.ts",
            "aaaa.pyx",
            "é.py ²a.py",
            "a\u{301}.py",
        ];
        crate::pat::assert_same(
            &format!(r#"(?<![0-9&])>>?\s*['\"]?({code})|\btee\s+(?:-a\s+)?['\"]?({code})"#),
            harness_hook::py::re::Flags::NONE,
            &*REDIRECT,
            &[(1, 1), (2, 2)],
            &texts,
        );

        // The path pattern without python's lookbehind
        crate::pat::assert_same(
            &format!(r"(?<![\w./@-]){code}"),
            harness_hook::py::re::Flags::NONE,
            &*BASH_PATH,
            &[],
            &texts,
        );
    }
}
