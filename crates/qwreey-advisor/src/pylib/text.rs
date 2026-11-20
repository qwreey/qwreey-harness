//! python `str` 동작 몇 가지: 글자 단위 자르기, `textwrap.dedent`, 인코딩 오류 처리(`replace`, `backslashreplace`).

use std::cmp::Ordering;

use harness_hook::py::surrogate::unit_of;
use harness_hook::py::text::is_space;

/// python `s[:n]`: 앞 `n` 글자(바이트가 아니라 코드 포인트).
pub fn take_chars(s: &str, n: usize) -> &str {
    match s.char_indices().nth(n) {
        Some((at, _)) => &s[..at],
        None => s,
    }
}

/// python `s[n:]`: 앞 `n` 글자를 뺀 나머지.
pub fn skip_chars(s: &str, n: usize) -> &str {
    match s.char_indices().nth(n) {
        Some((at, _)) => &s[at..],
        None => "",
    }
}

/// python `str.isspace()`: 비어 있지 않고 모든 글자가 공백.
pub fn is_space_str(s: &str) -> bool {
    !s.is_empty() && s.chars().all(is_space)
}

/// python `s.encode("utf-8", "replace")`: 짝 없는 서로게이트(자리표)는 `?` 다.
pub fn encode_replace(s: &str) -> Vec<u8> {
    let mut out = Vec::with_capacity(s.len());
    for c in s.chars() {
        if unit_of(c).is_some() {
            out.push(b'?');
        } else {
            out.extend_from_slice(c.encode_utf8(&mut [0; 4]).as_bytes());
        }
    }
    out
}

/// python stderr(UTF-8, `backslashreplace`)에 쓸 바이트: 짝 없는 서로게이트는 4자리 `\u` escape 글이 된다.
pub fn stderr_bytes(s: &str) -> Vec<u8> {
    let mut out = Vec::with_capacity(s.len());
    for c in s.chars() {
        match unit_of(c) {
            Some(unit) => out.extend_from_slice(format!("\\u{unit:04x}").as_bytes()),
            None => out.extend_from_slice(c.encode_utf8(&mut [0; 4]).as_bytes()),
        }
    }
    out
}

// python 의 str 비교: 코드 포인트 순서. 자리표는 제 서로게이트 코드 자리에 놓는다
fn py_cmp(a: &str, b: &str) -> Ordering {
    let code = |c: char| unit_of(c).unwrap_or(u32::from(c));
    a.chars().map(code).cmp(b.chars().map(code))
}

/// python `textwrap.dedent(text)`(3.14): 비지 않은 줄들의 공통 앞 공백(` `, `\t`)을 떼고, 공백뿐인 줄은 빈 줄로.
pub fn dedent(text: &str) -> String {
    let lines: Vec<&str> = text.split('\n').collect();

    // Common margin of the smallest and largest non-blank lines
    let non_blank = lines.iter().filter(|l| !l.is_empty() && !is_space_str(l));
    let first = non_blank.clone().min_by(|a, b| py_cmp(a, b)).copied();
    let last = non_blank.max_by(|a, b| py_cmp(a, b)).copied();
    let margin = match (first, last) {
        (Some(first), Some(last)) => {
            let mut other = last.chars();
            first
                .chars()
                .take_while(|&c| other.next() == Some(c) && (c == ' ' || c == '\t'))
                .count()
        }
        _ => 0,
    };

    // Cut the margin, blank out whitespace-only lines
    let out: Vec<&str> = lines
        .iter()
        .map(|l| {
            if is_space_str(l) {
                ""
            } else {
                skip_chars(l, margin)
            }
        })
        .collect();
    out.join("\n")
}

#[cfg(test)]
mod tests {
    use super::*;

    /// dedent 은 공통 앞 공백만 떼고, 탭과 공백은 같은 것으로 보지 않는다.
    #[test]
    fn dedent_like_python() {
        // Common spaces go, deeper indents stay
        assert_eq!(dedent("  a\n    b\n  c"), "a\n  b\nc");

        // Whitespace-only lines become empty and do not count
        assert_eq!(dedent("  a\n   \n  b\n"), "a\n\nb\n");

        // A tab and spaces share no margin
        assert_eq!(dedent("\ta\n  b"), "\ta\n  b");

        // No non-blank line: margin 0
        assert_eq!(dedent(" \n"), "\n");
    }

    /// 글자 단위 자르기는 바이트가 아니라 코드 포인트로 센다.
    #[test]
    fn slices_by_code_point() {
        assert_eq!(take_chars("\u{d55c}\u{ae00}x", 2), "\u{d55c}\u{ae00}");
        assert_eq!(take_chars("ab", 5), "ab");
        assert_eq!(skip_chars("\u{d55c}x", 1), "x");
        assert_eq!(skip_chars("a", 3), "");
    }
}
