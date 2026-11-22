//! python 의 수(int, float) 셈과 글 꼴. 원장 값은 python 이 쓴 그대로 int 일 수도 float 일 수도 있고, 셈의 결과 꼴
//! (`3` 대 `3.0`, `sum()` 의 반올림)이 알림 글에 그대로 나온다.

use std::cmp::Ordering;

use harness_hook::py::num::{float_repr, format_g};
use harness_hook::py::value::Value;

use crate::stop::{Result, Stop};

/// python int 또는 float 하나. bool 은 int 로 읽는다(python 에서 `True + 1 == 2`).
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Num {
    Int(i128),
    Float(f64),
}

impl Num {
    /// JSON 값이 수면 그 수. i128 을 넘는 정수와 수가 아닌 값은 `None`.
    pub fn of(value: &Value) -> Option<Num> {
        match value {
            Value::Bool(b) => Some(Num::Int(i128::from(*b))),
            Value::Int(n) => Some(Num::Int(*n)),
            Value::Float(f) => Some(Num::Float(*f)),
            _ => None,
        }
    }

    /// 수여야 하는 값(python 셈의 피연산자). 아니면 TypeError 자리라 [`Stop::Raises`].
    pub fn need(value: &Value) -> Result<Num> {
        match value {
            Value::BigInt(_) => Err(Stop::Unported("an integer past i128")),
            other => {
                Num::of(other).ok_or(Stop::Raises("arithmetic on a value that is not a number"))
            }
        }
    }

    /// JSON 값으로.
    pub fn value(self) -> Value {
        match self {
            Num::Int(n) => Value::Int(n),
            Num::Float(f) => Value::Float(f),
        }
    }

    /// float 로(python `float(n)`).
    pub fn f64(self) -> f64 {
        match self {
            Num::Int(n) => n as f64,
            Num::Float(f) => f,
        }
    }

    /// python `a + b`.
    pub fn plus(self, other: Num) -> Result<Num> {
        match (self, other) {
            (Num::Int(a), Num::Int(b)) => a.checked_add(b).map(Num::Int).ok_or(BIG),
            (a, b) => Ok(Num::Float(a.f64() + b.f64())),
        }
    }

    /// python `a - b`.
    pub fn minus(self, other: Num) -> Result<Num> {
        match (self, other) {
            (Num::Int(a), Num::Int(b)) => a.checked_sub(b).map(Num::Int).ok_or(BIG),
            (a, b) => Ok(Num::Float(a.f64() - b.f64())),
        }
    }

    /// python `a * b`.
    pub fn times(self, other: Num) -> Result<Num> {
        match (self, other) {
            (Num::Int(a), Num::Int(b)) => a.checked_mul(b).map(Num::Int).ok_or(BIG),
            (a, b) => Ok(Num::Float(a.f64() * b.f64())),
        }
    }

    /// python 의 비교. int 와 float 는 값 그대로 견주고, NaN 이 끼면 `None`(모든 비교가 거짓).
    pub fn compare(self, other: Num) -> Option<Ordering> {
        match (self, other) {
            (Num::Int(a), Num::Int(b)) => Some(a.cmp(&b)),
            (Num::Float(a), Num::Float(b)) => a.partial_cmp(&b),
            (Num::Int(a), Num::Float(b)) => int_float(a, b),
            (Num::Float(a), Num::Int(b)) => int_float(b, a).map(Ordering::reverse),
        }
    }

    /// python `a >= b`.
    pub fn ge(self, other: Num) -> bool {
        matches!(
            self.compare(other),
            Some(Ordering::Greater | Ordering::Equal)
        )
    }

    /// python `a > b`.
    pub fn gt(self, other: Num) -> bool {
        self.compare(other) == Some(Ordering::Greater)
    }

    /// python `a < b`.
    pub fn lt(self, other: Num) -> bool {
        self.compare(other) == Some(Ordering::Less)
    }

    /// python `str(n)`.
    pub fn text(self) -> String {
        match self {
            Num::Int(n) => n.to_string(),
            Num::Float(f) => float_repr(f),
        }
    }

    /// python `f"{n:g}"`(int 도 float 로 바꿔 쓴다).
    pub fn g(self) -> String {
        format_g(self.f64())
    }

    /// python `f"{n:.Nf}"`.
    pub fn fixed(self, digits: usize) -> String {
        let x = self.f64();
        if x.is_nan() {
            return "nan".to_owned();
        }
        if x.is_infinite() {
            return if x > 0.0 { "inf" } else { "-inf" }.to_owned();
        }
        format!("{x:.digits$}")
    }

    /// python `round(n, digits)`: int 는 그대로, float 는 십진 `digits` 자리로 올바르게 반올림한 float.
    pub fn round(self, digits: usize) -> Num {
        match self {
            Num::Int(_) => self,
            Num::Float(f) if !f.is_finite() => self,
            Num::Float(f) => Num::Float(format!("{f:.digits$}").parse().unwrap_or(f)),
        }
    }
}

/// python `max(a, b)`: 처음의 가장 큰 값(같으면 앞의 것, NaN 과 견주면 앞의 것).
pub fn py_max(a: Num, b: Num) -> Num {
    if b.gt(a) { b } else { a }
}

/// python `min(a, b)`: 처음의 가장 작은 값.
pub fn py_min(a: Num, b: Num) -> Num {
    if b.lt(a) { b } else { a }
}

const BIG: Stop = Stop::Unported("an integer past i128");

// int 와 float 의 정확한 비교(python long_richcompare 의 float 갈래)
fn int_float(a: i128, b: f64) -> Option<Ordering> {
    // NaN, infinities and floats past i128
    if b.is_nan() {
        return None;
    }
    if b.is_infinite() {
        return Some(if b > 0.0 {
            Ordering::Less
        } else {
            Ordering::Greater
        });
    }
    let whole = b.trunc();
    if whole.abs() >= 1.7e38 {
        return Some(if whole > 0.0 {
            Ordering::Less
        } else {
            Ordering::Greater
        });
    }

    // Whole part, then the fraction
    let by_whole = a.cmp(&(whole as i128));
    if by_whole != Ordering::Equal {
        return Some(by_whole);
    }
    0.0.partial_cmp(&(b - whole))
}

/// python 3.12+ `sum(values)`(시작 0): int 는 정확히 더하고, float 가 나오면 Neumaier 보정 합으로 바꾼다.
///
/// CPython `builtin_sum_impl` 을 따른다: float 갈래에서 int 는 보정 없이 더하고, 끝에 보정 값이 유한하면 더한다.
pub fn py_sum(values: impl IntoIterator<Item = Num>) -> Result<Num> {
    let mut values = values.into_iter();

    // Exact int phase until the first float
    let mut total: i128 = 0;
    let first_float = loop {
        match values.next() {
            None => return Ok(Num::Int(total)),
            Some(Num::Int(n)) => total = total.checked_add(n).ok_or(BIG)?,
            Some(Num::Float(x)) => break total as f64 + x,
        }
    };

    // Compensated float phase
    let mut sum = first_float;
    let mut compensation = 0.0;
    for value in values {
        // Neumaier for floats; ints are added without compensation
        match value {
            Num::Float(x) => {
                let t = sum + x;
                compensation += if sum.abs() >= x.abs() {
                    (sum - t) + x
                } else {
                    (x - t) + sum
                };
                sum = t;
            }
            Num::Int(n) if i64::try_from(n).is_ok() => sum += n as f64,
            Num::Int(_) => return Err(BIG),
        }
    }

    // A finite compensation is added at the end
    if compensation != 0.0 && compensation.is_finite() {
        sum += compensation;
    }
    Ok(Num::Float(sum))
}

#[cfg(test)]
mod tests {
    use super::*;

    /// int 끼리는 int, 하나라도 float 면 float, 꼴이 글에 그대로 나온다.
    #[test]
    fn arithmetic_keeps_python_types() {
        assert_eq!(Num::Int(3).minus(Num::Int(1)).unwrap().text(), "2");
        assert_eq!(Num::Int(3).minus(Num::Float(1.0)).unwrap().text(), "2.0");
        assert_eq!(Num::Int(2).times(Num::Float(2.0)).unwrap().g(), "4");
        assert_eq!(Num::Float(0.125).fixed(2), "0.12");
        assert_eq!(Num::Float(f64::NAN).fixed(2), "nan");
        assert_eq!(Num::Float(0.12345).round(4), Num::Float(0.1235));
        assert_eq!(Num::Int(0).round(4), Num::Int(0));
    }

    /// int 와 float 는 값 그대로 견준다(2^53 너머에서도).
    #[test]
    fn compares_exactly() {
        let big = (1i128 << 60) + 1;
        assert!(Num::Int(big).gt(Num::Float((1u64 << 60) as f64)));
        assert!(Num::Int(1).lt(Num::Float(1.5)));
        assert!(!Num::Float(f64::NAN).ge(Num::Int(0)));
        assert_eq!(py_max(Num::Float(0.0), Num::Int(0)), Num::Float(0.0));
        assert_eq!(py_min(Num::Int(5), Num::Float(2.0)), Num::Float(2.0));
    }

    /// sum 은 int 는 정확히, float 는 보정 합이다(python 3.12+ 에서 0.1 열 개는 1.0).
    #[test]
    fn sums_like_python() {
        assert_eq!(py_sum([]).unwrap(), Num::Int(0));
        assert_eq!(py_sum([Num::Int(2), Num::Int(3)]).unwrap(), Num::Int(5));
        assert_eq!(py_sum([Num::Float(0.1); 10]).unwrap(), Num::Float(1.0));
        let naive: f64 = [0.1f64; 10].iter().sum();
        assert_ne!(naive, 1.0);
    }
}
