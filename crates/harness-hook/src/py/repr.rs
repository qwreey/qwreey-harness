//! python `repr(str)`, `repr(v)`, `str.isprintable()`, `str.isdigit()`.
//!
//! 알림과 거절 사유에 `%r`, `{x!r}`, `str(v)` 로 들어가는 글이 python 과 같아야 해서 둔다. 판정 표는
//! `unicode_extra`(gen-unicode-extra.py 가 만든 파일)다.

use std::cmp::Ordering;

use super::surrogate::unit_of;
use super::unicode::is_decimal;
use super::unicode_extra::{DIGIT_NOT_DECIMAL, NOT_PRINTABLE};
use super::value::Value;

fn in_table(table: &[(u32, u32)], code: u32) -> bool {
    table
        .binary_search_by(|&(lo, hi)| {
            if hi < code {
                Ordering::Less
            } else if lo > code {
                Ordering::Greater
            } else {
                Ordering::Equal
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

/// python `repr(text)` 를 ASCII 글에만. ASCII 밖 글자가 있으면 `None`.
///
/// 그 자리를 옮기지 않은 것으로 다루던 곳을 위해 남긴다. 새 코드는 [`repr_str`] 를 쓴다.
pub fn repr_ascii(text: &str) -> Option<String> {
    text.is_ascii().then(|| repr_str(text))
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

/// python `repr(v)`: JSON 에서 온 값. 글은 따옴표로, 목록과 dict 는 원소마다 repr 이다.
///
/// python 은 `json.loads` 가 받는 깊이면 `repr` 도 끝내므로, 깊이에 상관없이 호출 스택 대신 작업 목록으로 돈다.
pub fn repr_value(v: &Value) -> String {
    let mut out = String::new();
    let mut work = vec![Piece::Value(v)];
    while let Some(piece) = work.pop() {
        match piece {
            Piece::Text(text) => out.push_str(text),
            Piece::Key(key) => out.push_str(&repr_str(key)),
            Piece::Value(value) => open_value(&mut out, &mut work, value),
        }
    }
    out
}

/// python `str(v)`: 글은 그대로, 그 밖은 [`repr_value`] 와 같다.
pub fn str_value(v: &Value) -> String {
    match v {
        Value::Str(s) => s.clone(),
        other => repr_value(other),
    }
}

/// python `str(v or "")`: 없거나 거짓 값이면 빈 글, 아니면 [`str_value`].
pub fn truthy_str(v: Option<&Value>) -> String {
    match v {
        Some(v) if v.truthy() => str_value(v),
        _ => String::new(),
    }
}

// 아직 쓰지 않은 repr 조각(작업 목록은 뒤에서 꺼내므로 거꾸로 쌓는다)
enum Piece<'a> {
    Value(&'a Value),
    Key(&'a str),
    Text(&'static str),
}

// 값 하나를 쓰거나, 그릇이면 여는 괄호를 쓰고 원소와 닫는 괄호를 작업 목록에 쌓는다
fn open_value<'a>(out: &mut String, work: &mut Vec<Piece<'a>>, v: &'a Value) {
    match v {
        // Text is quoted
        Value::Str(s) => out.push_str(&repr_str(s)),

        // Lists: items separated by commas
        Value::List(items) => {
            out.push('[');
            work.push(Piece::Text("]"));
            for (i, item) in items.iter().enumerate().rev() {
                work.push(Piece::Value(item));
                if i > 0 {
                    work.push(Piece::Text(", "));
                }
            }
        }

        // Dicts: quoted key, colon, value
        Value::Dict(dict) => {
            out.push('{');
            work.push(Piece::Text("}"));
            let entries: Vec<(&str, &Value)> = dict.iter().collect();
            for (i, (key, value)) in entries.into_iter().enumerate().rev() {
                work.push(Piece::Value(value));
                work.push(Piece::Text(": "));
                work.push(Piece::Key(key));
                if i > 0 {
                    work.push(Piece::Text(", "));
                }
            }
        }

        // Scalars print as str() does
        scalar => out.push_str(&scalar.scalar_str().unwrap_or_default()),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::py::json_load::{MAX_DEPTH, loads};
    use crate::py::surrogate::placeholder;

    /// repr 의 따옴표 고르기와 escape 가 python 과 같다.
    #[test]
    fn repr_matches_python() {
        // Quote choice: double quotes only when the text has ' and no "
        assert_eq!(repr_str("a'b"), "\"a'b\"");
        assert_eq!(repr_str("a'\"b"), "'a\\'\"b'");
        assert_eq!(repr_str(""), "''");

        // Control characters, non-printables and printable non-ASCII
        assert_eq!(repr_str("\t\n\r\\\u{7}\u{7f}"), "'\\t\\n\\r\\\\\\x07\\x7f'");
        assert_eq!(
            repr_str("\u{a0}\u{ad}\u{200b}\u{e9}\u{d55c}"),
            "'\\xa0\\xad\\u200b\u{e9}\u{d55c}'",
            "NBSP and soft hyphen are not printable in python, Latin and Hangul are"
        );
        assert_eq!(repr_str("\u{e0001}"), "'\\U000e0001'");

        // A lone surrogate shows as its escape
        let lone = placeholder(0xdc80).expect("surrogate placeholder");
        assert_eq!(repr_str(&lone.to_string()), "'\\udc80'");

        // The ASCII-only form refuses other text
        assert_eq!(repr_ascii("it's").as_deref(), Some("\"it's\""));
        assert_eq!(repr_ascii("\u{e9}"), None);
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

    /// 목록과 dict 의 str() 은 python repr 이고, 글은 그대로다.
    #[test]
    fn str_of_values_like_python() {
        let v =
            loads(r#"[1, 2.5, "a'b", {"k": null, "\u00e9": ["\u00a0"]}, true, [], {}]"#).unwrap();
        assert_eq!(
            str_value(&v),
            "[1, 2.5, \"a'b\", {'k': None, 'é': ['\\xa0']}, True, [], {}]"
        );
        assert_eq!(str_value(&Value::Str("x/y".into())), "x/y");
    }

    /// json_load 가 받는 가장 깊은 값도 호출 스택 없이 끝난다(python 도 끝낸다).
    #[test]
    fn deepest_value_has_no_recursion() {
        let deep = format!("{}\"a\"{}", "[".repeat(MAX_DEPTH), "]".repeat(MAX_DEPTH));
        let text = str_value(&loads(&deep).unwrap());
        let expected = format!("{}'a'{}", "[".repeat(MAX_DEPTH), "]".repeat(MAX_DEPTH));
        assert!(text == expected, "deep repr differs");
    }
}
