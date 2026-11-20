//! 정본 영역의 큰따옴표 리터럴(python `copy_regions.string_value` 의 python 밖 언어 갈래, `_unescape`)과 `quote`.
//!
//! 오류 글은 python 예외의 `str()` 이다: `int(x, 16)` 의 ValueError, `str.index` 의 "substring not found",
//! `chr()` 의 범위 오류, MarkError 의 "unknown escape". `chr()` 이 OverflowError 를 내는 큰 수는 python 이 잡지 않아 예외로 끝난다.

use std::sync::LazyLock;

use harness_hook::py::re::Regex;
use harness_hook::py::repr::repr_ascii;
use harness_hook::py::surrogate::placeholder;
use harness_hook::py::text::{is_space, strip};
use harness_hook::py::unicode::decimal_value;

use crate::halt::{Halt, Result};
use crate::reuse::regions::MARK;

static STR_LIT: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r#""((?:[^"\\\n]|\\.)*)""#).expect("constant pattern"));

/// python `quote(value)`: python, Rust, JS/TS, Luau 가 모두 읽는 큰따옴표 리터럴.
///
/// 네 언어가 함께 받는 escape 만 쓰고, 다른 제어 문자는 `\xHH` 다. ASCII 밖 글자는 그대로 둔다.
pub fn quote(value: &str) -> String {
    let mut out = String::with_capacity(value.len() + 2);
    out.push('"');
    for c in value.chars() {
        match c {
            '\\' => out.push_str("\\\\"),
            '"' => out.push_str("\\\""),
            '\n' => out.push_str("\\n"),
            '\t' => out.push_str("\\t"),
            '\r' => out.push_str("\\r"),
            c if c < ' ' || c == '\u{7f}' => out.push_str(&format!("\\x{:02x}", u32::from(c))),
            c => out.push(c),
        }
    }
    out.push('"');
    out
}

/// 주석과 표시 줄을 뺀 글의 큰따옴표 리터럴들, escape 를 푼 값.
///
/// 안쪽 `Err` 는 python 이 잡는 오류의 글(첫 오류에서 멈춘다), 바깥은 이 판이 옮기지 않았거나 python 이 끝나는 자리다.
pub fn c_literals(lines: &[&str]) -> Result<std::result::Result<Vec<String>, String>> {
    let code: Vec<&str> = lines
        .iter()
        .copied()
        .filter(|x| MARK.match_start(x).is_none())
        .filter(|x| {
            let t = x.trim_start_matches(is_space);
            !(t.starts_with("//") || t.starts_with("--") || t.starts_with('#'))
        })
        .collect();
    let code = code.join("\n");

    let mut found = Vec::new();
    for m in STR_LIT.find_iter(&code) {
        match unescape(m.text(&code, 1).unwrap_or(""))? {
            Ok(v) => found.push(v),
            Err(e) => return Ok(Err(e)),
        }
    }
    Ok(Ok(found))
}

// python _unescape: C 꼴 escape. 위치는 글자 단위다(python 이 s[i + 2:i + 4] 로 자른다)
fn unescape(s: &str) -> Result<std::result::Result<String, String>> {
    let chars: Vec<char> = s.chars().collect();
    let slice = |a: usize, b: usize| -> String {
        chars[a.min(chars.len())..b.min(chars.len())]
            .iter()
            .collect()
    };

    let mut out = String::new();
    let mut i = 0;
    while i < chars.len() {
        // Plain characters and a trailing backslash
        let c = chars[i];
        if c != '\\' || i + 1 >= chars.len() {
            out.push(c);
            i += 1;
            continue;
        }

        // One escape
        let e = chars[i + 1];
        let (code, next) = match e {
            'n' => (Ok('\n'), i + 2),
            't' => (Ok('\t'), i + 2),
            'r' => (Ok('\r'), i + 2),
            '0' => (Ok('\0'), i + 2),
            '\\' | '"' | '\'' => (Ok(e), i + 2),
            'x' => (hex_char(&slice(i + 2, i + 4))?, i + 4),
            'u' if chars.get(i + 2) == Some(&'{') => {
                let Some(j) = chars[i..].iter().position(|&c| c == '}').map(|p| p + i) else {
                    return Ok(Err("substring not found".to_owned()));
                };
                (hex_char(&slice(i + 3, j))?, j + 1)
            }
            'u' => (hex_char(&slice(i + 2, i + 6))?, i + 6),
            _ => return Ok(Err(format!("unknown escape \\{e}"))),
        };

        // The escaped character or the first error
        match code {
            Ok(c) => out.push(c),
            Err(msg) => return Ok(Err(msg)),
        }
        i = next;
    }
    Ok(Ok(out))
}

// python chr(int(text, 16)): 읽지 못하면 ValueError 글, 2^31 을 넘는 크기는 python 의 OverflowError(잡지 않는다)
fn hex_char(text: &str) -> Result<std::result::Result<char, String>> {
    let Some(n) = parse_hex(text) else {
        let shown = repr_ascii(text).ok_or(Halt::Unported("a non-ASCII bad hex escape"))?;
        return Ok(Err(format!(
            "invalid literal for int() with base 16: {shown}"
        )));
    };
    if !(-(1_i128 << 31)..(1_i128 << 31)).contains(&n) {
        return Err(Halt::PyError("chr() of a value past a C int"));
    }

    // python chr gives lone surrogates too
    let Ok(code) = u32::try_from(n) else {
        return Ok(Err("chr() arg not in range(0x110000)".to_owned()));
    };
    match char::from_u32(code).or_else(|| placeholder(code)) {
        Some(c) if code <= 0x10_FFFF => Ok(Ok(c)),
        _ => Ok(Err("chr() arg not in range(0x110000)".to_owned())),
    }
}

/// python `int(text, 16)`: 앞뒤 공백, 부호, `0x` 머리, 숫자 사이 `_` 하나, Unicode 십진 숫자를 받는다. 못 읽거나 i128 밖이면 `None`.
fn parse_hex(text: &str) -> Option<i128> {
    let t = strip(text);
    let (negative, t) = match t.as_bytes().first() {
        Some(b'-') => (true, &t[1..]),
        Some(b'+') => (false, &t[1..]),
        _ => (false, t),
    };

    // The 0x prefix may be followed by one underscore
    let (t, prefixed) = match t.get(..2) {
        Some("0x" | "0X") => (&t[2..], true),
        _ => (t, false),
    };
    let t = if prefixed {
        t.strip_prefix('_').unwrap_or(t)
    } else {
        t
    };
    if t.is_empty() || t.starts_with('_') || t.ends_with('_') || t.contains("__") {
        return None;
    }

    // Digits
    let mut value: i128 = 0;
    for c in t.chars().filter(|&c| c != '_') {
        let d = c.to_digit(16).or_else(|| decimal_value(c))?;
        value = value.checked_mul(16)?.checked_add(i128::from(d))?;
    }
    Some(if negative { -value } else { value })
}

#[cfg(test)]
mod tests {
    use super::*;

    /// python `quote` 는 네 언어가 함께 읽는 escape 만 쓴다.
    #[test]
    fn quotes_for_all_languages() {
        assert_eq!(
            quote("a\"b\\\n\u{1}\u{7f}\u{e9}"),
            "\"a\\\"b\\\\\\n\\x01\\x7f\u{e9}\""
        );
    }

    /// escape 와 오류 글이 python `_unescape` 와 같다.
    #[test]
    fn unescapes_like_python() {
        // Simple and hex escapes
        assert_eq!(
            c_literals(&[r#"X = "a\n\x41\u{1F600}é""#]).unwrap(),
            Ok(vec!["a\nA\u{1F600}\u{e9}".to_owned()])
        );

        // int(x, 16) takes a sign and spaces, as python does
        assert_eq!(unescape(r"\x+1").unwrap(), Ok("\u{1}".to_owned()));
        assert_eq!(
            unescape(r"\xzz").unwrap(),
            Err("invalid literal for int() with base 16: 'zz'".to_owned())
        );
        assert_eq!(
            unescape(r"\q").unwrap(),
            Err("unknown escape \\q".to_owned())
        );
        assert_eq!(
            unescape(r"\u{110000}").unwrap(),
            Err("chr() arg not in range(0x110000)".to_owned())
        );
        assert_eq!(
            unescape(r"\u{12").unwrap(),
            Err("substring not found".to_owned())
        );

        // A huge code point is python's uncaught OverflowError
        assert!(unescape(r"\u{FFFFFFFFFF}").is_err());

        // Comment and marker lines are skipped
        assert_eq!(
            c_literals(&["// \"no\"", "  -- \"no\"", "v = \"yes\""]).unwrap(),
            Ok(vec!["yes".to_owned()])
        );
    }
}
