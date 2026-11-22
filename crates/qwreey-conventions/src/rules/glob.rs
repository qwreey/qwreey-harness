//! rule 의 `paths` 글롭(python `rules_inject.glob_to_regex`, `rule_matches`): 공식 paths 와 같은 `**`, `*`, `?`, `{a,b}`, `[..]`.
//!
//! 글롭은 rule 을 쓴 사람의 글이라 py::re 로 돈다(`[..]` 안의 글을 그대로 정규식에 넣는다).

use harness_hook::py::path::{normpath, relpath};
use harness_hook::py::re::{Regex, escape};

use crate::halt::{Halt, Result};
use crate::pyops::re_halt;

/// python `glob_to_regex(glob)` 의 패턴 글(끝에 `\Z`). `**/` 는 0개 이상의 폴더, `{a,b}` 는 겹칠 수 있는 선택이다.
pub fn to_pattern(glob: &str) -> String {
    let chars: Vec<char> = glob.chars().collect();
    let mut out = String::new();
    let mut depth = 0usize;
    let mut i = 0;
    while i < chars.len() {
        i = match chars[i] {
            '*' => star(&chars, i, &mut out),
            '[' => bracket(&chars, i, &mut out),
            c => {
                plain(c, &mut depth, &mut out);
                i + 1
            }
        };
    }

    // Braces left open close at the end
    out.push_str(&")".repeat(depth));
    out.push_str(r"\Z");
    out
}

// `**/`, `**`, `*` 가운데 맞는 것. 다음 자리를 돌려준다
fn star(chars: &[char], i: usize, out: &mut String) -> usize {
    let next = |k: usize| chars.get(i + k).copied();
    match (next(1), next(2)) {
        (Some('*'), Some('/')) => {
            out.push_str("(?:.*/)?");
            i + 3
        }
        (Some('*'), _) => {
            out.push_str(".*");
            i + 2
        }
        _ => {
            out.push_str("[^/]*");
            i + 1
        }
    }
}

// `?`, 중괄호 선택의 `{` `,` `}`(열린 것이 있을 때만), 그 밖의 글자는 escape
fn plain(c: char, depth: &mut usize, out: &mut String) {
    match c {
        '?' => out.push_str("[^/]"),
        '{' => {
            *depth += 1;
            out.push_str("(?:");
        }
        '}' if *depth > 0 => {
            *depth -= 1;
            out.push(')');
        }
        ',' if *depth > 0 => out.push('|'),
        _ => out.push_str(&escape(&c.to_string())),
    }
}

// `[..]` 하나: 닫는 `]` 가 (여는 것 바로 뒤를 빼고) 있으면 문자 집합, 없으면 글자 `[`. 다음 자리를 돌려준다
fn bracket(chars: &[char], i: usize, out: &mut String) -> usize {
    let close = (i + 2..chars.len()).find(|&j| chars[j] == ']');
    let Some(j) = close else {
        out.push_str("\\[");
        return i + 1;
    };
    let body: String = chars[i + 1..j].iter().collect();
    let body = match body.strip_prefix('!') {
        Some(rest) => format!("^{rest}"),
        None => body,
    };
    out.push('[');
    out.push_str(&body.replace('\\', "\\\\"));
    out.push(']');
    j + 1
}

/// python `glob_to_regex(glob)`. python 이 re.error 를 내는 글롭은 오류다.
pub fn compile(glob: &str) -> Result<Regex> {
    Regex::new(&to_pattern(glob)).map_err(|e| re_halt(&e))
}

/// python `rule_matches(regexes, abs_path, root)`: 절대 경로, 앞 `/` 를 뗀 경로, 프로젝트 기준 상대 경로 가운데 하나가 맞는가.
///
/// 프로젝트 밖 파일의 상대 경로는 앞 `/` 를 뗀 절대 경로다.
pub fn rule_matches(regexes: &[Regex], abs_path: &str, root: &str) -> Result<bool> {
    let p = normpath(abs_path);
    let rel = if p.starts_with(&format!("{}/", root.trim_end_matches('/'))) {
        relpath(&p, root).ok_or(Halt::PyError("os.path.relpath failed"))?
    } else {
        p.trim_start_matches('/').to_owned()
    };
    let bare = p.trim_start_matches('/');
    Ok(regexes.iter().any(|rx| {
        rx.match_start(bare).is_some()
            || rx.match_start(&rel).is_some()
            || rx.match_start(&p).is_some()
    }))
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 글롭 조각마다 python 과 같은 패턴 글.
    #[test]
    fn patterns_like_python() {
        assert_eq!(to_pattern("**/*.ts"), r"(?:.*/)?[^/]*\.ts\Z");
        assert_eq!(to_pattern("a/**"), r"a/.*\Z");
        assert_eq!(to_pattern("*.{py,{ts,js}}"), r"[^/]*\.(?:py|(?:ts|js))\Z");
        assert_eq!(to_pattern("x{a,b"), r"x(?:a|b)\Z");
        assert_eq!(to_pattern("[!a]b[]c"), r"[^a]b\[\]c\Z");
        assert_eq!(to_pattern("a,b}"), r"a,b\}\Z");
    }

    /// 프로젝트 안은 상대 경로로, 밖은 앞 `/` 를 뗀 절대 경로로 맞춘다.
    #[test]
    fn matches_relative_inside_and_absolute_outside() {
        let rx = [compile("src/**/*.ts").unwrap()];
        assert!(rule_matches(&rx, "/p/src/a/b.ts", "/p").unwrap());
        assert!(!rule_matches(&rx, "/p/other/src/a/b.ts", "/p").unwrap());
        assert!(rule_matches(&[compile("**/*.ts").unwrap()], "/elsewhere/x.ts", "/p").unwrap());
    }
}
