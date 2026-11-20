//! python `json.dumps(value)`, `json.dumps(value, ensure_ascii=False)` 와 같은 바이트를 쓰는 serde_json Formatter.
//!
//! python 기본값: 구분자는 `", "` 와 `": "`, 따옴표, 역슬래시, 0x20 미만 제어 문자는 escape(`\n`, `\u001f` 처럼
//! 소문자 hex)한다. `ensure_ascii=True`(기본)면 0x20..0x7e 밖의 모든 문자를 `\uXXXX`(BMP 밖은 서로게이트 쌍)로 쓴다.
//! serde_json 의 기본 escape 는 제어 문자 쪽이 python 과 같아서 그대로 쓰고, 구분자와 ASCII 밖 문자만 바꾼다.

use std::io::{self, Write};

use serde::Serialize;
use serde_json::ser::Formatter;

use super::num::float_repr;

/// python `json.dumps` 의 `ensure_ascii`.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum EnsureAscii {
    /// `ensure_ascii=True`(python 기본): ASCII 밖 문자와 DEL 을 `\uXXXX` 로 쓴다.
    Yes,
    /// `ensure_ascii=False`: 제어 문자만 escape 하고 나머지는 UTF-8 그대로.
    No,
}

/// python 기본 `json.dumps` 와 같은 꼴로 쓰는 Formatter.
pub struct PyFormatter {
    ascii: EnsureAscii,
}

impl PyFormatter {
    /// `ensure_ascii` 를 정한 Formatter.
    pub fn new(ascii: EnsureAscii) -> PyFormatter {
        PyFormatter { ascii }
    }
}

impl Formatter for PyFormatter {
    fn begin_array_value<W: ?Sized + Write>(
        &mut self,
        writer: &mut W,
        first: bool,
    ) -> io::Result<()> {
        if first {
            Ok(())
        } else {
            writer.write_all(b", ")
        }
    }

    fn begin_object_key<W: ?Sized + Write>(
        &mut self,
        writer: &mut W,
        first: bool,
    ) -> io::Result<()> {
        if first {
            Ok(())
        } else {
            writer.write_all(b", ")
        }
    }

    fn begin_object_value<W: ?Sized + Write>(&mut self, writer: &mut W) -> io::Result<()> {
        writer.write_all(b": ")
    }

    fn write_f64<W: ?Sized + Write>(&mut self, writer: &mut W, value: f64) -> io::Result<()> {
        writer.write_all(float_repr(value).as_bytes())
    }

    fn write_f32<W: ?Sized + Write>(&mut self, writer: &mut W, value: f32) -> io::Result<()> {
        writer.write_all(float_repr(f64::from(value)).as_bytes())
    }

    // serde_json 은 따옴표, 역슬래시, 제어 문자를 뺀 조각만 여기로 넘긴다
    fn write_string_fragment<W: ?Sized + Write>(
        &mut self,
        writer: &mut W,
        fragment: &str,
    ) -> io::Result<()> {
        if self.ascii == EnsureAscii::No || fragment.bytes().all(|b| (0x20..0x7f).contains(&b)) {
            return writer.write_all(fragment.as_bytes());
        }
        let mut units = [0u16; 2];
        for c in fragment.chars() {
            if (' '..='~').contains(&c) {
                writer.write_all(&[c as u8])?;
                continue;
            }
            for unit in c.encode_utf16(&mut units).iter() {
                write!(writer, "\\u{unit:04x}")?;
            }
        }
        Ok(())
    }
}

/// `value` 를 python `json.dumps(value, ensure_ascii=...)` 와 같은 문자열로.
///
/// 오류는 serde_json 이 낼 수 있는 것(문자열이 아닌 맵 키, 실패하는 `Serialize` 구현)뿐이다.
/// 정수가 아닌 float 는 python 표기를 따르지만 NaN, 무한대는 serde_json 이 `null` 로 쓴다(python 은 `NaN`).
pub fn to_string<T: Serialize + ?Sized>(
    value: &T,
    ascii: EnsureAscii,
) -> serde_json::Result<String> {
    let mut out = Vec::new();
    let mut ser = serde_json::Serializer::with_formatter(&mut out, PyFormatter::new(ascii));
    value.serialize(&mut ser)?;
    Ok(String::from_utf8(out).expect("serde_json writes UTF-8"))
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    #[test]
    fn matches_python_dumps_examples() {
        let v = json!({"a": "\u{7f}\u{e9}\u{1f600}\u{1f}", "b": [1, 2.5, true, null]});
        assert_eq!(
            to_string(&v, EnsureAscii::Yes).unwrap(),
            r#"{"a": "\u007f\u00e9\ud83d\ude00\u001f", "b": [1, 2.5, true, null]}"#
        );
        assert_eq!(
            to_string(&v, EnsureAscii::No).unwrap(),
            "{\"a\": \"\u{7f}\u{e9}\u{1f600}\\u001f\", \"b\": [1, 2.5, true, null]}"
        );
    }
}
