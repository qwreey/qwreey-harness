//! 상태 파일에서 읽은 수(python 의 int 또는 float). 사칙은 python 처럼 int 끼리는 int, 하나라도 float 면 float.

use harness_hook::py::value::Value;

use super::Abort;

/// python 수 하나.
#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Num {
    Int(i128),
    Float(f64),
}

impl Num {
    /// JSON 값을 수로. bool 은 python 처럼 0, 1 이다. 수가 아니면 python 의 TypeError 자리라 [`Abort`].
    pub fn of(v: &Value) -> Result<Num, Abort> {
        match v {
            Value::Bool(b) => Ok(Num::Int(i128::from(*b))),
            Value::Int(i) => Ok(Num::Int(*i)),
            Value::Float(f) => Ok(Num::Float(*f)),
            _ => Err(Abort),
        }
    }

    /// float 로(디스크 크기는 2^53 아래라 정확하다).
    pub fn as_f64(self) -> f64 {
        match self {
            Num::Int(i) => i as f64,
            Num::Float(f) => f,
        }
    }

    /// 상태 파일에 쓸 값.
    pub fn to_value(self) -> Value {
        match self {
            Num::Int(i) => Value::Int(i),
            Num::Float(f) => Value::Float(f),
        }
    }
}

/// python `a - b`.
impl std::ops::Sub for Num {
    type Output = Num;

    fn sub(self, other: Num) -> Num {
        match (self, other) {
            (Num::Int(a), Num::Int(b)) => a
                .checked_sub(b)
                .map_or(Num::Float(a as f64 - b as f64), Num::Int),
            _ => Num::Float(self.as_f64() - other.as_f64()),
        }
    }
}
