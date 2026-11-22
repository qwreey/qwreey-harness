//! 상태 파일과 훅 입력의 JSON 값에 python 이 하는 일: `iter()`, `==`, 시각, 파일 쓰기.

use std::time::{SystemTime, UNIX_EPOCH};

use harness_hook::py::fs::os_path;
use harness_hook::py::surrogate::unit_of;
use harness_hook::py::value::Value;

use crate::num::Num;
use crate::stop::{Result, Stop};

/// python `iter(value)` 의 값들: 목록은 원소, 글은 글자, dict 는 키. 그 밖은 TypeError.
pub fn iterate(value: &Value) -> Result<Vec<Value>> {
    match value {
        Value::List(items) => Ok(items.clone()),
        Value::Str(s) => Ok(s.chars().map(|c| Value::Str(c.to_string())).collect()),
        Value::Dict(d) => Ok(d.iter().map(|(k, _)| Value::Str(k.to_owned())).collect()),
        _ => Err(Stop::Raises("iterating a value that is not iterable")),
    }
}

/// python `a == b`. 수는 값으로(1 == 1.0 == True), 목록과 dict 는 원소마다 견준다.
pub fn py_eq(a: &Value, b: &Value) -> bool {
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
        _ => match (Num::of(a), Num::of(b)) {
            (Some(x), Some(y)) => x.compare(y) == Some(std::cmp::Ordering::Equal),
            _ => false,
        },
    }
}

/// python `time.time()`: 지금 시각의 ns 를 float 로 나눈 초(CPython `_PyTime_AsSecondsDouble`).
pub fn now() -> f64 {
    let ns = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_or(0, |d| d.as_nanos() as i64);
    if ns % 1_000_000_000 == 0 {
        (ns / 1_000_000_000) as f64
    } else {
        ns as f64 / 1e9
    }
}

/// 글에 짝 없는 서로게이트(자리표)가 있나. python 이 `encoding="utf-8"` 로 연 파일에 쓰다 UnicodeEncodeError 를 내는 글이다.
pub fn has_surrogate(text: &str) -> bool {
    text.chars().any(|c| unit_of(c).is_some())
}

/// `text` 를 `<path>.<pid>.tmp` 에 쓴 뒤 `path` 로 바꿔 넣는다(python `open(tmp, "w")`, `os.replace`). 폴더를 만든다.
///
/// `tmp` 를 주면 그 이름을 쓴다(python 원장은 `<path>.tmp`).
pub fn replace_file(path: &str, tmp: Option<&str>, text: &str) -> Result<()> {
    let fail = |_| Stop::Raises("cannot write the state file");
    let target = os_path(path).ok_or(Stop::Raises("bad state path"))?;
    if let Some(dir) = target.parent() {
        std::fs::create_dir_all(dir).map_err(fail)?;
    }

    let tmp = match tmp {
        Some(name) => name.to_owned(),
        None => format!("{path}.{}.tmp", std::process::id()),
    };
    let tmp = os_path(&tmp).ok_or(Stop::Raises("bad state path"))?;
    std::fs::write(&tmp, text).map_err(fail)?;
    std::fs::rename(tmp, target).map_err(fail)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 수는 꼴이 달라도 값이 같으면 같고, 글과 수는 다르다.
    #[test]
    fn equality_like_python() {
        assert!(py_eq(&Value::Int(1), &Value::Float(1.0)));
        assert!(py_eq(&Value::Bool(true), &Value::Int(1)));
        assert!(!py_eq(&Value::Str("1".into()), &Value::Int(1)));
        let a = Value::List(vec![Value::Int(3), Value::Float(2.5)]);
        let b = Value::List(vec![Value::Float(3.0), Value::Float(2.5)]);
        assert!(py_eq(&a, &b));
    }

    /// 글은 글자마다, dict 는 키마다 돈다.
    #[test]
    fn iterates_like_python() {
        let chars = iterate(&Value::Str("ab".into())).unwrap();
        assert_eq!(chars, [Value::Str("a".into()), Value::Str("b".into())]);
        assert!(iterate(&Value::Int(1)).is_err());
    }
}
