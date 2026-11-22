//! 원장 설정(python `subagent_ledger.config`, `num`): harness.env 층 위의 [`DEFAULTS`].

use std::collections::BTreeMap;

use harness_hook::HookEnv;
use harness_hook::py::num::{parse_float, parse_int_saturating};
use harness_hook::py::text::strip;
use harness_hook::py::value::Value;
use harness_hook::settings::{self, LoadRequest, Project};

use crate::num::Num;

/// 원장 키와 기본값(python `CFG_DEFAULTS`).
pub const DEFAULTS: &[(&str, &str)] = &[
    ("HARNESS_SUBAGENT_SLOTS", "on"),
    ("HARNESS_FANOUT_WARN_CONCURRENT", "4"),
    ("HARNESS_FANOUT_WARN_BIG", "2"),
    ("HARNESS_FANOUT_WARN_WORKFLOW", "on"),
    ("HARNESS_AWAY_BUDGET_USD", "20"),
    ("HARNESS_AWAY_SLOTS", "2"),
    ("HARNESS_AWAY_OVER_SLOTS", "1"),
    ("HARNESS_AWAY_BUDGET_PCT", "30"),
    ("HARNESS_AWAY_PLAN", "auto"),
    ("HARNESS_AWAY_STAGE2_MULT", "2"),
    ("HARNESS_AWAY_LIMITS_STALE_MIN", "10"),
    ("HARNESS_AWAY_WORKFLOW", "idle"),
    ("HARNESS_SLOTS_STALE_MIN", "30"),
    ("HARNESS_SLOTS_RESERVE_SEC", "90"),
];
/// 기본값이 없어도 층에서 읽어 오는 키의 접두(python `CFG_PREFIXES`).
const PREFIXES: &[&str] = &[
    "HARNESS_SUBAGENT_",
    "HARNESS_FANOUT_",
    "HARNESS_AWAY_",
    "HARNESS_SLOTS_",
];

/// 원장 설정 값(키 -> 글).
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct Cfg {
    values: BTreeMap<String, String>,
}

impl Cfg {
    /// python `config(project_dir)`. `project` 는 python 이 `load_layers(project)` 에 넘기는 값이다.
    ///
    /// 층을 읽다 난 예외(글이 아닌 cwd, 홈을 모름)는 python 이 삼켜 기본값과 환경 변수만 남는다.
    pub fn load(hook: &HookEnv, project: Option<&Value>) -> Cfg {
        let mut values: BTreeMap<String, String> = DEFAULTS
            .iter()
            .map(|(k, v)| ((*k).to_owned(), (*v).to_owned()))
            .collect();

        // harness.env layers: this ledger's keys only
        if let Some(layers) = layered(hook, project) {
            for (key, value) in layers {
                if values.contains_key(&key) || PREFIXES.iter().any(|p| key.starts_with(p)) {
                    values.insert(key, value);
                }
            }
        }

        // Environment variables win for every known key
        for (key, value) in values.iter_mut() {
            if let Some(from_env) = hook.var(key) {
                *value = from_env;
            }
        }
        Cfg { values }
    }

    /// python `cfg.get(key, default)`.
    pub fn get<'a>(&'a self, key: &str, default: &'a str) -> &'a str {
        self.values.get(key).map_or(default, String::as_str)
    }

    /// python `num(cfg, key)`: float 로 읽은 값, 읽지 못하면 기본값.
    pub fn float(&self, key: &str) -> Num {
        let default = default_of(key);
        let value = parse_float(self.get(key, default))
            .or_else(|| parse_float(default))
            .unwrap_or(0.0);
        Num::Float(value)
    }

    /// python `num(cfg, key, int)`: int 로 읽은 값, 읽지 못하면 기본값. 견주기만 하므로 i128 끝에서 멈춘다.
    pub fn int(&self, key: &str) -> Num {
        let default = default_of(key);
        let value = parse_int_saturating(strip(self.get(key, default)))
            .or_else(|| parse_int_saturating(default))
            .unwrap_or(0);
        Num::Int(value)
    }
}

fn default_of(key: &str) -> &'static str {
    DEFAULTS
        .iter()
        .find(|(k, _)| *k == key)
        .map_or("0", |(_, v)| v)
}

// python load_layers(project): project 가 None 이면 $CLAUDE_PROJECT_DIR, 거짓 값이면 저장소 층 없음, 글이 아니면 TypeError
fn layered(hook: &HookEnv, project: Option<&Value>) -> Option<BTreeMap<String, String>> {
    let project = match hook.env.get_nonempty("CLAUDE_PROJECT_DIR") {
        Some(dir) => Project::Dir(dir.to_owned()),
        None => match project {
            None | Some(Value::Null) => Project::FromEnv,
            Some(Value::Str(dir)) if !dir.is_empty() => Project::Dir(dir.clone()),
            Some(v) if !v.truthy() => Project::Skip,
            Some(_) => return None,
        },
    };

    let request = LoadRequest {
        project,
        plugin_dir: hook.exe_dir.as_deref(),
        ..LoadRequest::default()
    };
    settings::load_layers(&hook.env, &request)
        .ok()
        .map(|layers| layers.values)
}

#[cfg(test)]
mod tests {
    use super::*;
    use harness_hook::Env;

    /// 환경 변수가 이기고, 읽지 못하는 수는 기본값이다.
    #[test]
    fn numbers_fall_back_to_defaults() {
        let env = Env::from_pairs([
            ("HARNESS_AWAY_STAGE2_MULT", " 3 "),
            ("HARNESS_FANOUT_WARN_CONCURRENT", "2.5"),
            ("HARNESS_ENV", "/nonexistent"),
            ("CLAUDE_CONFIG_DIR", "/nonexistent"),
        ]);
        let cfg = Cfg::load(&HookEnv::new(env, None), None);
        assert_eq!(cfg.float("HARNESS_AWAY_STAGE2_MULT"), Num::Float(3.0));
        assert_eq!(cfg.int("HARNESS_FANOUT_WARN_CONCURRENT"), Num::Int(4));
        assert_eq!(cfg.float("HARNESS_UNKNOWN"), Num::Float(0.0));
        assert_eq!(cfg.get("HARNESS_AWAY_WORKFLOW", "idle"), "idle");
    }
}
