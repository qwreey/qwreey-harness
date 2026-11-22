//! 세션 상태 파일 `<임시 폴더>/claude-qwreey-operator/<sid>.json`: 이 턴의 쓰기 수(`n`), 쓴 파일(`files`), 알림 여부(`crossed`).
//!
//! python 판과 같은 파일을 번갈아 읽고 쓴다. 값은 python 이 쓴 그대로 [`Dict`] 로 들고, python 이 그 값으로 하는 셈
//! (`n + 1`, `set(files) | set(paths)`, `sorted`, `len`)을 옮긴다. 셈이 python 에서 예외로 끝나는 값이면 [`Stop::Raises`] 다.

use std::cmp::Ordering;

use harness_hook::epoch::sanitize;
use harness_hook::py::fs::{self, read_bytes};
use harness_hook::py::json::{EnsureAscii, dumps_dict};
use harness_hook::py::json_load::{self, Decode};
use harness_hook::py::path::{dirname, join};
use harness_hook::py::repr::truthy_str;
use harness_hook::py::surrogate::unit_of;
use harness_hook::py::value::{Dict, Value};

use crate::stop::{Result, Stop};

/// python `state_path(sid)`: `<임시 폴더>/claude-qwreey-operator/<sid 의 단어 글자와 ->.json`.
pub fn path(tempdir: &str, session_id: Option<&Value>) -> String {
    let dir = join(tempdir, "claude-qwreey-operator");
    join(&dir, &format!("{}.json", sanitize(&truthy_str(session_id))))
}

/// python `load(path)`: 읽은 dict, 읽지 못하거나 dict 가 아니면 빈 dict.
///
/// python 은 OSError 와 ValueError(JSON, UTF-8)만 잡는다. 너무 깊은 중첩(RecursionError)은 잡지 않아 훅이 아무것도 내지 않는다.
pub fn load(path: &str) -> Result<Dict> {
    let Ok(bytes) = read_bytes(path) else {
        return Ok(Dict::new());
    };
    match json_load::from_bytes(&bytes, Decode::Strict) {
        Ok(value) => Ok(value.into_dict().unwrap_or_default()),
        Err(e) if e.too_deep() => Err(Stop::Raises("RecursionError reading the state")),
        Err(_) => Ok(Dict::new()),
    }
}

/// python `save(path, st)`: `<path>.<pid>.tmp` 에 `json.dump` 한 뒤 바꿔 넣는다. 폴더를 만든다.
pub fn save(path: &str, state: &Dict) -> Result<()> {
    let fail = |_| Stop::Raises("cannot write the state file");
    let dir = fs::os_path(dirname(path)).ok_or(Stop::Raises("bad state path"))?;
    std::fs::create_dir_all(dir).map_err(fail)?;

    let tmp = format!("{path}.{}.tmp", std::process::id());
    let tmp_os = fs::os_path(&tmp).ok_or(Stop::Raises("bad state path"))?;
    let final_os = fs::os_path(path).ok_or(Stop::Raises("bad state path"))?;
    std::fs::write(&tmp_os, dumps_dict(state, EnsureAscii::Yes, None)).map_err(fail)?;
    std::fs::rename(tmp_os, final_os).map_err(fail)
}

/// python `st.get("n", 0) + 1`.
pub fn next_count(state: &Dict) -> Result<Value> {
    match state.get("n").unwrap_or(&Value::Int(0)) {
        Value::Int(n) => n
            .checked_add(1)
            .map(Value::Int)
            .ok_or(Stop::Unported("a count past i128")),
        Value::Bool(b) => Ok(Value::Int(i128::from(*b) + 1)),
        Value::Float(f) => Ok(Value::Float(f + 1.0)),
        Value::BigInt(_) => Err(Stop::Unported("a count past i128")),
        _ => Err(Stop::Raises("n + 1 on a value that is not a number")),
    }
}

/// python `count >= limit`(int 와 float 는 값으로 견준다, NaN 은 거짓).
pub fn reaches(count: &Value, limit: i128) -> bool {
    match count {
        Value::Int(n) => *n >= limit,
        Value::Float(f) => *f >= limit as f64,
        _ => false,
    }
}

/// python `len(value)`: 목록, 글(글자 수), dict 만. 그 밖은 TypeError.
pub fn py_len(value: &Value) -> Result<usize> {
    match value {
        Value::List(items) => Ok(items.len()),
        Value::Str(s) => Ok(s.chars().count()),
        Value::Dict(d) => Ok(d.len()),
        _ => Err(Stop::Raises("len() of a value without a length")),
    }
}

/// python `sorted(set(st.get("files", [])) | set(paths))`.
///
/// 앞 값은 목록, 글(글자마다), dict(키마다)를 받는다. 같은 값(1 과 1.0 과 True 도)은 먼저 나온 것 하나만 남는다.
/// 글과 수가 섞였거나 None 이 다른 값과 함께면 python `sorted` 가 TypeError 를 낸다.
pub fn merged_files(old: Option<&Value>, paths: &[Value]) -> Result<Vec<Value>> {
    let mut items = iterate(old.unwrap_or(&Value::List(Vec::new())))?;
    items.extend(paths.iter().cloned());

    // set(): hashable values, first of equal ones kept
    let mut unique: Vec<Value> = Vec::new();
    for item in items {
        if matches!(item, Value::List(_) | Value::Dict(_)) {
            return Err(Stop::Raises("set() of an unhashable value"));
        }
        if !unique.iter().any(|seen| py_eq(seen, &item)) {
            unique.push(item);
        }
    }

    // sorted(): one kind of value, or a single item
    if unique.len() > 1 {
        let texts = unique.iter().all(|v| matches!(v, Value::Str(_)));
        let numbers = unique.iter().all(|v| number(v).is_some());
        if !texts && !numbers {
            return Err(Stop::Raises("sorted() of values that do not compare"));
        }
        if numbers && unique.iter().any(|v| matches!(v, Value::BigInt(_))) {
            return Err(Stop::Unported("sorting integers past i128"));
        }
        if numbers && unique.iter().any(|v| number(v).is_some_and(f64::is_nan)) {
            return Err(Stop::Unported("sorting NaN"));
        }
        unique.sort_by(compare);
    }
    Ok(unique)
}

// python iter(value) 의 값들
fn iterate(value: &Value) -> Result<Vec<Value>> {
    match value {
        Value::List(items) => Ok(items.clone()),
        Value::Str(s) => Ok(s.chars().map(|c| Value::Str(c.to_string())).collect()),
        Value::Dict(d) => Ok(d.iter().map(|(k, _)| Value::Str(k.to_owned())).collect()),
        _ => Err(Stop::Raises("set() of a value that is not iterable")),
    }
}

// 수로 볼 수 있는 값(bool 은 0, 1)
fn number(value: &Value) -> Option<f64> {
    match value {
        Value::Bool(b) => Some(f64::from(u8::from(*b))),
        Value::Int(n) => Some(*n as f64),
        Value::Float(f) => Some(*f),
        Value::BigInt(_) => Some(f64::NAN),
        _ => None,
    }
}

// python == (해시가 되는 값끼리)
fn py_eq(a: &Value, b: &Value) -> bool {
    match (a, b) {
        (Value::Str(x), Value::Str(y)) => x == y,
        (Value::Null, Value::Null) => true,
        (Value::BigInt(x), Value::BigInt(y)) => x == y,
        (Value::Int(x), Value::Int(y)) => x == y,
        _ => match (exact_int(a), exact_int(b)) {
            (Some(x), Some(y)) => x == y,
            _ => {
                matches!((number(a), number(b)), (Some(x), Some(y)) if x == y && !is_big(a) && !is_big(b))
            }
        },
    }
}

fn is_big(value: &Value) -> bool {
    matches!(value, Value::BigInt(_))
}

// 정수 값(bool, int, 정수인 float)이면 그 정수
fn exact_int(value: &Value) -> Option<i128> {
    match value {
        Value::Bool(b) => Some(i128::from(*b)),
        Value::Int(n) => Some(*n),
        Value::Float(f) if f.fract() == 0.0 && f.abs() < 1e38 => Some(*f as i128),
        _ => None,
    }
}

// sorted 의 순서: 글은 코드 포인트(서로게이트 자리표는 python 의 서로게이트 자리), 수는 값
fn compare(a: &Value, b: &Value) -> Ordering {
    match (a, b) {
        (Value::Str(x), Value::Str(y)) => {
            let key = |c: char| unit_of(c).unwrap_or(u32::from(c));
            x.chars().map(key).cmp(y.chars().map(key))
        }
        _ => match (exact_int(a), exact_int(b)) {
            (Some(x), Some(y)) => x.cmp(&y),
            _ => number(a).partial_cmp(&number(b)).unwrap_or(Ordering::Equal),
        },
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn text(s: &str) -> Value {
        Value::Str(s.into())
    }

    /// 앞 파일과 새 경로를 합쳐 겹친 것을 빼고 코드 포인트 순서로 늘어놓는다.
    #[test]
    fn merges_and_sorts_like_python() {
        let old = Value::List(vec![text("b.py"), text("a.py")]);
        let merged = merged_files(Some(&old), &[text("a.py"), text("\u{e9}.rs")]).unwrap();
        assert_eq!(merged, [text("a.py"), text("b.py"), text("\u{e9}.rs")]);

        // Equal numbers keep the first, mixed kinds raise
        let nums =
            merged_files(None, &[Value::Float(1.0), Value::Int(1), Value::Float(0.5)]).unwrap();
        assert_eq!(nums, [Value::Float(0.5), Value::Float(1.0)]);
        assert!(merged_files(Some(&old), &[Value::Float(1.5)]).is_err());
        assert!(merged_files(Some(&Value::Int(3)), &[]).is_err());
    }

    /// 글인 files 는 글자마다, dict 는 키마다 센다.
    #[test]
    fn iterates_text_and_dicts() {
        assert_eq!(
            merged_files(Some(&text("ba")), &[]).unwrap(),
            [text("a"), text("b")]
        );
        assert_eq!(py_len(&text("\u{d55c}x")).unwrap(), 2);
        assert!(py_len(&Value::Int(1)).is_err());
    }

    /// n 은 int, bool, float 에만 1 을 더한다.
    #[test]
    fn counts_like_python() {
        let with = |v: Value| Dict::from_pairs(vec![("n".to_owned(), v)]);
        assert_eq!(next_count(&Dict::new()).unwrap(), Value::Int(1));
        assert_eq!(next_count(&with(Value::Bool(true))).unwrap(), Value::Int(2));
        assert_eq!(
            next_count(&with(Value::Float(2.5))).unwrap(),
            Value::Float(3.5)
        );
        assert!(next_count(&with(Value::Null)).is_err());
        assert!(reaches(&Value::Float(12.0), 12) && !reaches(&Value::Float(f64::NAN), 1));
    }
}
