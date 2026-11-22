//! 훅 입력 값을 python 처럼 글로: `str(v)`, `str(v or "")`.
//!
//! Claude Code 는 문자열만 주지만 python 판은 어떤 JSON 값이든 `str()` 로 바꿔 쓴다(경로, session_id). 목록과 dict 의
//! `str()` 은 repr 이라 글의 따옴표와 escape 가 python 과 같아야 한다. ASCII 밖 글자의 repr 은 python 의 출력 가능 표
//! (`str.isprintable`)가 필요해 옮기지 않았다([`Stop::Unported`]).

use harness_hook::py::num::float_repr;
use harness_hook::py::repr::repr_ascii;
use harness_hook::py::value::Value;

use crate::stop::{Result, Stop};

// 이보다 깊게 중첩된 값의 repr 은 옮기지 않는다(python 도 깊으면 RecursionError 다, 그 깊이는 C 스택에 달렸다)
const MAX_DEPTH: usize = 100;

/// python `str(v)`.
pub fn py_str(v: &Value) -> Result<String> {
    match v {
        Value::Str(s) => Ok(s.clone()),
        other => repr(other, 0),
    }
}

/// python `str(v or "")`: 거짓 값은 빈 글.
pub fn truthy_text(v: Option<&Value>) -> Result<String> {
    match v {
        Some(v) if v.truthy() => py_str(v),
        _ => Ok(String::new()),
    }
}

// python repr(v): 글은 따옴표로, 목록과 dict 는 원소마다 repr
fn repr(v: &Value, depth: usize) -> Result<String> {
    if depth > MAX_DEPTH {
        return Err(Stop::Unported("repr of a deeply nested value"));
    }

    match v {
        // Scalars print as str() does
        Value::Null => Ok("None".to_owned()),
        Value::Bool(true) => Ok("True".to_owned()),
        Value::Bool(false) => Ok("False".to_owned()),
        Value::Int(i) => Ok(i.to_string()),
        Value::BigInt(digits) => Ok(digits.clone()),
        Value::Float(f) => Ok(float_repr(*f)),

        // Text is quoted
        Value::Str(s) => quoted(s),

        // Containers repr each item
        Value::List(items) => {
            let parts: Result<Vec<String>> = items.iter().map(|x| repr(x, depth + 1)).collect();
            Ok(format!("[{}]", parts?.join(", ")))
        }
        Value::Dict(dict) => {
            let mut parts = Vec::with_capacity(dict.len());
            for (key, value) in dict.iter() {
                parts.push(format!("{}: {}", quoted(key)?, repr(value, depth + 1)?));
            }
            Ok(format!("{{{}}}", parts.join(", ")))
        }
    }
}

fn quoted(text: &str) -> Result<String> {
    repr_ascii(text).ok_or(Stop::Unported("repr of non-ASCII text"))
}

#[cfg(test)]
mod tests {
    use super::*;
    use harness_hook::py::json_load::loads;

    /// 목록과 dict 는 python repr, 글은 그대로, 거짓 값은 빈 글이다.
    #[test]
    fn str_like_python() {
        let v = loads(r#"[1, 2.5, "a'b", {"k": null}, true, []]"#).unwrap();
        assert_eq!(
            py_str(&v).unwrap(),
            r#"[1, 2.5, "a'b", {'k': None}, True, []]"#
        );
        assert_eq!(py_str(&Value::Str("x/y".into())).unwrap(), "x/y");
        assert_eq!(truthy_text(Some(&Value::Int(0))).unwrap(), "");
        assert_eq!(truthy_text(Some(&Value::Float(1e20))).unwrap(), "1e+20");

        // 목록 안의 ASCII 밖 글자는 python 의 출력 가능 표가 있어야 한다
        let odd = loads(r#"["é"]"#).unwrap();
        assert!(matches!(py_str(&odd), Err(Stop::Unported(_))));
    }
}
