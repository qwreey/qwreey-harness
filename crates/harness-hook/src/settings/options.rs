//! 플러그인 옵션 층: settings.json 의 `pluginConfigs["<플러그인>@<마켓>"].options`(python `plugin_manifest`,
//! `plugin_options`, `option_value`). `/config`, `/plugin configure` 가 이 자리에 쓴다.
//!
//! - 플러그인 이름은 시작 디렉터리부터 위로 5단계 안에서 처음 읽히는 `.claude-plugin/plugin.json` 의 `name`.
//! - 그 plugin.json 의 `userConfig` 에 선언된 키만 읽는다. 옵션 키는 환경 변수 이름의 소문자다.
//! - 같은 이름이 여러 마켓에 있으면 `enabledPlugins` 에서 켠 것, 그래도 여럿이면 이름순 첫째.
//!   켠 사본에 설정이 아직 없으면 꺼진 사본의 값을 쓰지 않는다.

use std::collections::BTreeSet;
use std::fs;
use std::path::Path;

use serde_json::{Map, Value};

use super::envfile::Values;
use crate::env::Env;
use crate::py::num::{float_repr, integral_float_text};
use crate::py::path::expanduser;

const MANIFEST_DEPTH: usize = 5;

/// plugin.json 에서 읽은 것.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct PluginManifest {
    /// 플러그인 이름(`name`).
    pub name: String,
    /// `userConfig` 키를 대문자로 바꾼 것(= harness.env 키).
    pub option_keys: BTreeSet<String>,
}

/// JSON 파일 하나. 없거나 읽지 못하거나 JSON 이 아니면 `None`.
///
/// python `json.load` 와 다른 점: `NaN`, `Infinity` 글자와 짝 없는 서로게이트를 가리키는 escape 를 받지 않고,
/// 128 단계보다 깊은 중첩도 받지 않는다. python 은 그런 settings.json 의 옵션을 읽고 Rust 는 옵션 층을 건너뛴다.
pub fn read_json(path: &Path) -> Option<Value> {
    let bytes = fs::read(path).ok()?;
    serde_json::from_slice(&bytes).ok()
}

/// `start` 부터 위로 5단계 안에서 처음 만나는 plugin.json(이름이 문자열인 것). 못 찾으면 `None`.
///
/// `start` 는 절대 경로여야 한다(python 은 `os.path.abspath(__file__)` 의 디렉터리).
pub fn plugin_manifest(start: &Path) -> Option<PluginManifest> {
    let mut dir = start;
    for _ in 0..MANIFEST_DEPTH {
        // 읽히지 않거나 이름이 없는 plugin.json 은 건너뛰고 위로 간다
        let data = read_json(&dir.join(".claude-plugin").join("plugin.json"));
        if let Some(Value::Object(data)) = data
            && let Some(Value::String(name)) = data.get("name")
        {
            let option_keys = match data.get("userConfig") {
                Some(Value::Object(config)) => config.keys().map(|k| k.to_uppercase()).collect(),
                _ => BTreeSet::new(),
            };
            return Some(PluginManifest {
                name: name.clone(),
                option_keys,
            });
        }

        dir = dir.parent()?;
    }
    None
}

/// 플러그인 `name` 의 옵션 가운데 `keys`(환경 변수 이름)만 읽는다: (값, 읽은 플러그인 id 또는 빈 문자열).
///
/// `config_dir` 은 settings.json 이 있는 설정 디렉터리. 관리 설정(managed settings)은 읽지 않는다.
pub fn plugin_options(
    env: &Env,
    name: &str,
    keys: &BTreeSet<String>,
    config_dir: &Path,
) -> (Values, String) {
    let nothing = || (Values::new(), String::new());
    if keys.is_empty() {
        return nothing();
    }
    let Some(Value::Object(data)) = read_json(&config_dir.join("settings.json")) else {
        return nothing();
    };
    let Some(Value::Object(configs)) = data.get("pluginConfigs") else {
        return nothing();
    };

    // 이 플러그인의 사본들(마켓마다 하나)
    let ids: Vec<&String> = configs
        .iter()
        .filter(|(id, v)| owner(id) == name && v.is_object())
        .map(|(id, _)| id)
        .collect();
    if ids.is_empty() {
        return nothing();
    }

    // 켠 사본에 설정이 없으면 꺼진 옛 사본의 값(예: 게이트 끔)이 새 사본에 새지 않게 한다
    let enabled: Option<&Map<String, Value>> =
        data.get("enabledPlugins").and_then(Value::as_object);
    let is_on = |id: &str| enabled.and_then(|m| m.get(id)) == Some(&Value::Bool(true));
    let on: Vec<&String> = enabled
        .into_iter()
        .flatten()
        .filter(|(id, _)| is_on(id) && owner(id) == name)
        .map(|(id, _)| id)
        .collect();
    if !on.is_empty() && !on.iter().any(|id| ids.contains(id)) {
        return nothing();
    }

    // 켠 것 먼저, 그다음 이름순
    let pid = ids
        .into_iter()
        .min_by_key(|id| (!is_on(id), id.as_str()))
        .expect("ids is not empty");
    let mut out = Values::new();
    if let Some(Value::Object(opts)) = configs[pid].get("options") {
        for key in keys {
            if let Some(v) = opts
                .get(&key.to_lowercase())
                .and_then(|v| option_value(v, env))
            {
                out.insert(key.clone(), v);
            }
        }
    }
    (out, pid.clone())
}

// python i.rpartition("@")[0]: 마지막 @ 앞, @ 가 없으면 빈 문자열
fn owner(id: &str) -> &str {
    id.rfind('@').map_or("", |at| &id[..at])
}

/// settings.json 옵션 값 하나를 harness.env 꼴 문자열로(python `option_value`). null, 객체는 `None`.
///
/// 참/거짓은 `on`/`off`, 숫자는 python `str`(정수 값 float 는 정수로), 목록은 `;` 로 잇고,
/// 문자열은 `;` 로 나눈 조각마다 맨 앞 `~` 를 홈으로 바꾼다(`$NAME` 은 풀지 않는다).
pub fn option_value(value: &Value, env: &Env) -> Option<String> {
    match value {
        Value::Bool(b) => Some(if *b { "on" } else { "off" }.to_owned()),
        Value::Number(n) => Some(number_text(n)),
        Value::Array(items) => Some(
            items
                .iter()
                .filter_map(|v| option_value(v, env))
                .collect::<Vec<_>>()
                .join(";"),
        ),
        Value::String(s) => Some(
            s.split(';')
                .map(|part| {
                    if part.starts_with('~') {
                        expanduser(part, env)
                    } else {
                        part.to_owned()
                    }
                })
                .collect::<Vec<_>>()
                .join(";"),
        ),
        Value::Null | Value::Object(_) => None,
    }
}

// u64, i64 를 넘는 정수는 serde_json 이 f64 로 읽어 python(임의 정밀도)과 다를 수 있다
fn number_text(n: &serde_json::Number) -> String {
    if let Some(i) = n.as_i64() {
        return i.to_string();
    }
    if let Some(u) = n.as_u64() {
        return u.to_string();
    }
    let f = n.as_f64().unwrap_or(f64::NAN);
    if f.is_finite() && f.fract() == 0.0 {
        integral_float_text(f)
    } else {
        float_repr(f)
    }
}
