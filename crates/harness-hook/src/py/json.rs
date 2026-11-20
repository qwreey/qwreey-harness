//! python `json.dumps(value)`, `json.dumps(value, ensure_ascii=False)` 와 같은 바이트를 쓰는 serde_json Formatter.
//!
//! python 기본값: 구분자는 `", "` 와 `": "`, 따옴표, 역슬래시, 0x20 미만 제어 문자는 escape(`\n`, `\u001f` 처럼
//! 소문자 hex)한다. `ensure_ascii=True`(기본)면 0x20..0x7e 밖의 모든 문자를 `\uXXXX`(BMP 밖은 서로게이트 쌍)로 쓴다.
//! serde_json 의 기본 escape 는 제어 문자 쪽이 python 과 같아서 그대로 쓰고, 구분자와 ASCII 밖 문자만 바꾼다.
//! 짝 없는 서로게이트의 자리표([`super::surrogate`])는 `ensure_ascii=True` 에서 python 처럼 `\udcff` 꼴 하나로 쓴다.
//!
//! 훅 출력 구조체는 serde 로([`to_string`]), python 값([`Value`])은 [`dumps`] 로 쓴다. serde_json 은 NaN, 무한대를 `null` 로
//! 쓰고 i128 을 넘는 정수를 담지 못해서, python 값은 serde 를 거치지 않는다.

use std::io::{self, Write};

use serde::Serialize;
use serde_json::ser::Formatter;

use super::num::float_repr;
use super::surrogate::unit_of;
use super::value::{Dict, Value};

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
/// 그런 값이 들 수 있는 python 값은 [`dumps`] 로 쓴다.
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

/// python 값을 `json.dumps(value, ensure_ascii=..., indent=...)` 와 같은 글로.
///
/// NaN, 무한대는 `NaN`, `Infinity`, `-Infinity`, 큰 정수는 그 숫자 그대로다. 깊은 중첩도 되부르지 않고 쓴다.
pub fn dumps(value: &Value, ascii: EnsureAscii, indent: Option<usize>) -> String {
    write_all(Work::Value(value, 0), ascii, indent)
}

/// dict 하나를 [`dumps`] 처럼(값으로 감싸려고 복사하지 않는다).
pub fn dumps_dict(dict: &Dict, ascii: EnsureAscii, indent: Option<usize>) -> String {
    write_all(Work::Dict(dict, 0), ascii, indent)
}

// 꺼낸 차례로 쓴다. 목록과 dict 는 항목을 다시 쌓는다
fn write_all(first: Work<'_>, ascii: EnsureAscii, indent: Option<usize>) -> String {
    let mut out = String::new();
    let mut work = vec![first];
    while let Some(item) = work.pop() {
        match item {
            Work::Text(text) => out.push_str(text),
            Work::Break(depth) => {
                out.push('\n');
                out.extend(std::iter::repeat_n(' ', indent.unwrap_or(0) * depth));
            }
            Work::Key(key) => {
                write_str(&mut out, key, ascii);
                out.push_str(": ");
            }
            Work::Value(value, depth) => {
                write_value(&mut out, &mut work, value, depth, ascii, indent)
            }
            Work::Dict(dict, depth) => {
                let items = dict.iter().map(|(k, v)| (Some(k), v)).collect();
                write_items(&mut out, &mut work, ("{", "}"), items, depth, indent);
            }
        }
    }
    out
}

/// [`dumps`] 가 쓸 차례. 스택에서 꺼낸 순서로 쓴다.
enum Work<'a> {
    Value(&'a Value, usize),
    Dict(&'a Dict, usize),
    Text(&'static str),
    /// 줄바꿈과 깊이만큼의 들여쓰기(indent 가 있을 때만 넣는다).
    Break(usize),
    Key(&'a str),
}

// 스칼라는 바로 쓴다
fn write_value<'a>(
    out: &mut String,
    work: &mut Vec<Work<'a>>,
    value: &'a Value,
    depth: usize,
    ascii: EnsureAscii,
    indent: Option<usize>,
) {
    match value {
        Value::Null => out.push_str("null"),
        Value::Bool(b) => out.push_str(if *b { "true" } else { "false" }),
        Value::Int(i) => out.push_str(&i.to_string()),
        Value::BigInt(digits) => out.push_str(digits),
        Value::Float(f) => out.push_str(&float_text(*f)),
        Value::Str(s) => write_str(out, s, ascii),
        Value::List(items) => {
            let items = items.iter().map(|v| (None, v)).collect();
            write_items(out, work, ("[", "]"), items, depth, indent);
        }
        Value::Dict(dict) => work.push(Work::Dict(dict, depth)),
    }
}

// 여는 괄호를 쓰고 항목들(dict 면 키와 함께)과 닫는 괄호를 쓸 차례에 둔다
fn write_items<'a>(
    out: &mut String,
    work: &mut Vec<Work<'a>>,
    (open, close): (&str, &'static str),
    items: Vec<(Option<&'a str>, &'a Value)>,
    depth: usize,
    indent: Option<usize>,
) {
    out.push_str(open);
    if items.is_empty() {
        out.push_str(close);
        return;
    }

    // 닫는 괄호부터 거꾸로 쌓는다
    work.push(Work::Text(close));
    if indent.is_some() {
        work.push(Work::Break(depth));
    }
    for (i, (key, item)) in items.into_iter().enumerate().rev() {
        work.push(Work::Value(item, depth + 1));
        if let Some(key) = key {
            work.push(Work::Key(key));
        }
        match (indent, i) {
            (Some(_), _) => work.push(Work::Break(depth + 1)),
            (None, 0) => {}
            (None, _) => work.push(Work::Text(", ")),
        }
        if indent.is_some() && i > 0 {
            work.push(Work::Text(","));
        }
    }
}

// python float.__repr__, 유한하지 않은 값은 json 의 낱말
fn float_text(f: f64) -> String {
    if f.is_nan() {
        "NaN".to_owned()
    } else if f.is_infinite() {
        if f > 0.0 { "Infinity" } else { "-Infinity" }.to_owned()
    } else {
        float_repr(f)
    }
}

// python 의 글 쓰기(encode_basestring, ensure_ascii 면 encode_basestring_ascii)
fn write_str(out: &mut String, s: &str, ascii: EnsureAscii) {
    out.push('"');
    for c in s.chars() {
        match c {
            // 따옴표, 역슬래시, 0x20 미만은 늘 escape
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            '\u{8}' => out.push_str("\\b"),
            '\u{c}' => out.push_str("\\f"),
            c if c < ' ' => push_unit(out, u32::from(c)),

            // ensure_ascii 면 0x7f 이상도, 서로게이트 자리표는 그 코드 하나로
            c if ascii == EnsureAscii::No || c <= '~' => out.push(c),
            c => match unit_of(c) {
                Some(unit) => push_unit(out, unit),
                None => {
                    for unit in c.encode_utf16(&mut [0; 2]) {
                        push_unit(out, u32::from(*unit));
                    }
                }
            },
        }
    }
    out.push('"');
}

fn push_unit(out: &mut String, unit: u32) {
    use std::fmt::Write as _;
    let _ = write!(out, "\\u{unit:04x}");
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
