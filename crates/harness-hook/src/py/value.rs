//! python `json.load` 가 주는 값(dict 는 넣은 순서를 지킨다)과 `json.dump` 로 다시 쓰기.
//!
//! why not `serde_json::Value`: preserve_order 기능 없이는 객체 키를 정렬해 버려, python 이 쓴 파일을 읽고 고쳐 쓰면 키 순서가
//! 달라진다. 그 기능을 켜면 워크스페이스 전체의 `serde_json::Map` 순서가 바뀐다. 상태 파일을 python 훅과 번갈아 쓰려면 순서가 같아야 한다.
//!
//! python 과 다른 점: 정수는 i128 범위까지(그 밖은 serde_json 이 float 로 읽는다), `NaN`, `Infinity` 글자는 읽지 못한다.

use std::fmt;

use serde::de::{self, Deserialize, Deserializer, MapAccess, SeqAccess, Visitor};
use serde::ser::{Serialize, SerializeMap, SerializeSeq, Serializer};

/// JSON 값 하나. python 의 None, bool, int, float, str, list, dict 자리다.
#[derive(Clone, Debug, PartialEq)]
pub enum Value {
    Null,
    Bool(bool),
    Int(i128),
    Float(f64),
    Str(String),
    List(Vec<Value>),
    Dict(Dict),
}

/// 넣은 순서를 지키는 dict. 같은 키를 다시 넣으면 자리는 그대로 두고 값만 바꾼다(python dict 와 같다).
#[derive(Clone, Debug, Default, PartialEq)]
pub struct Dict(Vec<(String, Value)>);

impl Dict {
    /// 빈 dict.
    pub fn new() -> Dict {
        Dict::default()
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
        // dumps 글이 같은가: 1 과 1.0 은 다르고, True 와 1 도 다르다
        (Value::Float(x), Value::Float(y)) => x.to_bits() == y.to_bits(),
        _ => a == b,
    }
}

impl Value {
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

    /// python 의 참거짓(`bool(v)`).
    pub fn truthy(&self) -> bool {
        match self {
            Value::Null => false,
            Value::Bool(b) => *b,
            Value::Int(i) => *i != 0,
            Value::Float(f) => *f != 0.0,
            Value::Str(s) => !s.is_empty(),
            Value::List(l) => !l.is_empty(),
            Value::Dict(d) => !d.is_empty(),
        }
    }
}

/// `serde_json::Value` 를 이것으로(객체 키 순서는 그 값의 순서).
impl From<&serde_json::Value> for Value {
    fn from(v: &serde_json::Value) -> Value {
        match v {
            serde_json::Value::Null => Value::Null,
            serde_json::Value::Bool(b) => Value::Bool(*b),
            serde_json::Value::Number(n) => match (n.as_i64(), n.as_u64()) {
                (Some(i), _) => Value::Int(i128::from(i)),
                (None, Some(u)) => Value::Int(i128::from(u)),
                _ => Value::Float(n.as_f64().unwrap_or(f64::NAN)),
            },
            serde_json::Value::String(s) => Value::Str(s.clone()),
            serde_json::Value::Array(a) => Value::List(a.iter().map(Value::from).collect()),
            serde_json::Value::Object(o) => Value::Dict(Dict(
                o.iter().map(|(k, v)| (k.clone(), Value::from(v))).collect(),
            )),
        }
    }
}

impl Serialize for Value {
    fn serialize<S: Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
        match self {
            Value::Null => s.serialize_unit(),
            Value::Bool(b) => s.serialize_bool(*b),
            Value::Int(i) => s.serialize_i128(*i),
            Value::Float(f) => s.serialize_f64(*f),
            Value::Str(t) => s.serialize_str(t),
            Value::List(items) => {
                let mut seq = s.serialize_seq(Some(items.len()))?;
                for item in items {
                    seq.serialize_element(item)?;
                }
                seq.end()
            }
            Value::Dict(d) => d.serialize(s),
        }
    }
}

impl Serialize for Dict {
    fn serialize<S: Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
        let mut map = s.serialize_map(Some(self.0.len()))?;
        for (k, v) in &self.0 {
            map.serialize_entry(k, v)?;
        }
        map.end()
    }
}

impl<'de> Deserialize<'de> for Value {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Value, D::Error> {
        d.deserialize_any(ValueVisitor)
    }
}

struct ValueVisitor;

impl<'de> Visitor<'de> for ValueVisitor {
    type Value = Value;

    fn expecting(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str("a JSON value")
    }

    fn visit_unit<E: de::Error>(self) -> Result<Value, E> {
        Ok(Value::Null)
    }

    fn visit_bool<E: de::Error>(self, b: bool) -> Result<Value, E> {
        Ok(Value::Bool(b))
    }

    fn visit_i64<E: de::Error>(self, i: i64) -> Result<Value, E> {
        Ok(Value::Int(i128::from(i)))
    }

    fn visit_u64<E: de::Error>(self, u: u64) -> Result<Value, E> {
        Ok(Value::Int(i128::from(u)))
    }

    fn visit_f64<E: de::Error>(self, f: f64) -> Result<Value, E> {
        Ok(Value::Float(f))
    }

    fn visit_str<E: de::Error>(self, s: &str) -> Result<Value, E> {
        Ok(Value::Str(s.to_owned()))
    }

    fn visit_string<E: de::Error>(self, s: String) -> Result<Value, E> {
        Ok(Value::Str(s))
    }

    fn visit_seq<A: SeqAccess<'de>>(self, mut seq: A) -> Result<Value, A::Error> {
        let mut items = Vec::new();
        while let Some(item) = seq.next_element()? {
            items.push(item);
        }
        Ok(Value::List(items))
    }

    fn visit_map<A: MapAccess<'de>>(self, mut map: A) -> Result<Value, A::Error> {
        let mut dict = Dict::new();
        while let Some((k, v)) = map.next_entry::<String, Value>()? {
            dict.insert(k, v);
        }
        Ok(Value::Dict(dict))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::py::json::{EnsureAscii, to_string};

    #[test]
    fn keeps_order_and_writes_like_python() {
        let v: Value =
            serde_json::from_str(r#"{"b": 1, "a": {"y": 2.5, "x": [true, null]}, "b": 3}"#)
                .unwrap();
        assert_eq!(
            to_string(&v, EnsureAscii::Yes).unwrap(),
            r#"{"b": 3, "a": {"y": 2.5, "x": [true, null]}}"#
        );
        let Value::Dict(d) = &v else { panic!() };
        let other: Value =
            serde_json::from_str(r#"{"a": {"x": [true, null], "y": 2.5}, "b": 3}"#).unwrap();
        assert!(d.same_content(other.as_dict().unwrap()));
        let float: Value =
            serde_json::from_str(r#"{"a": {"x": [true, null], "y": 2.5}, "b": 3.0}"#).unwrap();
        assert!(!d.same_content(float.as_dict().unwrap()));
    }
}
