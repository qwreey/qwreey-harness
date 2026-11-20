//! 훅 입력 값을 python 훅이 읽는 꼴로: `x or ""`, `x or {}`, `str(x)` 의 결과와, 그 뒤에 python 이 예외로 끝나는 꼴.

use harness_hook::epoch::sanitize;
use harness_hook::py::value::{Dict, Value};

use crate::halt::{Halt, Result};

/// python 에서 참인 값의 `str()`. 없거나 거짓이면 `None`.
///
/// 목록과 dict 는 python 이 repr 글을 쓰는 자리라 이 판이 옮기지 않는다([`Halt::Unported`]).
pub fn truthy_text(value: Option<&Value>) -> Result<Option<String>> {
    match value {
        Some(v) if v.truthy() => v
            .scalar_str()
            .map(Some)
            .ok_or(Halt::Unported("a list or dict id")),
        _ => Ok(None),
    }
}

/// python `re.sub(r"[^\w-]", "", str(value or "nosession"))`(상태 파일 이름에 넣는 id).
pub fn sanitized_id(value: Option<&Value>) -> Result<String> {
    Ok(sanitize(truthy_text(value)?.as_deref().unwrap_or("")))
}

/// python `value or {}` 를 dict 로 쓰는 자리. 거짓이면 `None`(빈 dict), 참인 dict 가 아니면 python 은 `.get` 에서 끝난다.
pub fn dict_or_empty(value: Option<&Value>) -> Result<Option<&Dict>> {
    match value {
        Some(Value::Dict(d)) => Ok(Some(d)),
        Some(v) if v.truthy() => Err(Halt::PyError("expected a dict")),
        _ => Ok(None),
    }
}

/// python `value or ""` 를 글로 쓰는 자리. 거짓이면 빈 글, 참인 글이 아니면 python 은 글 함수에서 끝난다.
pub fn str_or_empty(value: Option<&Value>) -> Result<&str> {
    match value {
        Some(Value::Str(s)) => Ok(s),
        Some(v) if v.truthy() => Err(Halt::PyError("expected a string")),
        _ => Ok(""),
    }
}

/// `d.get(key)` 를 `dict_or_empty` 결과에서.
pub fn get<'a>(dict: Option<&'a Dict>, key: &str) -> Option<&'a Value> {
    dict.and_then(|d| d.get(key))
}

#[cfg(test)]
mod tests {
    use super::*;

    /// `x or ""`, `x or {}`, `str(x)` 를 python 처럼 읽고 python 이 끝나는 꼴은 오류로 돌려준다.
    #[test]
    fn reads_like_python_or() {
        // Truthy scalars give their str() text
        assert_eq!(
            truthy_text(Some(&Value::Int(5))).unwrap().as_deref(),
            Some("5")
        );
        assert_eq!(truthy_text(Some(&Value::Int(0))).unwrap(), None);
        assert!(truthy_text(Some(&Value::List(vec![Value::Null]))).is_err());

        // Ids for file names
        assert_eq!(sanitized_id(None).unwrap(), "nosession");
        assert_eq!(sanitized_id(Some(&Value::Str("a/b".into()))).unwrap(), "ab");

        // `x or ""` and `x or {}`: a truthy value of another type is a python error
        assert_eq!(str_or_empty(Some(&Value::Int(0))).unwrap(), "");
        assert!(str_or_empty(Some(&Value::Int(1))).is_err());
        assert!(dict_or_empty(Some(&Value::List(vec![]))).unwrap().is_none());
    }
}
