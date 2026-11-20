//! 회차별 dedup 상태 파일(python `st`): `<임시 폴더>/claude-second-opinion/<sid>.c<회차>.json`.
//!
//! python 판과 번갈아 읽고 쓴다. 키 순서와 값 꼴(정수, float 표기)을 그대로 지키려고 `py::value::Dict` 로 다룬다.
//! python 이 예외로 끝나는 꼴(객체가 아닌 파일, 수가 아닌 횟수)은 [`Abort`] 다. 그 경로의 python 은 저장도 출력도 하지 않는다.

use harness_hook::py::json::{EnsureAscii, dumps_dict};
use harness_hook::py::value::{Dict, Value};

use crate::abort::{Abort, Result};
use crate::hookio::parse_object;
use crate::pylib::fs::{read_bytes, write_text};

/// 한 세션 회차의 상태.
#[derive(Clone, Debug, PartialEq)]
pub struct State {
    path: String,
    dict: Dict,
}

impl State {
    /// python `read_json(p)`: 읽지 못하거나 JSON 이 아니면 빈 상태. 객체가 아닌 JSON 은 python 이 쓰다가 예외로 끝난다.
    pub fn load(path: String) -> Result<State> {
        let parsed = match read_bytes(&path) {
            Ok(bytes) => parse_object(&bytes),
            Err(_) => Err(None),
        };
        let dict = match parsed {
            Ok(d) => d,
            Err(None) => Dict::new(),
            Err(Some(_)) => return Err(Abort("state file is not an object")),
        };
        Ok(State { path, dict })
    }

    /// python `json.dump(st, open(sp, "w"))`.
    pub fn save(&self) -> Result<()> {
        let text = dumps_dict(&self.dict, EnsureAscii::Yes, None);
        write_text(&self.path, &text).map_err(|_| Abort("cannot write the state file"))
    }

    /// python `cnt = st.setdefault("fail", {}); cnt[sig] = cnt.get(sig, 0) + 1`: 올린 뒤의 횟수가 2 인가.
    pub fn count_failure(&mut self, sig: &str) -> Result<bool> {
        let Value::Dict(counts) = self.dict.setdefault("fail", Value::Dict(Dict::new())) else {
            return Err(Abort("fail is not an object"));
        };
        let next = match counts.get(sig) {
            None => Value::Int(1),
            Some(Value::Int(n)) => Value::Int(n.checked_add(1).ok_or(Abort("count overflow"))?),
            Some(Value::Bool(b)) => Value::Int(i128::from(*b) + 1),
            Some(Value::Float(f)) => Value::Float(f + 1.0),
            Some(_) => return Err(Abort("count is not a number")),
        };
        let second = matches!(next, Value::Int(2)) || matches!(next, Value::Float(f) if f == 2.0);
        counts.insert(sig, next);
        Ok(second)
    }

    /// python `h in st.setdefault("nudged", [])`. 목록이 아니면 python 은 그 뒤 append 에서 예외로 끝난다.
    pub fn nudged_contains(&mut self, hash: &str) -> Result<bool> {
        let Value::List(list) = self.dict.setdefault("nudged", Value::List(Vec::new())) else {
            return Err(Abort("nudged is not a list"));
        };
        Ok(list.iter().any(|v| v.as_str() == Some(hash)))
    }

    /// python `time.time() - st.get("last_nudge", 0) < fresh`: done 알림 뒤 쉬는 중인가.
    pub fn cooling(&self, now: f64, fresh_seconds: f64) -> Result<bool> {
        let last = match self.dict.get("last_nudge") {
            None => 0.0,
            Some(v) => number(v).ok_or(Abort("last_nudge is not a number"))?,
        };
        Ok(now - last < fresh_seconds)
    }

    /// python `st["nudged"].append(h); st["last_nudge"] = time.time()`. [`State::nudged_contains`] 가 목록을 둔 뒤 부른다.
    pub fn record_nudge(&mut self, hash: &str, now: f64) -> Result<()> {
        let Some(Value::List(list)) = self.dict.get_mut("nudged") else {
            return Err(Abort("nudged is not a list"));
        };
        list.push(Value::Str(hash.to_owned()));
        self.dict.insert("last_nudge", Value::Float(now));
        Ok(())
    }
}

/// python 수 값을 float 로(int 와 bool 은 python 산술처럼 바뀐다). 수가 아니면 `None`.
pub fn number(value: &Value) -> Option<f64> {
    match value {
        Value::Int(n) => Some(*n as f64),
        Value::Bool(b) => Some(f64::from(u8::from(*b))),
        Value::Float(f) => Some(*f),
        Value::BigInt(digits) => digits.parse::<f64>().ok().filter(|f| f.is_finite()),
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn state(json: &str) -> State {
        let dict = crate::hookio::loads_object(json).expect("test state is an object");
        State {
            path: String::new(),
            dict,
        }
    }

    /// 실패 횟수는 2 번째에만 참이고, 키 순서와 정수 꼴을 지킨다.
    #[test]
    fn failure_counts_keep_python_shape() {
        // First and second time
        let mut st = state(r#"{"nudged": ["a"]}"#);
        assert_eq!(st.count_failure("Bash|x"), Ok(false));
        assert_eq!(st.count_failure("Bash|x"), Ok(true));
        assert_eq!(
            st.count_failure("Bash|x"),
            Ok(false),
            "only the second time notifies"
        );
        assert_eq!(
            dumps_dict(&st.dict, EnsureAscii::Yes, None),
            r#"{"nudged": ["a"], "fail": {"Bash|x": 3}}"#
        );

        // A float count from an old file stays a float
        let mut st = state(r#"{"fail": {"s": 1.0}}"#);
        assert_eq!(st.count_failure("s"), Ok(true), "2.0 == 2 in python");

        // A broken shape is python's exception
        let mut st = state(r#"{"fail": {"s": "1"}}"#);
        assert!(st.count_failure("s").is_err());
    }

    /// nudge 기록: 목록에 더하고 last_nudge 를 새로 넣거나 그 자리에서 바꾼다.
    #[test]
    fn nudge_records_append() {
        let mut st = state(r#"{"last_nudge": 1, "x": 0}"#);
        assert_eq!(st.nudged_contains("h"), Ok(false));
        st.record_nudge("h", 2.5).expect("list was set");
        assert_eq!(
            dumps_dict(&st.dict, EnsureAscii::Yes, None),
            r#"{"last_nudge": 2.5, "x": 0, "nudged": ["h"]}"#
        );
        assert_eq!(st.nudged_contains("h"), Ok(true));
        assert_eq!(st.cooling(10.0, 60.0), Ok(true));
        assert_eq!(st.cooling(100.0, 60.0), Ok(false));
    }
}
