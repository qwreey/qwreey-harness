//! 줄 기준(warn, hard, grow, flat)과 성장 기준점의 수: python int 와 float 의 셈, 비교, 글로 쓰기.
//!
//! 기준은 저장소 structure.json 에서 와서 float(`800.0`)나 bool 일 수도 있다. python 은 int 와 float 를 정확히 비교하고
//! 알림 글에 `repr` 꼴(`1600.0`)로 쓴다. 글이나 목록인 기준은 곱하기는 되고(되풀이) 비교에서 TypeError 다.

use std::cmp::Ordering;

use harness_hook::py::num::float_repr;
use harness_hook::py::value::Value;

use crate::halt::{Halt, Result};

/// python 수 하나.
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Num {
    Int(i128),
    Float(f64),
}

impl Num {
    /// python 수(int, float, bool)면 그 값, 수가 아니면 `None`. i128 밖의 정수는 옮기지 않았다.
    pub fn of(value: &Value) -> Result<Option<Num>> {
        Ok(match value {
            Value::Int(i) => Some(Num::Int(*i)),
            Value::Bool(b) => Some(Num::Int(i128::from(*b))),
            Value::Float(f) => Some(Num::Float(*f)),
            Value::BigInt(_) => return Err(Halt::Unported("a limit beyond i128")),
            _ => None,
        })
    }

    /// python `a - b`.
    pub fn sub(self, other: Num) -> Result<Num> {
        Ok(match (self, other) {
            (Num::Int(a), Num::Int(b)) => {
                Num::Int(a.checked_sub(b).ok_or(Halt::Unported("an i128 overflow"))?)
            }
            (a, b) => Num::Float(a.as_f64() - b.as_f64()),
        })
    }

    /// python `a * k`.
    pub fn times(self, k: i128) -> Result<Num> {
        Ok(match self {
            Num::Int(a) => Num::Int(a.checked_mul(k).ok_or(Halt::Unported("an i128 overflow"))?),
            Num::Float(f) => Num::Float(f * k as f64),
        })
    }

    /// python `a >= b`(int 와 float 는 정확히 비교한다, NaN 은 늘 거짓).
    pub fn at_least(self, other: Num) -> bool {
        matches!(
            compare(self, other),
            Some(Ordering::Greater | Ordering::Equal)
        )
    }

    /// python `str(x)`: int 는 숫자, float 는 `repr`.
    pub fn text(self) -> String {
        match self {
            Num::Int(i) => i.to_string(),
            Num::Float(f) => float_repr(f),
        }
    }

    fn as_f64(self) -> f64 {
        match self {
            Num::Int(i) => i as f64,
            Num::Float(f) => f,
        }
    }
}

fn compare(a: Num, b: Num) -> Option<Ordering> {
    match (a, b) {
        (Num::Int(x), Num::Int(y)) => Some(x.cmp(&y)),
        (Num::Float(x), Num::Float(y)) => x.partial_cmp(&y),
        (Num::Int(x), Num::Float(y)) => int_float(x, y),
        (Num::Float(x), Num::Int(y)) => int_float(y, x).map(Ordering::reverse),
    }
}

// python 의 int 와 float 비교: float 로 바꾸지 않고 정수 부분과 소수 부분으로 견준다
fn int_float(i: i128, f: f64) -> Option<Ordering> {
    if f.is_nan() {
        return None;
    }

    // Outside the i128 range the sign decides
    let whole = f.trunc();
    if whole >= 2f64.powi(127) {
        return Some(Ordering::Less);
    }
    if whole < -(2f64.powi(127)) {
        return Some(Ordering::Greater);
    }

    // Integral parts first, then the fraction
    match i.cmp(&(whole as i128)) {
        Ordering::Equal if f > whole => Some(Ordering::Less),
        Ordering::Equal if f < whole => Some(Ordering::Greater),
        other => Some(other),
    }
}

/// 줄 기준 하나(python `spec.get(x, cfg[x]) * k`).
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Limit {
    Num(Num),
    /// 글이나 목록: python 은 곱하기는 하고 비교에서 TypeError 로 끝난다.
    NotNum,
}

impl Limit {
    /// python `value * k` 의 결과. None 과 dict 는 곱하기에서 TypeError 다.
    pub fn of(value: &Value, k: i128) -> Result<Limit> {
        match value {
            Value::Str(_) | Value::List(_) => Ok(Limit::NotNum),
            Value::Null | Value::Dict(_) => Err(Halt::PyError("a limit that cannot be multiplied")),
            other => match Num::of(other)? {
                Some(n) => Ok(Limit::Num(n.times(k)?)),
                None => Err(Halt::PyError("a limit that cannot be multiplied")),
            },
        }
    }

    /// python `n >= limit`.
    pub fn reached_by(self, n: Num) -> Result<bool> {
        match self {
            Limit::Num(limit) => Ok(n.at_least(limit)),
            Limit::NotNum => Err(Halt::PyError("comparing a line count with a non-number")),
        }
    }

    /// python `str(limit)`(비교를 지난 기준만 글에 쓰인다).
    pub fn text(self) -> String {
        match self {
            Limit::Num(n) => n.text(),
            Limit::NotNum => String::new(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// int 와 float 의 비교와 셈이 python 과 같다.
    #[test]
    fn compares_like_python() {
        // An int equal to a float's whole part is below it when the float has a fraction
        assert!(!Num::Int(800).at_least(Num::Float(800.5)));
        assert!(Num::Int(801).at_least(Num::Float(800.5)));
        assert!(Num::Int(800).at_least(Num::Float(800.0)));
        assert!(
            !Num::Int(800).at_least(Num::Float(f64::NAN)),
            "NaN never compares"
        );
        assert!(Num::Int(i128::MAX).at_least(Num::Float(-1e300)));

        // Floats print with repr, bools count as ints
        assert_eq!(Num::Int(3).sub(Num::Float(1.0)).unwrap().text(), "2.0");
        let doubled = Limit::of(&Value::Bool(true), 2).unwrap();
        assert_eq!(doubled, Limit::Num(Num::Int(2)));
    }

    /// 수가 아닌 기준은 python 이 예외를 내는 자리에서 끝난다.
    #[test]
    fn non_numbers_fail_where_python_raises() {
        // A string limit multiplies but cannot be compared
        let text = Limit::of(&Value::Str("8".into()), 2).unwrap();
        assert!(text.reached_by(Num::Int(1)).is_err());

        // None cannot be multiplied at all
        assert!(Limit::of(&Value::Null, 1).is_err());
    }
}
