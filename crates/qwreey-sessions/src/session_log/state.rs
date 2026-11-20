//! 훅 상태 `.state/<sid>.hook.json`(python 판의 `hs`): 알림 커서, 이미 한 알림, 마지막으로 워커를 띄운 때.
//!
//! 파일에 든 JSON 을 그대로 들고, dict 로 쓸 때만 dict 인지 본다(python 은 dict 가 아니면 그 자리에서 AttributeError).

use harness_hook::py::value::{Dict, Value};

use crate::abort::{Abort, Result};
use crate::store::{Store, read_json};

/// 알림 dedup 키를 이만큼만 남긴다.
const REMINDED_KEEP: usize = 50;

/// 읽은 훅 상태와, 읽은 뒤 내용이 바뀌었는지.
///
/// 읽은 값을 복사해 두고 견주지 않는다: 복사와 비교는 중첩 단계마다 되부르므로, 망가진 깊은 상태 파일에서 스택이 넘친다.
/// 바꾸는 길은 [`HookState::set`], [`HookState::once`] 뿐이고, 둘 다 실제로 달라질 때만 표시한다.
#[derive(Clone, Debug, PartialEq)]
pub struct HookState {
    value: Value,
    changed: bool,
}

impl HookState {
    /// 외부 저장소가 있으면 그 세션의 훅 상태 파일, 없으면 빈 dict(python `store.hstate(sid) if store.exists() else {}`).
    pub fn load(store: &Store, sid: &str) -> Result<HookState> {
        let value = if store.exists() {
            read_json(&store.hstate_path(sid)?)
        } else {
            Value::Dict(Dict::new())
        };
        Ok(HookState {
            value,
            changed: false,
        })
    }

    /// 읽은 때와 내용이 달라졌나(python `json.dumps(hs, sort_keys=True) != hs0`).
    pub fn changed(&self) -> bool {
        self.changed
    }

    /// 지금 값.
    pub fn value(&self) -> &Value {
        &self.value
    }

    fn dict_mut(&mut self) -> Result<&mut Dict> {
        match &mut self.value {
            Value::Dict(d) => Ok(d),
            _ => Err(Abort("hook state is not a dict")),
        }
    }

    /// `hs.get(key, default)`.
    pub fn get<'a>(&'a self, key: &str, default: &'a Value) -> Result<&'a Value> {
        crate::pyval::get(&self.value, key, default, "hook state is not a dict")
    }

    /// `hs[key] = value`.
    pub fn set(&mut self, key: &str, value: Value) -> Result<()> {
        let dict = self.dict_mut()?;
        let same = dict.get(key).is_some_and(|old| old.same_content(&value));
        dict.insert(key, value);
        self.changed |= !same;
        Ok(())
    }

    /// 이 키로 처음 알리는가(python `once`). 처음이면 `reminded` 에 남기고 참.
    ///
    /// `key` 는 `<trigger>@<회차>` 다. `reminded` 가 목록이 아니면 python 처럼: 글이나 dict 에 이미 들었으면 거짓,
    /// 아니면 append 에서 AttributeError.
    pub fn once(&mut self, key: &str) -> Result<bool> {
        let done = self
            .dict_mut()?
            .setdefault("reminded", Value::List(Vec::new()));

        // 이미 알렸나(python `key in done`)
        let seen = match &*done {
            Value::List(items) => items.iter().any(|v| v.as_str() == Some(key)),
            Value::Str(text) => text.contains(key),
            Value::Dict(d) => d.get(key).is_some(),
            _ => return Err(Abort("reminded is not a container")),
        };
        if seen {
            return Ok(false);
        }

        // 남기고 오래된 것 버리기
        let Value::List(items) = done else {
            return Err(Abort("reminded is not a list"));
        };
        items.push(Value::Str(key.to_owned()));
        if items.len() > REMINDED_KEEP {
            items.drain(..items.len() - REMINDED_KEEP);
        }
        self.changed = true;
        Ok(true)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn state(json: &str) -> HookState {
        let value = harness_hook::py::json_load::loads(json).unwrap();
        HookState {
            value,
            changed: false,
        }
    }

    #[test]
    fn once_keeps_the_last_fifty() {
        let mut hs = state("{}");
        assert!(hs.once("a@0").unwrap());
        assert!(!hs.once("a@0").unwrap());
        for i in 0..60 {
            hs.once(&format!("k{i}@0")).unwrap();
        }
        let Value::Dict(d) = hs.value() else { panic!() };
        let Some(Value::List(items)) = d.get("reminded") else {
            panic!()
        };
        assert_eq!(items.len(), 50);
        assert_eq!(items[0], Value::Str("k10@0".to_owned()));
        assert!(hs.changed());
    }

    #[test]
    fn odd_shapes_follow_python() {
        assert!(!state(r#"{"reminded": "xa@0x"}"#).once("a@0").unwrap());
        assert!(state(r#"{"reminded": "b"}"#).once("a@0").is_err());
        assert!(state(r#"{"reminded": 3}"#).once("a@0").is_err());
        assert!(state("[1]").once("a@0").is_err());
        assert!(!state("[1]").changed());
        let mut hs = state(r#"{"notice_seq": 3}"#);
        hs.set("notice_seq", Value::Int(3)).unwrap();
        assert!(!hs.changed());
        hs.set("notice_seq", Value::Float(3.0)).unwrap();
        assert!(hs.changed());
    }
}
