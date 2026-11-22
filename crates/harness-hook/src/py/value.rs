//! python `json.load` 가 주는 값(dict 는 넣은 순서를 지킨다). 읽기는 [`super::json_load`], 쓰기는 [`super::json::dumps`].
//!
//! why not `serde_json::Value`: preserve_order 기능 없이는 객체 키를 정렬해 버려, python 이 쓴 파일을 읽고 고쳐 쓰면 키 순서가
//! 달라진다. 그 기능을 켜면 워크스페이스 전체의 `serde_json::Map` 순서가 바뀐다. 상태 파일을 python 훅과 번갈아 쓰려면 순서가 같아야 한다.
//! 또 python 처럼 i128 을 넘는 정수([`Value::BigInt`])와 NaN, 무한대를 담는다.
//!
//! serde 의 `Serialize`, `Deserialize` 는 두지 않는다: serde_json 은 NaN 을 `null` 로 쓰고 큰 정수를 float 로 읽어 python 과 달라진다.

use std::collections::HashMap;

use super::num::float_repr;

/// JSON 값 하나. python 의 None, bool, int, float, str, list, dict 자리다.
#[derive(Clone, Debug, PartialEq)]
pub enum Value {
    Null,
    Bool(bool),
    Int(i128),
    /// i128 밖의 정수. python `str(n)` 글(부호와 숫자, 앞자리 0 없음)이다. i128 안의 값은 늘 [`Value::Int`] 다.
    BigInt(String),
    Float(f64),
    Str(String),
    List(Vec<Value>),
    Dict(Dict),
}

/// 넣은 순서를 지키는 dict. 같은 키를 다시 넣으면 자리는 그대로 두고 값만 바꾼다(python dict 와 같다).
#[derive(Clone, Debug, Default, PartialEq)]
pub struct Dict(Vec<(String, Value)>);

/// 키가 이보다 많은 객체는 겹친 키를 해시로 찾는다(적으면 훑는 편이 빠르다).
const HASH_DEDUP_FROM: usize = 16;

impl Dict {
    /// 빈 dict.
    pub fn new() -> Dict {
        Dict::default()
    }

    /// (키, 값) 목록으로 만든 dict(python `dict(pairs)`): 겹친 키는 처음 자리에 마지막 값.
    pub fn from_pairs(pairs: Vec<(String, Value)>) -> Dict {
        if pairs.len() <= HASH_DEDUP_FROM {
            let mut dict = Dict::new();
            for (k, v) in pairs {
                dict.insert(k, v);
            }
            return dict;
        }

        // 큰 객체: 키마다 첫 자리를 기억해 둔다(훑으면 키 수의 제곱)
        let mut first: HashMap<String, usize> = HashMap::with_capacity(pairs.len());
        let mut out: Vec<(String, Value)> = Vec::with_capacity(pairs.len());
        for (k, v) in pairs {
            match first.get(&k) {
                Some(&i) => out[i].1 = v,
                None => {
                    first.insert(k.clone(), out.len());
                    out.push((k, v));
                }
            }
        }
        Dict(out)
    }

    /// `d.get(key)`.
    pub fn get(&self, key: &str) -> Option<&Value> {
        self.0.iter().find(|(k, _)| k == key).map(|(_, v)| v)
    }

    /// `d.get(key)` 를 고칠 수 있게.
    pub fn get_mut(&mut self, key: &str) -> Option<&mut Value> {
        self.0.iter_mut().find(|(k, _)| k == key).map(|(_, v)| v)
    }

    /// `d[key] = value`.
    pub fn insert(&mut self, key: impl Into<String>, value: Value) {
        let key = key.into();
        match self.get_mut(&key) {
            Some(slot) => *slot = value,
            None => self.0.push((key, value)),
        }
    }

    /// `d.pop(key, None)`.
    pub fn remove(&mut self, key: &str) -> Option<Value> {
        let i = self.0.iter().position(|(k, _)| k == key)?;
        Some(self.0.remove(i).1)
    }

    /// `d.setdefault(key, default)`.
    pub fn setdefault(&mut self, key: &str, default: Value) -> &mut Value {
        if self.get(key).is_none() {
            self.0.push((key.to_owned(), default));
        }
        self.get_mut(key).expect("just inserted")
    }

    /// 키와 값, 넣은 순서로.
    pub fn iter(&self) -> impl Iterator<Item = (&str, &Value)> {
        self.0.iter().map(|(k, v)| (k.as_str(), v))
    }

    /// 키 수.
    pub fn len(&self) -> usize {
        self.0.len()
    }

    /// 비었는가(python 에서 거짓).
    pub fn is_empty(&self) -> bool {
        self.0.is_empty()
    }

    /// 키 순서를 무시하고 같은가(python `json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)`).
    pub fn same_content(&self, other: &Dict) -> bool {
        self.len() == other.len()
            && self
                .iter()
                .all(|(k, v)| other.get(k).is_some_and(|w| same_content(v, w)))
    }
}

fn same_content(a: &Value, b: &Value) -> bool {
    match (a, b) {
        (Value::Dict(x), Value::Dict(y)) => x.same_content(y),
        (Value::List(x), Value::List(y)) => {
            x.len() == y.len() && x.iter().zip(y).all(|(p, q)| same_content(p, q))
        }
        // dumps 글이 같은가: 1 과 1.0 은 다르고, True 와 1 도 다르다. NaN 은 모두 `NaN` 이다
        (Value::Float(x), Value::Float(y)) => {
            x.to_bits() == y.to_bits() || (x.is_nan() && y.is_nan())
        }
        _ => a == b,
    }
}

// 깊게 중첩된 값도 되부름 없이 버린다. 기본 drop 은 단계마다 스택을 써서 수만 단계면 넘친다(읽기 한도는 50000 단계).
// 안의 목록과 dict 를 꺼내 한 줄로 늘어놓은 뒤 버리므로, 늘어놓은 값들의 drop 은 더 내려가지 않는다
impl Drop for Value {
    fn drop(&mut self) {
        let mut pending = match self {
            Value::List(items) if items.iter().any(Value::is_container) => std::mem::take(items),
            Value::Dict(Dict(pairs)) if pairs.iter().any(|(_, v)| v.is_container()) => {
                std::mem::take(pairs).into_iter().map(|(_, v)| v).collect()
            }
            _ => return,
        };
        while let Some(mut value) = pending.pop() {
            match &mut value {
                Value::List(items) => pending.append(items),
                Value::Dict(Dict(pairs)) => {
                    pending.extend(std::mem::take(pairs).into_iter().map(|(_, v)| v))
                }
                _ => {}
            }
        }
    }
}

impl Value {
    /// dict 면 그 dict 를 꺼낸다(아니면 값 그대로 `Err`). [`Drop`] 이 있어 `match` 로 꺼낼 수 없다.
    pub fn into_dict(mut self) -> Result<Dict, Value> {
        if let Value::Dict(d) = &mut self {
            return Ok(std::mem::take(d));
        }
        Err(self)
    }

    fn is_container(&self) -> bool {
        matches!(self, Value::List(_) | Value::Dict(_))
    }

    /// 키 순서를 무시하고 같은가(python `json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)`).
    pub fn same_content(&self, other: &Value) -> bool {
        same_content(self, other)
    }

    /// dict 면 그것.
    pub fn as_dict(&self) -> Option<&Dict> {
        match self {
            Value::Dict(d) => Some(d),
            _ => None,
        }
    }

    /// 문자열이면 그것.
    pub fn as_str(&self) -> Option<&str> {
        match self {
            Value::Str(s) => Some(s),
            _ => None,
        }
    }

    /// python `str(v)` 의 글. 목록과 dict 는 `None` 이다(그 repr 은 [`crate::py::repr::str_value`]).
    pub fn scalar_str(&self) -> Option<String> {
        match self {
            Value::Null => Some("None".to_owned()),
            Value::Bool(true) => Some("True".to_owned()),
            Value::Bool(false) => Some("False".to_owned()),
            Value::Int(i) => Some(i.to_string()),
            Value::BigInt(digits) => Some(digits.clone()),
            Value::Float(f) => Some(float_repr(*f)),
            Value::Str(s) => Some(s.clone()),
            Value::List(_) | Value::Dict(_) => None,
        }
    }

    /// python 의 참거짓(`bool(v)`).
    pub fn truthy(&self) -> bool {
        match self {
            Value::Null => false,
            Value::Bool(b) => *b,
            Value::Int(i) => *i != 0,
            Value::BigInt(_) => true,
            Value::Float(f) => *f != 0.0,
            Value::Str(s) => !s.is_empty(),
            Value::List(l) => !l.is_empty(),
            Value::Dict(d) => !d.is_empty(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::py::json::{EnsureAscii, dumps};
    use crate::py::json_load::loads;

    /// 겹친 키는 처음 자리에 마지막 값으로 남고, 쓸 때 그 순서를 지킨다.
    #[test]
    fn duplicate_keys_keep_first_position_and_last_value() {
        let v = loads(r#"{"b": 1, "a": {"y": 2.5, "x": [true, null]}, "b": 3}"#).unwrap();

        assert_eq!(
            dumps(&v, EnsureAscii::Yes, None),
            r#"{"b": 3, "a": {"y": 2.5, "x": [true, null]}}"#
        );
    }

    /// `same_content` 는 키 순서가 달라도 같은 내용이면 참이다.
    #[test]
    fn same_content_ignores_key_order() {
        let v = loads(r#"{"b": 1, "a": {"y": 2.5, "x": [true, null]}, "b": 3}"#).unwrap();
        let Value::Dict(d) = &v else { panic!() };
        let other = loads(r#"{"a": {"x": [true, null], "y": 2.5}, "b": 3}"#).unwrap();
        assert!(d.same_content(other.as_dict().unwrap()));
    }

    /// `same_content` 는 정수 3 과 실수 3.0 을 다른 내용으로 본다.
    #[test]
    fn same_content_tells_int_from_float() {
        let v = loads(r#"{"b": 1, "a": {"y": 2.5, "x": [true, null]}, "b": 3}"#).unwrap();
        let Value::Dict(d) = &v else { panic!() };
        let float = loads(r#"{"a": {"x": [true, null], "y": 2.5}, "b": 3.0}"#).unwrap();

        assert!(!d.same_content(float.as_dict().unwrap()));
    }

    /// NaN 도 NaN 과 같은 내용으로 본다.
    #[test]
    fn same_content_takes_nan_as_equal() {
        let nan = loads("[NaN]").unwrap();

        assert!(nan.same_content(&loads("[NaN]").unwrap()));
    }

    /// 키가 많은 객체도 겹친 키는 처음 자리에 마지막 값으로 남는다.
    #[test]
    fn big_objects_keep_first_position_and_last_value() {
        let pairs: Vec<(String, Value)> = (0..40)
            .map(|i| (format!("k{}", i % 30), Value::Int(i)))
            .collect();
        let d = Dict::from_pairs(pairs);
        assert_eq!(d.len(), 30);
        assert_eq!(d.iter().next(), Some(("k0", &Value::Int(30))));
        assert_eq!(d.get("k29"), Some(&Value::Int(29)));
    }

    /// 100 만 겹 중첩 목록을 버려도 스택이 넘치지 않는다.
    #[test]
    fn drop_handles_deep_nesting() {
        let mut v = Value::Null;
        for _ in 0..1_000_000 {
            v = Value::List(vec![v]);
        }
        drop(v);
    }
}
