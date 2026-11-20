//! python `repr(text)` 의 글(알림에 `%r` 로 넣는 낱말).
//!
//! ASCII 글만 옮겼다. ASCII 밖 글자는 python 이 `str.isprintable()`(Unicode 범주 표)로 그대로 둘지 escape 할지 정해
//! 그 표가 없는 여기서는 `None` 을 돌려준다. 부르는 곳은 그 자리를 옮기지 않은 것으로 다룬다.

/// python `repr(text)`. ASCII 밖 글자가 있으면 `None`.
///
/// 따옴표는 python 처럼 고른다: `'` 가 있고 `"` 가 없으면 `"`, 아니면 `'`(그때 글 안의 `'` 는 `\'`).
pub fn repr_ascii(text: &str) -> Option<String> {
    if !text.is_ascii() {
        return None;
    }
    let quote = if text.contains('\'') && !text.contains('"') {
        '"'
    } else {
        '\''
    };

    let mut out = String::with_capacity(text.len() + 2);
    out.push(quote);
    for c in text.chars() {
        match c {
            '\\' => out.push_str("\\\\"),
            '\t' => out.push_str("\\t"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            c if c == quote => {
                out.push('\\');
                out.push(c);
            }
            c if c < ' ' || c == '\u{7f}' => out.push_str(&format!("\\x{:02x}", u32::from(c))),
            c => out.push(c),
        }
    }
    out.push(quote);
    Some(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 따옴표 고르기와 제어 문자 escape 가 python `repr` 과 같다.
    #[test]
    fn repr_like_python() {
        // python picks double quotes only when the text has ' and no "
        assert_eq!(repr_ascii("a=b").as_deref(), Some("'a=b'"));
        assert_eq!(repr_ascii("it's").as_deref(), Some("\"it's\""));
        assert_eq!(repr_ascii("'\"").as_deref(), Some("'\\'\"'"));

        // Control characters use the short escapes, then \xhh
        assert_eq!(
            repr_ascii("\t\x01\x7f\\").as_deref(),
            Some("'\\t\\x01\\x7f\\\\'")
        );

        // Non-ASCII needs python's printable table
        assert_eq!(repr_ascii("\u{e9}"), None);
    }
}
