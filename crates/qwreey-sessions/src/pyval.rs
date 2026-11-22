//! python 값의 `str()`, 수 비교와 덧셈. 훅 입력과 상태 파일([`Value`])을 python 처럼 읽는다.
//!
//! 상태 파일은 이 훅과 워커(python)가 쓰므로 정상이면 꼴이 정해져 있다. 꼴이 어긋난 값에서 python 이 TypeError 를 내는
//! 자리는 [`Abort`] 다. python 은 받지만 여기서 옮기지 않은 드문 꼴(목록의 `str()` 등)도 [`Abort`] 로 끝낸다.

use std::cmp::Ordering;

use harness_hook::py::num::float_repr;
use harness_hook::py::value::Value;

use crate::abort::{Abort, Result};

/// `data.get(key) or <다음>` 의 참인 값을 `str()` 로. 거짓이면 `Ok(None)`, 참인 목록이나 객체는 [`Abort`].
pub fn truthy_str(v: Option<&Value>, what: &'static str) -> Result<Option<String>> {
    match v.filter(|v| v.truthy()) {
        None => Ok(None),
        Some(v) => v.scalar_str().map(Some).ok_or(Abort(what)),
    }
}

/// python 의 int 또는 float(bool 은 int).
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Num {
    Int(i128),
    Float(f64),
}

impl Num {
    /// 상태 값이 수면 그것(bool 은 0, 1). i128 밖의 정수는 옮기지 않아 `None` 이다(python 에서는 수다).
    pub fn of(v: &Value) -> Option<Num> {
        match v {
            Value::Bool(b) => Some(Num::Int(i128::from(*b))),
            Value::Int(i) => Some(Num::Int(*i)),
            Value::Float(f) => Some(Num::Float(*f)),
            _ => None,
        }
    }

    /// 수가 아니면 python TypeError 자리.
    pub fn require(v: &Value, what: &'static str) -> Result<Num> {
        Num::of(v).ok_or(Abort(what))
    }

    /// f64 로(큰 int 는 python 처럼 반올림한다).
    pub fn as_f64(self) -> f64 {
        match self {
            Num::Int(i) => i as f64,
            Num::Float(f) => f,
        }
    }

    /// python `a + b`. int 끼리 넘치면(python 은 큰 int) [`Abort`].
    pub fn plus(self, other: Num) -> Result<Num> {
        match (self, other) {
            (Num::Int(a), Num::Int(b)) => {
                a.checked_add(b).map(Num::Int).ok_or(Abort("int overflow"))
            }
            (a, b) => Ok(Num::Float(a.as_f64() + b.as_f64())),
        }
    }

    /// python `f"{n}"`.
    pub fn text(self) -> String {
        match self {
            Num::Int(i) => i.to_string(),
            Num::Float(f) => float_repr(f),
        }
    }

    /// python 의 수 비교(int 와 float 도 값 그대로). NaN 이 끼면 `None`.
    pub fn compare(self, other: Num) -> Option<Ordering> {
        match (self, other) {
            (Num::Int(a), Num::Int(b)) => Some(a.cmp(&b)),
            (Num::Float(a), Num::Float(b)) => a.partial_cmp(&b),
            (Num::Int(a), Num::Float(b)) => int_float_cmp(a, b),
            (Num::Float(a), Num::Int(b)) => int_float_cmp(b, a).map(Ordering::reverse),
        }
    }
}

// int 와 float 를 반올림 없이 비교한다(python 과 같다)
fn int_float_cmp(i: i128, f: f64) -> Option<Ordering> {
    if f.is_nan() {
        return None;
    }

    // i128 밖의 float
    let floor = f.floor();
    if floor >= 2f64.powi(127) {
        return Some(Ordering::Less);
    }
    if floor < -(2f64.powi(127)) {
        return Some(Ordering::Greater);
    }

    // 정수 부분이 같으면 소수 부분이 있는 float 가 크다
    let whole = floor as i128;
    Some(match i.cmp(&whole) {
        Ordering::Equal if f > floor => Ordering::Less,
        other => other,
    })
}

/// python `a > b`: 수끼리, 글끼리. 다른 꼴의 짝은 python TypeError 자리라 [`Abort`].
pub fn greater(a: &Value, b: &Value, what: &'static str) -> Result<bool> {
    if let (Some(x), Some(y)) = (Num::of(a), Num::of(b)) {
        return Ok(x.compare(y) == Some(Ordering::Greater));
    }
    match (a, b) {
        (Value::Str(x), Value::Str(y)) => Ok(x > y),
        _ => Err(Abort(what)),
    }
}

/// dict 의 `d.get(key, default)`. dict 가 아니면 python AttributeError 자리라 [`Abort`].
pub fn get<'a>(
    d: &'a Value,
    key: &str,
    default: &'a Value,
    what: &'static str,
) -> Result<&'a Value> {
    match d {
        Value::Dict(dict) => Ok(dict.get(key).unwrap_or(default)),
        _ => Err(Abort(what)),
    }
}

/// `Value::Int(0)`: `d.get(key, 0)` 의 기본값.
pub static ZERO: Value = Value::Int(0);

#[cfg(test)]
mod tests {
    use super::*;

    /// 정수와 실수는 python 처럼 값으로 비교하고, NaN 은 순서가 없다.
    #[test]
    fn numbers_compare_like_python() {
        assert_eq!(Num::Int(3).compare(Num::Float(3.0)), Some(Ordering::Equal));
        assert_eq!(Num::Int(3).compare(Num::Float(3.5)), Some(Ordering::Less));
        assert_eq!(
            Num::Float(-0.5).compare(Num::Int(-1)),
            Some(Ordering::Greater)
        );
        assert_eq!(
            Num::Int(i128::MAX).compare(Num::Float(1e300)),
            Some(Ordering::Less)
        );
        assert_eq!(Num::Int(1).compare(Num::Float(f64::NAN)), None);
    }

    /// `greater` 는 글끼리, bool 과 정수는 비교하고 글과 정수는 오류다.
    #[test]
    fn greater_compares_like_python() {
        assert!(greater(&Value::Str("b".into()), &Value::Str("a".into()), "t").unwrap());
        assert!(greater(&Value::Bool(true), &Value::Int(0), "t").unwrap());
        assert!(
            greater(&Value::Str("1".into()), &Value::Int(0), "t").is_err(),
            "python raises TypeError on str > int"
        );
    }

    /// 더한 합의 글은 정수끼리면 정수, 하나라도 실수면 실수 꼴이다.
    #[test]
    fn sums_print_like_python() {
        assert_eq!(Num::Int(1).plus(Num::Float(0.5)).unwrap().text(), "1.5");
        assert_eq!(Num::Int(4).plus(Num::Int(1)).unwrap().text(), "5");
    }

    /// 거짓 값은 없음, 참인 숫자는 python `str()` 글, 목록은 오류다.
    #[test]
    fn input_strings_follow_python_str() {
        assert_eq!(truthy_str(Some(&Value::Int(0)), "t"), Ok(None));
        assert_eq!(
            truthy_str(Some(&Value::Float(1.0)), "t"),
            Ok(Some("1.0".into()))
        );
        assert!(
            truthy_str(Some(&Value::List(vec![Value::Int(1)])), "t").is_err(),
            "a list is not a string input"
        );
    }
}
