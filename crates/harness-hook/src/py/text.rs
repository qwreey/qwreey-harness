//! python `str` 의 공백 판정, `strip`, `split()`, `splitlines()`.

/// python `str.isspace()` 와 정규식 `\s` 가 공백으로 보는 문자.
///
/// Rust 의 `char::is_whitespace`(Unicode White_Space)에 python 이 더 보는 U+001C..U+001F(정보 구분 문자)를 더했다.
pub fn is_space(c: char) -> bool {
    c.is_whitespace() || matches!(c, '\u{1c}'..='\u{1f}')
}

/// python `str.strip()`.
pub fn strip(s: &str) -> &str {
    s.trim_matches(is_space)
}

/// python `str.split()`(인자 없음): 공백 덩어리로 나누고 빈 조각은 뺀다.
pub fn split_whitespace(s: &str) -> impl Iterator<Item = &str> {
    s.split(is_space).filter(|part| !part.is_empty())
}

/// python `str.splitlines()` 이 줄 끝으로 보는 문자(`\r\n` 은 [`splitlines`] 가 한 번으로 친다).
pub fn is_line_break(c: char) -> bool {
    matches!(
        c,
        '\n' | '\r'
            | '\u{0b}'
            | '\u{0c}'
            | '\u{1c}'
            | '\u{1d}'
            | '\u{1e}'
            | '\u{85}'
            | '\u{2028}'
            | '\u{2029}'
    )
}

/// python `str.splitlines()`: 줄 끝 문자로 나누고 끝 문자는 뺀다. 마지막 줄 끝 뒤의 빈 줄은 없다.
pub fn splitlines(s: &str) -> Vec<&str> {
    let mut lines = Vec::new();
    let mut start = 0;
    let mut chars = s.char_indices().peekable();
    while let Some((i, c)) = chars.next() {
        if !is_line_break(c) {
            continue;
        }
        lines.push(&s[start..i]);

        // CRLF 는 줄 끝 하나
        start = i + c.len_utf8();
        if c == '\r' && chars.peek().is_some_and(|&(_, next)| next == '\n') {
            chars.next();
            start += 1;
        }
    }

    if start < s.len() {
        lines.push(&s[start..]);
    }
    lines
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn splitlines_matches_python_examples() {
        assert_eq!(splitlines(""), Vec::<&str>::new());
        assert_eq!(splitlines("a\n"), vec!["a"]);
        assert_eq!(
            splitlines("a\r\n\rb\u{2028}c\u{1c}"),
            vec!["a", "", "b", "c"]
        );
        assert_eq!(splitlines("\n\n"), vec!["", ""]);
    }

    #[test]
    fn strip_and_split_use_python_spaces() {
        assert_eq!(strip("\u{1f}\u{3000} a b\u{85}"), "a b");
        assert_eq!(
            split_whitespace(" choom\t-n\u{a0}1000 ").collect::<Vec<_>>(),
            vec!["choom", "-n", "1000"]
        );
    }
}
