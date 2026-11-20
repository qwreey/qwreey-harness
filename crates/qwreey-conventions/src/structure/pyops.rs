//! 설정과 상태 파일의 JSON 값에 python 의 컨테이너 연산(`in`, `for`, `append`)을 python 과 같은 결과와 예외로.
//!
//! 값은 저장소가 쓴 structure.json 이나 앞선 실행이 쓴 상태 파일에서 온다. 꼴이 틀려도 python 과 같은 자리에서 같은 결과를 낸다:
//! dict 는 키를, 글은 글자를 돌고, 돌 수 없는 값(None, 수, bool)은 TypeError([`Halt::PyError`])다.

use harness_hook::py::re;
use harness_hook::py::value::{Dict, Value};

use crate::halt::{Halt, Result};

/// 반복으로 나온 원소 하나: 목록의 원소, dict 의 키, 글의 글자.
#[derive(Clone, Debug, PartialEq)]
pub enum Item<'a> {
    Value(&'a Value),
    Text(String),
}

impl Item<'_> {
    /// 글이면 그 글.
    pub fn as_str(&self) -> Option<&str> {
        match self {
            Item::Value(Value::Str(s)) => Some(s),
            Item::Value(_) => None,
            Item::Text(s) => Some(s),
        }
    }

    /// dict 면 그것.
    pub fn as_dict(&self) -> Option<&Dict> {
        match self {
            Item::Value(Value::Dict(d)) => Some(d),
            _ => None,
        }
    }

    /// python `set` 에 넣을 수 있는가(목록과 dict 는 TypeError).
    pub fn hashable(&self) -> bool {
        !matches!(self, Item::Value(Value::List(_) | Value::Dict(_)))
    }

    /// 원소를 값으로.
    pub fn to_value(&self) -> Value {
        match self {
            Item::Value(v) => (*v).clone(),
            Item::Text(s) => Value::Str(s.clone()),
        }
    }
}

/// python `for x in value`.
pub fn items(value: &Value) -> Result<Vec<Item<'_>>> {
    match value {
        Value::List(v) => Ok(v.iter().map(Item::Value).collect()),
        Value::Dict(d) => Ok(d.iter().map(|(k, _)| Item::Text(k.to_owned())).collect()),
        Value::Str(s) => Ok(s.chars().map(|c| Item::Text(c.to_string())).collect()),
        _ => Err(Halt::PyError("iterating a value that is not iterable")),
    }
}

/// python `for x in value or []`: 없거나 거짓이면 빈 목록.
pub fn items_or_empty(value: Option<&Value>) -> Result<Vec<Item<'_>>> {
    match value {
        Some(v) if v.truthy() => items(v),
        _ => Ok(Vec::new()),
    }
}

/// python `needle in value`(`needle` 은 글): 글은 부분 글, 목록은 같은 원소, dict 는 키.
pub fn contains(value: &Value, needle: &str) -> Result<bool> {
    match value {
        Value::Str(s) => Ok(s.contains(needle)),
        Value::List(v) => Ok(v.iter().any(|x| matches!(x, Value::Str(s) if s == needle))),
        Value::Dict(d) => Ok(d.get(needle).is_some()),
        _ => Err(Halt::PyError("`in` on a value that is not a container")),
    }
}

/// python `value.append(text)`: 목록만 가진 메서드다.
pub fn append(value: &mut Value, text: &str) -> Result<()> {
    match value {
        Value::List(v) => {
            v.push(Value::Str(text.to_owned()));
            Ok(())
        }
        _ => Err(Halt::PyError("append on a value that is not a list")),
    }
}

/// python 이 이 정규식 오류에서 내는 예외. 옮기지 않은 문법은 [`Halt::Unported`].
pub fn re_halt(error: &re::Error) -> Halt {
    match error {
        re::Error::Unsupported(_) => Halt::Unported("a regex syntax this port does not support"),
        _ => Halt::PyError("re.error"),
    }
}

/// python `fnmatch.fnmatch(name, pat)`.
pub fn fnmatch(name: &str, pat: &str) -> Result<bool> {
    harness_hook::py::fnmatch::fnmatch(name, pat).map_err(|e| re_halt(&e))
}

/// python 의 글 순서(코드 포인트). 짝 없는 서로게이트의 자리표는 서로게이트 자리로 본다.
pub fn str_order(a: &str, b: &str) -> std::cmp::Ordering {
    let key = |c: char| harness_hook::py::surrogate::unit_of(c).unwrap_or(u32::from(c));
    a.chars().map(key).cmp(b.chars().map(key))
}

#[cfg(test)]
mod tests {
    use super::*;
    use harness_hook::py::json_load::loads;

    /// `in` 과 `for` 가 값의 꼴마다 python 과 같은 결과를 낸다.
    #[test]
    fn container_ops_follow_python() {
        // A string is searched as a substring, a dict by key, a list by element
        assert!(contains(&loads(r#"".ts.vue""#).unwrap(), ".ts").unwrap());
        assert!(contains(&loads(r#"{"a": 1}"#).unwrap(), "a").unwrap());
        assert!(!contains(&loads(r#"[1, "b"]"#).unwrap(), "1").unwrap());
        assert!(
            contains(&loads("5").unwrap(), "a").is_err(),
            "int is not iterable"
        );

        // Iteration gives dict keys and string characters
        let dict = loads(r#"{"x": 1, "y": 2}"#).unwrap();
        let keys = items(&dict).unwrap();
        assert_eq!(keys, vec![Item::Text("x".into()), Item::Text("y".into())]);
        assert_eq!(items(&Value::Str("ab".into())).unwrap().len(), 2);
        assert!(items(&Value::Null).is_err());
        assert!(
            items_or_empty(Some(&Value::Int(0))).unwrap().is_empty(),
            "0 or [] is []"
        );
    }

    /// 자리표는 python 의 서로게이트 코드 자리에서 정렬된다.
    #[test]
    fn placeholders_sort_as_surrogates() {
        // A surrogate sorts below private-use 0xE000 in python, though its placeholder is above
        let surrogate = harness_hook::py::surrogate::placeholder(0xDCFF)
            .unwrap()
            .to_string();
        assert_eq!(str_order(&surrogate, "\u{e000}"), std::cmp::Ordering::Less);
    }
}
