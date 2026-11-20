//! 저장소 설정 `<root>/.claude/structure.json`(python `load_cfg`): 기본값 dict 를 파일의 값으로 덮어쓴 것.
//!
//! 값은 꼴을 고치지 않고 JSON 값 그대로 둔다. python 은 쓰는 자리마다 그 값으로 셈하거나 예외로 끝나므로, 읽는 쪽이
//! 그 자리에서 python 처럼 다룬다([`super::pyops`], [`super::num`]).

use harness_hook::py::fs;
use harness_hook::py::json_load::loads;
use harness_hook::py::path::join;
use harness_hook::py::value::{Dict, Value};

use super::pyops::items;

/// structure.json 을 덮어쓴 설정(python `cfg`).
#[derive(Clone, Debug, PartialEq)]
pub struct Config {
    values: Dict,
}

impl Config {
    /// python `DEFAULTS`: 경고 800, 강제 1500, 성장 300, 평평한 폴더 15.
    pub fn defaults() -> Config {
        let values = Dict::from_pairs(vec![
            ("warn".to_owned(), Value::Int(800)),
            ("hard".to_owned(), Value::Int(1500)),
            ("grow".to_owned(), Value::Int(300)),
            ("flat".to_owned(), Value::Int(15)),
            ("ignore".to_owned(), Value::List(Vec::new())),
            ("exempt".to_owned(), Value::List(Vec::new())),
            ("toolkits".to_owned(), Value::Dict(Dict::new())),
        ]);
        Config { values }
    }

    /// python `load_cfg(root)`: 읽지 못하거나 JSON 이 아니면 기본값 그대로.
    pub fn load(root: &str) -> Config {
        let mut cfg = Config::defaults();
        let path = join(&join(root, ".claude"), "structure.json");
        let parsed = fs::read_text(&path).ok().and_then(|text| loads(&text).ok());
        if let Some(value) = parsed {
            cfg.update(&value);
        }
        cfg
    }

    /// 기본값을 `value` 로 덮어쓴 설정(시험용).
    #[cfg(test)]
    pub fn from_value(value: &Value) -> Config {
        let mut cfg = Config::defaults();
        cfg.update(value);
        cfg
    }

    /// python `cfg.get(key)`.
    pub fn get(&self, key: &str) -> Option<&Value> {
        self.values.get(key)
    }

    /// python `cfg[key]` 를 기본값에 있는 키로. 파일은 키를 지우지 못하므로 늘 있다.
    pub fn item(&self, key: &str) -> &Value {
        static NONE: Value = Value::Null;
        self.values.get(key).unwrap_or(&NONE)
    }

    // python dict.update(value): dict 는 덮어쓰고, 목록은 (키, 값) 짝으로 읽다가 틀린 짝에서 멈춘다(앞의 짝은 남는다).
    // 다른 값은 TypeError, ValueError 로 load_cfg 가 잡는다
    fn update(&mut self, value: &Value) {
        match value {
            // An object overrides key by key
            Value::Dict(d) => {
                for (k, v) in d.iter() {
                    self.values.insert(k, v.clone());
                }
            }

            // A list is read as key-value pairs
            Value::List(pairs) => {
                for pair in pairs {
                    let Ok(pair) = items(pair) else { break };
                    if pair.len() != 2 || !pair[0].hashable() {
                        break;
                    }
                    // 글이 아닌 키(수, bool, None)는 글 키로 읽는 이 설정에서 보이지 않는다
                    if let Some(key) = pair[0].as_str() {
                        self.values.insert(key, pair[1].to_value());
                    }
                }
            }

            // Anything else raises inside the try
            _ => {}
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// dict 는 덮어쓰고, 목록은 python dict.update 처럼 짝을 읽다가 멈춘다.
    #[test]
    fn updates_like_python_dict_update() {
        // A dict overrides keys and keeps the defaults
        let mut cfg = Config::defaults();
        cfg.update(&loads(r#"{"warn": 100, "x": 1}"#).unwrap());
        assert_eq!(cfg.item("warn"), &Value::Int(100));
        assert_eq!(cfg.item("hard"), &Value::Int(1500));

        // A list of pairs applies up to the first bad pair; a two-char string is a pair
        let mut cfg = Config::defaults();
        cfg.update(&loads(r#"[["hard", 9], "fl", [1], ["warn", 1]]"#).unwrap());
        assert_eq!(cfg.item("hard"), &Value::Int(9));
        assert_eq!(cfg.get("f"), Some(&Value::Str("l".into())));
        assert_eq!(cfg.item("warn"), &Value::Int(800), "stopped at [1]");
    }
}
