//! 이 훅이 쓰는 python 동작 가운데 `harness_hook::py` 에 없는 것: 값 비교(`==`), 글 비교, `json.loads(bytes)`, `round(x, 3)`,
//! 파일 읽기, 세션 id 정리. qwreey-advisor crate 에도 비슷한 조각이 있다(둘 다 쓰면 `harness_hook::py` 로 옮길 후보).

use std::cmp::Ordering;
use std::path::PathBuf;

use harness_hook::py::json_load::{self, Decode};
use harness_hook::py::surrogate::{placeholder, to_os, unit_of};
use harness_hook::py::unicode::is_word;
use harness_hook::py::value::{Dict, Value};

/// python 이 예외를 내는 곳. 바깥 `except Exception` 이 잡아 아무것도 내지 않고 끝난다.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Abort(pub &'static str);

/// [`Abort`] 로 끝날 수 있는 결과.
pub type Result<T> = std::result::Result<T, Abort>;

/// python 이 OS 에 넘기는 경로. NUL 이나 바이트로 바꿀 수 없는 서로게이트가 있으면 `None`(python ValueError).
pub fn os_path(path: &str) -> Option<PathBuf> {
    if path.contains('\0') {
        return None;
    }
    to_os(path)
}

/// python `open(path, "rb").read()`. 실패는 `None`(OSError 든 ValueError 든 부르는 곳이 같게 잡는다).
pub fn read_bytes(path: &str) -> Option<Vec<u8>> {
    std::fs::read(os_path(path)?).ok()
}

/// `json.load(open(path))` 의 객체(엄격한 UTF-8). 객체가 아니면 `Err(Some(값))`, 읽지 못하면 `Err(None)`.
pub fn parse_object(bytes: &[u8]) -> std::result::Result<Dict, Option<Value>> {
    match json_load::from_bytes(bytes, Decode::Strict) {
        Ok(value) => value.into_dict().map_err(Some),
        Err(_) => Err(None),
    }
}

/// python `json.loads(raw)` 에 bytes 를 줄 때: UTF-8 BOM 을 떼고 `surrogatepass` 로 푼다(UTF-8 로 쓴 서로게이트를 받는다).
///
/// python 은 앞 네 바이트의 NUL 꼴로 UTF-16, UTF-32 도 알아본다. transcript 줄에는 NUL 이 없어 그 꼴은 읽지 못한 줄로 본다.
pub fn loads_bytes(raw: &[u8]) -> Option<Value> {
    if raw.iter().take(4).any(|&b| b == 0)
        || raw.starts_with(&[0xff, 0xfe])
        || raw.starts_with(&[0xfe, 0xff])
    {
        return None;
    }
    let raw = raw.strip_prefix(&[0xef, 0xbb, 0xbf]).unwrap_or(raw);
    let text = decode_surrogatepass(raw)?;
    json_load::loads(&text).ok()
}

// UTF-8 에 ED A0..BF xx(서로게이트를 UTF-8 꼴로 쓴 것)를 서로게이트 자리표로 받는다. 그 밖의 틀린 바이트는 None
fn decode_surrogatepass(mut bytes: &[u8]) -> Option<String> {
    let mut out = String::with_capacity(bytes.len());
    loop {
        match std::str::from_utf8(bytes) {
            Ok(text) => {
                out.push_str(text);
                return Some(out);
            }
            Err(e) => {
                let (valid, rest) = bytes.split_at(e.valid_up_to());
                out.push_str(std::str::from_utf8(valid).ok()?);
                let [0xed, b1 @ 0xa0..=0xbf, b2 @ 0x80..=0xbf, ..] = *rest else {
                    return None;
                };
                let unit = 0xd000 | (u32::from(b1 & 0x3f) << 6) | u32::from(b2 & 0x3f);
                out.push(placeholder(unit)?);
                bytes = &rest[3..];
            }
        }
    }
}

/// python 의 str 비교: 코드 포인트 순서. 자리표는 제 서로게이트 코드 자리에 놓는다.
pub fn py_cmp(a: &str, b: &str) -> Ordering {
    let code = |c: char| unit_of(c).unwrap_or(u32::from(c));
    a.chars().map(code).cmp(b.chars().map(code))
}

/// python `a == b`(JSON 값): 수는 int, float, bool 을 가리지 않고 값으로, dict 는 키 순서 없이.
pub fn py_eq(a: &Value, b: &Value) -> bool {
    if let (Some(x), Some(y)) = (number(a), number(b)) {
        return x == y;
    }
    match (a, b) {
        (Value::Null, Value::Null) => true,
        (Value::Str(x), Value::Str(y)) => x == y,
        (Value::BigInt(x), Value::BigInt(y)) => x == y,
        (Value::List(x), Value::List(y)) => {
            x.len() == y.len() && x.iter().zip(y).all(|(p, q)| py_eq(p, q))
        }
        (Value::Dict(x), Value::Dict(y)) => {
            x.len() == y.len() && x.iter().all(|(k, v)| y.get(k).is_some_and(|w| py_eq(v, w)))
        }
        _ => false,
    }
}

/// 수 값(python 산술의 int, float, bool). i128 밖의 정수는 비교에 쓰지 않는다.
pub fn number(value: &Value) -> Option<Num> {
    match value {
        Value::Int(n) => Some(Num::Int(*n)),
        Value::Bool(b) => Some(Num::Int(i128::from(*b))),
        Value::Float(f) => Some(Num::Float(*f)),
        _ => None,
    }
}

/// python 의 int 또는 float.
#[derive(Clone, Copy, Debug)]
pub enum Num {
    Int(i128),
    Float(f64),
}

impl Num {
    /// python `a + b`. int 끼리 넘치면(python 만 셀 수 있는 수) `None`.
    pub fn checked_add(self, other: Num) -> Option<Num> {
        match (self, other) {
            (Num::Int(a), Num::Int(b)) => a.checked_add(b).map(Num::Int),
            (a, b) => Some(Num::Float(a.as_f64() + b.as_f64())),
        }
    }

    /// python `a - b`.
    pub fn checked_sub(self, other: Num) -> Option<Num> {
        match (self, other) {
            (Num::Int(a), Num::Int(b)) => a.checked_sub(b).map(Num::Int),
            (a, b) => Some(Num::Float(a.as_f64() - b.as_f64())),
        }
    }

    fn as_f64(self) -> f64 {
        match self {
            Num::Int(n) => n as f64,
            Num::Float(f) => f,
        }
    }

    /// python 의 int, float 비교(`a < b` 등). NaN 은 어느 쪽과도 같지 않다.
    pub fn partial_cmp(self, other: Num) -> Option<Ordering> {
        match (self, other) {
            (Num::Int(a), Num::Int(b)) => Some(a.cmp(&b)),
            (a, b) => a.as_f64().partial_cmp(&b.as_f64()),
        }
    }

    /// JSON 에 쓸 값.
    pub fn value(self) -> Value {
        match self {
            Num::Int(n) => Value::Int(n),
            Num::Float(f) => Value::Float(f),
        }
    }
}

impl PartialEq for Num {
    fn eq(&self, other: &Num) -> bool {
        self.partial_cmp(*other) == Some(Ordering::Equal)
    }
}

/// python `round(x, 3)`: 정확한 십진 값에서 셋째 자리로(정확히 가운데면 짝수 쪽).
pub fn round3(x: f64) -> f64 {
    if !x.is_finite() {
        return x;
    }
    format!("{x:.3}").parse().unwrap_or(x)
}

/// python `re.sub(r"[^\w-]", "", str(v or "nosession"))`. `text` 는 `str()` 한 글이다(빈 글이면 nosession).
pub fn sanitize(text: &str) -> String {
    let text = if text.is_empty() { "nosession" } else { text };
    text.chars()
        .filter(|&c| c == '-' || is_word(u32::from(c)))
        .collect()
}

/// python `s[:n]`: 앞 `n` 글자.
pub fn take_chars(s: &str, n: usize) -> &str {
    match s.char_indices().nth(n) {
        Some((at, _)) => &s[..at],
        None => s,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// round(x, 3) 는 정확한 값에서 반올림한다: 2 진으로 정확한 가운데 값(0.0625)은 짝수 쪽이다.
    #[test]
    fn round3_like_python() {
        assert_eq!(round3(0.0625), 0.062, "an exact tie rounds to even");
        assert_eq!(round3(2.0 / 3.0), 0.667);
        assert_eq!(
            round3(0.0015),
            0.002,
            "0.0015 is just above the tie in binary"
        );
        assert_eq!(round3(0.9995), 1.0);
    }

    /// python == : 1 == 1.0 == True, dict 는 순서 없이, NaN 은 다르다.
    #[test]
    fn py_eq_like_python() {
        let v = |s: &str| json_load::loads(s).expect("json");
        assert!(py_eq(&v("1"), &v("1.0")));
        assert!(py_eq(&v("true"), &v("1")));
        assert!(py_eq(
            &v(r#"{"a": 1, "b": [2]}"#),
            &v(r#"{"b": [2.0], "a": true}"#)
        ));
        assert!(!py_eq(&v("NaN"), &v("NaN")));
        assert!(!py_eq(&v(r#""1""#), &v("1")));
    }

    /// bytes 의 json.loads: BOM 을 떼고, UTF-8 로 쓴 서로게이트를 받고, 틀린 바이트는 오류.
    #[test]
    fn loads_bytes_surrogatepass() {
        assert!(loads_bytes(b"\xef\xbb\xbf{\"a\": 1}").is_some());
        let decoded = loads_bytes(b"\"\xed\xb2\x80\"").expect("encoded surrogate decodes");
        let first = decoded.as_str().and_then(|s| s.chars().next());
        assert_eq!(first.and_then(unit_of), Some(0xdc80));
        assert!(loads_bytes(b"\"\xff\"").is_none());
    }
}
