//! python `json.dumps(value)`, `json.dumps(value, ensure_ascii=False)` 와 같은 바이트를 쓰는 serde_json Formatter.
//!
//! python 기본값: 구분자는 `", "` 와 `": "`, 따옴표, 역슬래시, 0x20 미만 제어 문자는 escape(`\n`, `\u001f` 처럼
//! 소문자 hex)한다. `ensure_ascii=True`(기본)면 0x20..0x7e 밖의 모든 문자를 `\uXXXX`(BMP 밖은 서로게이트 쌍)로 쓴다.
//! serde_json 의 기본 escape 는 제어 문자 쪽이 python 과 같아서 그대로 쓰고, 구분자와 ASCII 밖 문자만 바꾼다.
//! 짝 없는 서로게이트의 자리표([`super::surrogate`])는 `ensure_ascii=True` 에서 python 처럼 `\udcff` 꼴 하나로 쓴다.

use std::io::{self, Write};

use serde::Serialize;
use serde_json::ser::Formatter;

use super::num::float_repr;
use super::surrogate::unit_of;

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
    /// `indent=n` 이면 `Some(n)`: 항목마다 줄을 바꾸고 깊이마다 공백 n 개, 항목 구분자는 `","`(python 이 indent 를 주면 바꾼다).
    indent: Option<usize>,
    depth: usize,
    has_value: bool,
}

impl PyFormatter {
    /// `ensure_ascii` 를 정한 Formatter.
    pub fn new(ascii: EnsureAscii) -> PyFormatter {
        PyFormatter {
            ascii,
            indent: None,
            depth: 0,
            has_value: false,
        }
    }

    /// python `json.dumps(value, ensure_ascii=..., indent=indent)` 꼴.
    pub fn indented(ascii: EnsureAscii, indent: usize) -> PyFormatter {
        PyFormatter {
            indent: Some(indent),
            ..PyFormatter::new(ascii)
        }
    }

    // 항목 앞: 첫 항목이 아니면 구분자, indent 가 있으면 줄바꿈과 들여쓰기
    fn item_start<W: ?Sized + Write>(&mut self, writer: &mut W, first: bool) -> io::Result<()> {
        match self.indent {
            None if first => Ok(()),
            None => writer.write_all(b", "),
            Some(width) => {
                writer.write_all(if first { b"\n" } else { b",\n" })?;
                writer.write_all(" ".repeat(width * self.depth).as_bytes())
            }
        }
    }

    // 묶음 끝: indent 가 있고 항목이 있었으면 줄을 바꿔 한 단계 덜 들여 쓴 뒤 닫는다
    fn group_end<W: ?Sized + Write>(&mut self, writer: &mut W, close: &[u8]) -> io::Result<()> {
        self.depth = self.depth.saturating_sub(1);
        if let Some(width) = self.indent
            && self.has_value
        {
            writer.write_all(b"\n")?;
            writer.write_all(" ".repeat(width * self.depth).as_bytes())?;
        }
        writer.write_all(close)
    }
}

impl Formatter for PyFormatter {
    fn begin_array<W: ?Sized + Write>(&mut self, writer: &mut W) -> io::Result<()> {
        self.depth += 1;
        self.has_value = false;
        writer.write_all(b"[")
    }

    fn end_array<W: ?Sized + Write>(&mut self, writer: &mut W) -> io::Result<()> {
        self.group_end(writer, b"]")
    }

    fn begin_array_value<W: ?Sized + Write>(
        &mut self,
        writer: &mut W,
        first: bool,
    ) -> io::Result<()> {
        self.item_start(writer, first)
    }

    fn end_array_value<W: ?Sized + Write>(&mut self, _writer: &mut W) -> io::Result<()> {
        self.has_value = true;
        Ok(())
    }

    fn begin_object<W: ?Sized + Write>(&mut self, writer: &mut W) -> io::Result<()> {
        self.depth += 1;
        self.has_value = false;
        writer.write_all(b"{")
    }

    fn end_object<W: ?Sized + Write>(&mut self, writer: &mut W) -> io::Result<()> {
        self.group_end(writer, b"}")
    }

    fn begin_object_key<W: ?Sized + Write>(
        &mut self,
        writer: &mut W,
        first: bool,
    ) -> io::Result<()> {
        self.item_start(writer, first)
    }

    fn end_object_value<W: ?Sized + Write>(&mut self, _writer: &mut W) -> io::Result<()> {
        self.has_value = true;
        Ok(())
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
            // python 글의 짝 없는 서로게이트(자리표)는 그 코드 하나로
            if let Some(unit) = unit_of(c) {
                write!(writer, "\\u{unit:04x}")?;
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

/// `value` 를 python `json.dumps(value, ensure_ascii=..., indent=n)` 꼴 문자열로.
///
/// 오류는 [`to_string`] 과 같다.
pub fn to_string_indented<T: Serialize + ?Sized>(
    value: &T,
    ascii: EnsureAscii,
    indent: usize,
) -> serde_json::Result<String> {
    let mut out = Vec::new();
    let mut ser =
        serde_json::Serializer::with_formatter(&mut out, PyFormatter::indented(ascii, indent));
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

    #[test]
    fn indented_matches_python_dumps() {
        // python: json.dumps({"a": [1, {}], "b": {"c": []}, "d": "é"}, ensure_ascii=False, indent=1)
        let v = json!({"a": [1, {}], "b": {"c": []}, "d": "\u{e9}"});
        assert_eq!(
            to_string_indented(&v, EnsureAscii::No, 1).unwrap(),
            "{\n \"a\": [\n  1,\n  {}\n ],\n \"b\": {\n  \"c\": []\n },\n \"d\": \"\u{e9}\"\n}"
        );
        assert_eq!(
            to_string_indented(&json!({}), EnsureAscii::No, 1).unwrap(),
            "{}"
        );
    }

    #[test]
    fn lone_surrogates_render_like_python() {
        // python: json.dumps("a\udcff\ud800b") == '"a\\udcff\\ud800b"'
        let text = format!(
            "a{}{}b",
            crate::py::surrogate::placeholder(0xDCFF).unwrap(),
            crate::py::surrogate::placeholder(0xD800).unwrap()
        );
        assert_eq!(
            to_string(&text, EnsureAscii::Yes).unwrap(),
            r#""a\udcff\ud800b""#
        );
    }
}
