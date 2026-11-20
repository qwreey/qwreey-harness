//! python `repr(str)`, `str.isprintable()`, `str.isdigit()`.
//!
//! 거절 사유(`{path!r}`)가 python 과 같은 글이어야 해서 둔다. 판정 표는 [`super::unicode_extra`](만든 파일)다.

use harness_hook::py::surrogate::unit_of;
use harness_hook::py::unicode::is_decimal;

use super::unicode_extra::{DIGIT_NOT_DECIMAL, NOT_PRINTABLE};

fn in_table(table: &[(u32, u32)], code: u32) -> bool {
    table
        .binary_search_by(|&(lo, hi)| {
            if hi < code {
                std::cmp::Ordering::Less
            } else if lo > code {
                std::cmp::Ordering::Greater
            } else {
                std::cmp::Ordering::Equal
            }
        })
        .is_ok()
}

/// python `c.isprintable()`. 서로게이트 자리표는 python 의 서로게이트처럼 거짓이다.
pub fn is_printable(c: char) -> bool {
    unit_of(c).is_none() && !in_table(NOT_PRINTABLE, u32::from(c))
}

/// python `str.isdigit()`: 비어 있지 않고 모든 글자가 숫자(십진 숫자와 위 첨자 같은 숫자)다.
pub fn is_digit_str(s: &str) -> bool {
    !s.is_empty()
        && s.chars().all(|c| {
            let code = u32::from(c);
            unit_of(c).is_none() && (is_decimal(code) || in_table(DIGIT_NOT_DECIMAL, code))
        })
}

/// python `repr(s)`: 따옴표를 고르고(`'` 가 있고 `"` 가 없으면 `"`), escape 할 글자를 escape 한다.
pub fn repr_str(s: &str) -> String {
    let quote = if s.contains('\'') && !s.contains('"') {
        '"'
    } else {
        '\''
    };
    let mut out = String::with_capacity(s.len() + 2);
    out.push(quote);
    for c in s.chars() {
        push_escaped(&mut out, c, quote);
    }
    out.push(quote);
    out
}

fn push_escaped(out: &mut String, c: char, quote: char) {
    // 서로게이트 자리표는 python 처럼 그 서로게이트 코드의 4자리 escape
    if let Some(unit) = unit_of(c) {
        out.push_str(&format!("\\u{unit:04x}"));
        return;
    }

    // Named escapes, printable ASCII, then by printability
    match c {
        '\\' => out.push_str("\\\\"),
        '\t' => out.push_str("\\t"),
        '\n' => out.push_str("\\n"),
        '\r' => out.push_str("\\r"),
        c if c == quote => {
            out.push('\\');
            out.push(c);
        }
        c if (' '..='\u{7e}').contains(&c) => out.push(c),
        c if c.is_ascii() => out.push_str(&format!("\\x{:02x}", u32::from(c))),
        c if is_printable(c) => out.push(c),
        c => {
            let code = u32::from(c);
            if code <= 0xff {
                out.push_str(&format!("\\x{code:02x}"));
            } else if code <= 0xffff {
                out.push_str(&format!("\\u{code:04x}"));
            } else {
                out.push_str(&format!("\\U{code:08x}"));
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use harness_hook::py::surrogate::placeholder;

    /// repr 의 따옴표 고르기와 escape 가 python 과 같다.
    #[test]
    fn repr_matches_python() {
        // Quote choice: double quotes only when the text has ' and no "
        assert_eq!(repr_str("a'b"), "\"a'b\"");
        assert_eq!(repr_str("a'\"b"), "'a\\'\"b'");
        assert_eq!(repr_str(""), "''");

        // Control characters, non-printables and printable non-ASCII
        assert_eq!(repr_str("\t\n\r\\\u{7}"), "'\\t\\n\\r\\\\\\x07'");
        assert_eq!(
            repr_str("\u{a0}\u{ad}\u{200b}\u{e9}\u{d55c}"),
            "'\\xa0\\xad\\u200b\u{e9}\u{d55c}'",
            "NBSP and soft hyphen are not printable in python, Latin and Hangul are"
        );
        assert_eq!(repr_str("\u{e0001}"), "'\\U000e0001'");

        // A lone surrogate shows as its escape
        let lone = placeholder(0xdc80).expect("surrogate placeholder");
        assert_eq!(repr_str(&lone.to_string()), "'\\udc80'");
    }

    /// isdigit 은 십진 숫자에 위 첨자 같은 숫자를 더 받고, 빈 글은 거짓이다.
    #[test]
    fn isdigit_takes_superscripts() {
        assert!(is_digit_str("12"));
        assert!(
            is_digit_str("\u{b2}"),
            "superscript two is a digit, not a decimal"
        );
        assert!(!is_digit_str(""));
        assert!(!is_digit_str("1a"));
    }
}
