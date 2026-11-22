//! python `json.loads` 와 같은 값을 주는 JSON 읽기. 훅 stdin(`json.load(sys.stdin)`)과 python 이 쓴 상태 파일을 읽는다.
//!
//! why not serde_json: python 과 받는 입력과 값이 다르다. serde_json 은 128 단계보다 깊은 중첩, `NaN`, `Infinity`,
//! 짝 없는 서로게이트 escape(`"\ud800"`), UTF-8 이 아닌 바이트를 거절하고, u64 를 넘는 정수를 float 로 읽는다
//! (arbitrary_precision 기능을 켜도 NaN 은 담지 못하고, 워크스페이스 전체의 `serde_json::Number` 가 바뀐다).
//! 깊은 MCP `tool_response` 하나로 Rust 훅만 입력 전체를 버리게 된다.
//!
//! python 과 같게 맞춘 것:
//! - 공백은 ` \t\n\r` 만, 앞뒤에 둘 수 있다. 글 맨 앞 BOM 은 오류다.
//! - `NaN`, `Infinity`, `-Infinity` 를 받는다. 수는 `-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][-+]?[0-9]+)?` 이고, 소수부나 지수가
//!   있으면 float(가장 가까운 값, 넘치면 무한대), 없으면 정수다. 정수는 크기 제한이 없되 숫자 4300 자를 넘으면 python 처럼
//!   오류다(`int` 의 자릿수 한도, `-X int_max_str_digits` 기본값).
//! - 글 안의 0x20 미만 글자는 오류(strict). escape 는 `\" \\ \/ \b \f \n \r \t \uXXXX` 이고, 짝 없는 서로게이트는
//!   [`super::surrogate`] 의 자리표다. 높은 서로게이트 escape 바로 뒤의 낮은 서로게이트 escape 만 한 글자로 합친다.
//! - 객체의 겹친 키는 처음 자리에 마지막 값이다.
//!
//! 중첩은 되부름 없이 읽는다. python 3.14 는 C 스택 크기로 멈춰(8 MiB 스택에서 약 52000 단계, 3.11 이하는 약 1000)
//! 정확히 같게 맞출 수 없다. 여기서는 [`MAX_DEPTH`] 를 넘으면 오류다(python 의 RecursionError 자리, 훅은 아무것도 내지 않는다).
//! 상태 파일에서는 갈래가 하나 더 있다: python 은 `except (OSError, ValueError)` 가 RecursionError 를 잡지 않아 훅이 예외로
//! 끝나고, Rust 는 읽지 못한 파일(`{}`)로 본다. 두 판이 다른 것은 5만 단계를 넘는 망가진 파일뿐이다.
//! 읽은 값의 drop 은 [`Value`] 의 Drop 이 되부름 없이 한다.

use std::fmt;

use super::surrogate::{decode_os, placeholder};
use super::value::{Dict, Value};

/// 이보다 깊은 중첩은 읽지 않는다.
pub const MAX_DEPTH: usize = 50_000;
/// python `int(text)` 가 받는 십진 숫자 수의 한도(`sys.int_info.default_max_str_digits`). 넘으면 python 은 ValueError 다.
pub const MAX_INT_DIGITS: usize = 4300;

/// 바이트를 글로 바꾸는 법.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Decode {
    /// `open(path, encoding="utf-8")`: UTF-8 이 아니면 오류(python UnicodeDecodeError, ValueError 의 하위).
    Strict,
    /// `python3 -X utf8` 의 stdin: UTF-8 이 아닌 바이트 하나는 U+DC80..U+DCFF 하나(surrogateescape).
    SurrogateEscape,
}

/// 읽지 못한 까닭과 자리(글의 바이트 위치).
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct JsonError {
    pub what: &'static str,
    pub offset: usize,
}

impl fmt::Display for JsonError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{} at byte {}", self.what, self.offset)
    }
}

impl std::error::Error for JsonError {}

/// [`MAX_DEPTH`] 를 넘은 중첩의 오류 글.
const TOO_DEEP: &str = "nested too deeply";

impl JsonError {
    /// 중첩이 [`MAX_DEPTH`] 를 넘어 멈췄나. python 은 이 자리에서 ValueError 가 아닌 RecursionError 를 낸다.
    pub fn too_deep(&self) -> bool {
        self.what == TOO_DEEP
    }
}

/// 바이트를 `decode` 로 글로 바꾼 뒤 [`loads`].
pub fn from_bytes(bytes: &[u8], decode: Decode) -> Result<Value, JsonError> {
    match decode {
        Decode::Strict => match std::str::from_utf8(bytes) {
            Ok(text) => loads(text),
            Err(e) => Err(JsonError {
                what: "not UTF-8",
                offset: e.valid_up_to(),
            }),
        },
        Decode::SurrogateEscape => loads(&decode_os(bytes)),
    }
}

/// python `json.loads(text)`.
pub fn loads(text: &str) -> Result<Value, JsonError> {
    let mut parser = Parser {
        text,
        bytes: text.as_bytes(),
        pos: 0,
    };
    parser.document()
}

/// 열린 배열이나 객체 하나.
enum Frame {
    List(Vec<Value>),
    /// 지금까지의 (키, 값)과 값을 기다리는 키.
    Dict(Vec<(String, Value)>, String),
}

struct Parser<'a> {
    text: &'a str,
    bytes: &'a [u8],
    pos: usize,
}

impl Parser<'_> {
    fn error<T>(&self, what: &'static str) -> Result<T, JsonError> {
        Err(JsonError {
            what,
            offset: self.pos,
        })
    }

    fn peek(&self) -> Option<u8> {
        self.bytes.get(self.pos).copied()
    }

    fn skip_ws(&mut self) {
        while matches!(self.peek(), Some(b' ' | b'\t' | b'\n' | b'\r')) {
            self.pos += 1;
        }
    }

    // 값 하나와 앞뒤 공백, 그 뒤로 남는 글이 없어야 한다
    fn document(&mut self) -> Result<Value, JsonError> {
        let mut stack: Vec<Frame> = Vec::new();
        let value = self.nested(&mut stack)?;
        self.skip_ws();
        if self.pos != self.bytes.len() {
            return self.error("extra data");
        }
        Ok(value)
    }

    // 맨 바깥 값을 읽는다. 열린 배열과 객체는 `stack` 에 두고 되부르지 않는다
    fn nested(&mut self, stack: &mut Vec<Frame>) -> Result<Value, JsonError> {
        loop {
            let Some(mut done) = self.value_start(stack)? else {
                continue;
            };

            // 끝난 값을 열린 단계에 넣는다. 단계가 닫히면 그것이 다시 끝난 값이다
            loop {
                if stack.is_empty() {
                    return Ok(done);
                }
                match self.attach(stack, done)? {
                    Some(closed) => done = closed,
                    None => break,
                }
            }
        }
    }

    // 값의 시작: 스칼라나 빈 배열, 빈 객체면 끝난 값, 여는 괄호면 새 단계를 열고 `None`
    fn value_start(&mut self, stack: &mut Vec<Frame>) -> Result<Option<Value>, JsonError> {
        self.skip_ws();
        if matches!(self.peek(), Some(b'[' | b'{')) && stack.len() >= MAX_DEPTH {
            return self.error(TOO_DEEP);
        }
        match self.peek() {
            Some(b'[') => {
                self.pos += 1;
                self.skip_ws();
                if self.peek() == Some(b']') {
                    self.pos += 1;
                    return Ok(Some(Value::List(Vec::new())));
                }
                stack.push(Frame::List(Vec::new()));
                Ok(None)
            }
            Some(b'{') => {
                self.pos += 1;
                self.skip_ws();
                if self.peek() == Some(b'}') {
                    self.pos += 1;
                    return Ok(Some(Value::Dict(Dict::new())));
                }
                let key = self.key()?;
                stack.push(Frame::Dict(Vec::new(), key));
                Ok(None)
            }
            _ => self.scalar().map(Some),
        }
    }

    // 끝난 값을 맨 위 단계에 넣고 뒤의 `,` 나 닫는 괄호를 읽는다. 닫혔으면 그 단계의 값, 다음 값이 오면 `None`
    fn attach(&mut self, stack: &mut Vec<Frame>, done: Value) -> Result<Option<Value>, JsonError> {
        let frame = stack.last_mut().expect("a frame is open");
        self.skip_ws();
        let close = match frame {
            Frame::List(items) => {
                items.push(done);
                b']'
            }
            Frame::Dict(pairs, key) => {
                pairs.push((std::mem::take(key), done));
                b'}'
            }
        };

        // 다음 값(객체면 그 키까지)
        if self.peek() == Some(b',') {
            self.pos += 1;
            if let Frame::Dict(_, key) = frame {
                self.skip_ws();
                *key = self.key()?;
            }
            return Ok(None);
        }

        // 닫기
        if self.peek() != Some(close) {
            return self.error("expecting ',' delimiter");
        }
        self.pos += 1;
        Ok(Some(match stack.pop().expect("a frame is open") {
            Frame::List(items) => Value::List(items),
            Frame::Dict(pairs, _) => Value::Dict(Dict::from_pairs(pairs)),
        }))
    }

    // 객체 키와 그 뒤의 `:`(앞 공백은 건너뛰었다)
    fn key(&mut self) -> Result<String, JsonError> {
        if self.peek() != Some(b'"') {
            return self.error("expecting property name enclosed in double quotes");
        }
        let key = self.string()?;
        self.skip_ws();
        if self.peek() != Some(b':') {
            return self.error("expecting ':' delimiter");
        }
        self.pos += 1;
        Ok(key)
    }

    fn scalar(&mut self) -> Result<Value, JsonError> {
        let rest = &self.bytes[self.pos..];
        let word = |w: &str| rest.starts_with(w.as_bytes());

        // 글과 수는 따로 읽고, 낱말은 길이만큼 건너뛴다
        let (value, len) = match self.peek() {
            Some(b'"') => return self.string().map(Value::Str),
            Some(b'-' | b'0'..=b'9') if !word("-Infinity") => return self.number(),
            Some(b'n') if word("null") => (Value::Null, 4),
            Some(b't') if word("true") => (Value::Bool(true), 4),
            Some(b'f') if word("false") => (Value::Bool(false), 5),
            Some(b'N') if word("NaN") => (Value::Float(f64::NAN), 3),
            Some(b'I') if word("Infinity") => (Value::Float(f64::INFINITY), 8),
            Some(b'-') if word("-Infinity") => (Value::Float(f64::NEG_INFINITY), 9),
            _ => return self.error("expecting value"),
        };
        self.pos += len;
        Ok(value)
    }

    // python NUMBER_RE. 소수부와 지수는 숫자가 하나 이상 따라올 때만 수의 일부다(아니면 뒤에 남아 오류가 된다)
    fn number(&mut self) -> Result<Value, JsonError> {
        let start = self.pos;
        let digits_from = |bytes: &[u8], at: usize| {
            bytes[at..]
                .iter()
                .take_while(|b| b.is_ascii_digit())
                .count()
        };

        // 정수부
        let mut end = start + usize::from(self.peek() == Some(b'-'));
        match self.bytes.get(end) {
            Some(b'0') => end += 1,
            Some(b'1'..=b'9') => end += digits_from(self.bytes, end),
            _ => return self.error("expecting value"),
        }
        let int_end = end;

        // 소수부, 지수
        if self.bytes.get(end) == Some(&b'.') && digits_from(self.bytes, end + 1) > 0 {
            end += 1 + digits_from(self.bytes, end + 1);
        }
        if matches!(self.bytes.get(end), Some(b'e' | b'E')) {
            let sign = usize::from(matches!(self.bytes.get(end + 1), Some(b'+' | b'-')));
            let exp = digits_from(self.bytes, end + 1 + sign);
            if exp > 0 {
                end += 1 + sign + exp;
            }
        }
        let text = &self.text[start..end];

        // float: Rust 의 읽기도 가장 가까운 값이고, 넘치면 무한대, 너무 작으면 0 이다(python float() 와 같다)
        if end != int_end {
            let value = text.parse::<f64>().map_err(|_| JsonError {
                what: "bad number",
                offset: start,
            })?;
            self.pos = end;
            return Ok(Value::Float(value));
        }

        // 정수: i128 밖이면 글 그대로(앞자리 0 이 없는 JSON 정수라 python str(int) 와 같다)
        if text.trim_start_matches('-').len() > MAX_INT_DIGITS {
            return self.error("integer has too many digits");
        }
        self.pos = end;
        Ok(match text.parse::<i128>() {
            Ok(i) => Value::Int(i),
            Err(_) => Value::BigInt(text.to_owned()),
        })
    }

    // 따옴표로 시작하는 글. 끝 따옴표 뒤로 간다
    fn string(&mut self) -> Result<String, JsonError> {
        self.pos += 1;
        let mut out = String::new();
        loop {
            // escape, 따옴표, 제어 문자가 아닌 조각은 그대로
            let run = self.bytes[self.pos..]
                .iter()
                .take_while(|&&b| b != b'"' && b != b'\\' && b >= 0x20)
                .count();
            out.push_str(&self.text[self.pos..self.pos + run]);
            self.pos += run;

            match self.peek() {
                Some(b'"') => {
                    self.pos += 1;
                    return Ok(out);
                }
                Some(b'\\') => self.escape(&mut out)?,
                Some(_) => return self.error("invalid control character"),
                None => return self.error("unterminated string"),
            }
        }
    }

    // `\` 로 시작하는 escape 하나
    fn escape(&mut self, out: &mut String) -> Result<(), JsonError> {
        // 한 글자 escape, `\u` 는 따로
        let simple = match self.bytes.get(self.pos + 1) {
            Some(b'"') => '"',
            Some(b'\\') => '\\',
            Some(b'/') => '/',
            Some(b'b') => '\u{8}',
            Some(b'f') => '\u{c}',
            Some(b'n') => '\n',
            Some(b'r') => '\r',
            Some(b't') => '\t',
            Some(b'u') => {
                out.push(self.unicode_escape()?);
                return Ok(());
            }
            _ => return self.error("invalid \\escape"),
        };

        out.push(simple);
        self.pos += 2;
        Ok(())
    }

    // `\uXXXX`, 높은 서로게이트 뒤에 낮은 서로게이트 escape 가 오면 둘을 한 글자로
    fn unicode_escape(&mut self) -> Result<char, JsonError> {
        let unit = self.hex4(self.pos + 2)?;
        self.pos += 6;
        if (0xD800..=0xDBFF).contains(&unit) && self.bytes[self.pos..].starts_with(b"\\u") {
            let low = self.hex4(self.pos + 2)?;
            if (0xDC00..=0xDFFF).contains(&low) {
                self.pos += 6;
                let code = 0x10000 + ((unit - 0xD800) << 10) + (low - 0xDC00);
                return Ok(char::from_u32(code).expect("a surrogate pair is a valid scalar"));
            }
        }
        Ok(char::from_u32(unit)
            .or_else(|| placeholder(unit))
            .expect("four hex digits are a scalar or a surrogate"))
    }

    // `at` 의 십진이 아닌 16진 숫자 넷(대소문자). python 처럼 `+` 등은 받지 않는다
    fn hex4(&self, at: usize) -> Result<u32, JsonError> {
        let Some(digits) = self.bytes.get(at..at + 4) else {
            return self.error("invalid \\uXXXX escape");
        };
        digits.iter().try_fold(0u32, |acc, &b| {
            let d = char::from(b).to_digit(16).ok_or(JsonError {
                what: "invalid \\uXXXX escape",
                offset: self.pos,
            })?;
            Ok(acc * 16 + d)
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::py::surrogate::unit_of;

    fn units(v: &Value) -> Vec<Option<u32>> {
        v.as_str().unwrap().chars().map(unit_of).collect()
    }

    /// python `json` 만 받는 `NaN`, `Infinity` 와 넘치거나 모자란 지수를 읽는다.
    #[test]
    fn reads_python_only_forms() {
        let v = loads(" [NaN, Infinity, -Infinity, -0, -0.0, 1E400, 1e-400, 1.5e3] ").unwrap();
        let Value::List(items) = &v else { panic!() };

        assert!(matches!(items[0], Value::Float(f) if f.is_nan()));
        assert_eq!(items[1], Value::Float(f64::INFINITY));
        assert_eq!(items[2], Value::Float(f64::NEG_INFINITY));
        assert_eq!(items[3], Value::Int(0), "-0 is an integer, so plain 0");
        assert!(matches!(items[4], Value::Float(f) if f == 0.0 && f.is_sign_negative()));
        assert_eq!(
            items[5],
            Value::Float(f64::INFINITY),
            "1E400 overflows to infinity"
        );
        assert_eq!(items[6], Value::Float(0.0), "1e-400 underflows to zero");
        assert_eq!(items[7], Value::Float(1500.0));
    }

    /// i128 에 들지 않는 정수는 자릿수 글 그대로 든다.
    #[test]
    fn big_integers_keep_their_digits() {
        let big = format!("-{}", "9".repeat(60));

        assert_eq!(loads(&big).unwrap(), Value::BigInt(big.clone()));
        assert_eq!(
            loads("170141183460469231731687303715884105728").unwrap(),
            Value::BigInt("170141183460469231731687303715884105728".into()),
            "i128::MAX plus one"
        );
    }

    /// 정수는 4300 자리까지만 받는다(python 의 정수 글자 수 한도).
    #[test]
    fn integers_over_4300_digits_are_rejected() {
        assert_eq!(
            loads(&"1".repeat(4300)).unwrap(),
            Value::BigInt("1".repeat(4300))
        );
        assert!(loads(&"1".repeat(4301)).is_err());
    }

    /// 끝 쉼표, BOM, 앞자리 0, 짝 안 맞는 escape 같은 python 이 거절하는 글은 거절한다.
    #[test]
    fn rejects_what_python_rejects() {
        for bad in [
            "",
            "[1,]",
            "{\"a\":1,}",
            "\u{feff}1",
            "[01]",
            "1.",
            "-",
            "\"\\u+123\"",
            "\"\\ud800\\u12\"",
            "\"\t\"",
            "nan",
            "-NaN",
            "{1: 2}",
            "[1 2]",
            "\"a",
            "{\"a\" 1}",
            "1 2",
        ] {
            assert!(loads(bad).is_err(), "{bad:?}");
        }
    }

    /// 서로게이트 escape 는 쌍이면 한 글자로 합치고, 짝 없는 것은 자리표로 남긴다.
    #[test]
    fn surrogate_escapes_follow_python_scanstring() {
        let v = loads(r#""\ud83d\ude00\ud800x\udc00\ud800\\u""#).unwrap();

        assert_eq!(
            units(&v),
            [
                None,
                Some(0xD800),
                None,
                Some(0xDC00),
                Some(0xD800),
                None,
                None
            ]
        );
    }

    /// 글자 escape(`\/`, `\b`, `\u00e9` ...)를 풀어 읽는다.
    #[test]
    fn simple_escapes_are_decoded() {
        assert_eq!(
            loads(r#""\/\b\f\n\r\t\"\u00e9\u007F""#).unwrap(),
            Value::Str("/\u{8}\u{c}\n\r\t\"\u{e9}\u{7f}".into())
        );
    }

    /// 엄격한 해석은 UTF-8 이 아닌 바이트를 거절한다.
    #[test]
    fn strict_decode_rejects_invalid_utf8() {
        let raw = b"{\"a\": \"x\xffy\"}";

        assert!(from_bytes(raw, Decode::Strict).is_err());
    }

    /// surrogateescape 해석은 글 안의 나쁜 바이트를 서로게이트 자리표로 남긴다.
    #[test]
    fn surrogateescape_keeps_invalid_bytes_inside_strings() {
        let raw = b"{\"a\": \"x\xffy\"}";

        let v = from_bytes(raw, Decode::SurrogateEscape).unwrap();

        let a = v.as_dict().unwrap().get("a").unwrap();
        assert_eq!(units(a), [None, Some(0xDCFF), None]);
    }

    /// surrogateescape 해석도 글 밖의 나쁜 바이트는 거절한다.
    #[test]
    fn surrogateescape_rejects_invalid_bytes_outside_strings() {
        assert!(from_bytes(b"[1, \xff]", Decode::SurrogateEscape).is_err());
    }

    /// 목록은 `MAX_DEPTH` 겹까지 읽고 한 겹 더 깊으면 거절한다(호출 스택 없이).
    #[test]
    fn list_depth_has_a_limit() {
        let ok = format!("{}{}", "[".repeat(MAX_DEPTH), "]".repeat(MAX_DEPTH));
        drop(loads(&ok).unwrap());

        let deep = format!("{}{}", "[".repeat(MAX_DEPTH + 1), "]".repeat(MAX_DEPTH + 1));
        assert!(loads(&deep).is_err());
    }

    /// 객체도 `MAX_DEPTH` 겹까지 읽는다.
    #[test]
    fn dict_depth_reaches_the_limit() {
        let dicts = format!("{}1{}", "{\"a\": ".repeat(MAX_DEPTH), "}".repeat(MAX_DEPTH));

        drop(loads(&dicts).unwrap());
    }

    /// 가장 깊은 값 뒤에 글이 남으면 거절한다.
    #[test]
    fn trailing_text_after_deepest_value_is_rejected() {
        let trailing = format!("{}{}x", "[".repeat(MAX_DEPTH), "]".repeat(MAX_DEPTH));

        assert!(loads(&trailing).is_err());
    }
}
