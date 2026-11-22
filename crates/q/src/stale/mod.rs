//! `hook stale-work`: 오래 방치된 백그라운드 작업 알림(python `scripts/stale_work.py`).
//!
//! Stop, SubagentStop 이 판정해 상태 파일(`<임시 폴더>/claude-q-stale/<sid>.json`)에 쌓고([`evaluate`]), Stop(메인)이 사용자 줄을
//! systemMessage 로 내고, UserPromptSubmit 이 모델 문구를 additionalContext 로 준다. 실패는 삼킨다.
//! 끄기: q 옵션 harness_q_stale, 또는 harness.env 나 환경 변수의 `HARNESS_Q_STALE=off`.

pub mod evaluate;
pub mod signal;

use harness_hook::HookEnv;
use harness_hook::epoch::sanitize;
use harness_hook::py::fs::{exists, read_bytes};
use harness_hook::py::json::{EnsureAscii, dumps_dict};
use harness_hook::py::json_load::{self, Decode};
use harness_hook::py::path::join;
use harness_hook::py::repr::truthy_str;
use harness_hook::py::text::strip;
use harness_hook::py::value::{Dict, Value};
use harness_hook::settings::{self, LoadRequest, Project};

use crate::pyval::{has_surrogate, iterate, now, py_eq, replace_file};
use crate::stop::{Result, Stop};

const TAG: &str = "stale-work";
const SWITCH: &str = "HARNESS_Q_STALE";
const LEVELS: &[&str] = &["action", "warn", "info"];

/// 훅 한 번. 낼 JSON 글(python `json.dump(out, sys.stdout)`, 끝 줄바꿈 없음) 또는 `None`.
pub fn run(hook: &HookEnv, raw: &[u8]) -> Result<Option<String>> {
    if switched_off(hook) {
        return Ok(None);
    }
    let Some(input) = json_load::from_bytes(raw, Decode::SurrogateEscape)
        .ok()
        .and_then(|v| v.into_dict().ok())
    else {
        return Ok(None);
    };

    let event = input.get("hook_event_name").and_then(Value::as_str);
    let tempdir = hook
        .tempdir()
        .ok_or(Stop::Raises("tempfile.gettempdir() found no folder"))?;
    let path = state_file(tempdir, input.get("session_id"));
    let now = now();
    match event {
        Some("UserPromptSubmit") => deliver_model(hook, &input, &path),
        Some("Stop" | "SubagentStop") => judge_tasks(hook, &input, &path, now, tempdir),
        _ => Ok(None),
    }
}

/// python `switched_off()`: 환경 변수가 이기고, 없으면 harness.env 층(q 옵션 포함). 층을 읽지 못하면 켠 채로 둔다.
fn switched_off(hook: &HookEnv) -> bool {
    let value = hook.var(SWITCH).unwrap_or_else(|| layered_switch(hook));
    matches!(strip(&value).to_lowercase().as_str(), "off" | "0" | "no")
}

// harness.env 층의 스위치 값(python `load_layers(defaults=STALE_DEFAULTS)`, 예외면 빈 값)
fn layered_switch(hook: &HookEnv) -> String {
    let defaults = [(SWITCH, "on")];
    let request = LoadRequest {
        project: Project::FromEnv,
        defaults: &defaults,
        plugin_dir: hook.exe_dir.as_deref(),
        ..LoadRequest::default()
    };
    settings::load_layers(&hook.env, &request)
        .ok()
        .and_then(|layers| layers.get(SWITCH).map(str::to_owned))
        .unwrap_or_default()
}

/// python `state_file(sid)`.
fn state_file(tempdir: &str, session_id: Option<&Value>) -> String {
    let dir = join(tempdir, "claude-q-stale");
    join(&dir, &format!("{}.json", sanitize(&truthy_str(session_id))))
}

/// python `load(path)`: 읽은 dict, 아니면 `{"tasks": {}, "model": [], "user": []}`.
fn load(path: &str) -> Dict {
    read_bytes(path)
        .ok()
        .and_then(|bytes| json_load::from_bytes(&bytes, Decode::Strict).ok())
        .and_then(|v| v.into_dict().ok())
        .unwrap_or_else(|| {
            Dict::from_pairs(vec![
                ("tasks".to_owned(), Value::Dict(Dict::new())),
                ("model".to_owned(), Value::List(Vec::new())),
                ("user".to_owned(), Value::List(Vec::new())),
            ])
        })
}

/// python `save(path, st)`(`ensure_ascii=False`, UTF-8 파일이라 짝 없는 서로게이트는 UnicodeEncodeError).
fn save(path: &str, st: &Dict) -> Result<()> {
    let text = dumps_dict(st, EnsureAscii::No, None);
    if has_surrogate(&text) {
        return Err(Stop::Raises("UnicodeEncodeError writing the state"));
    }
    replace_file(path, None, &text)
}

// UserPromptSubmit: 쌓인 모델 문구를 내고 비운다
fn deliver_model(hook: &HookEnv, input: &Dict, path: &str) -> Result<Option<String>> {
    if input.get("agent_id").is_some_and(Value::truthy) || !exists(path) {
        return Ok(None);
    }
    let mut st = load(path);
    let Some(model) = st.get("model").filter(|v| v.truthy()) else {
        return Ok(None);
    };

    let text = wrap(hook, model, input.get("session_id"))?;
    st.insert("model", Value::List(Vec::new()));
    save(path, &st)?;
    let inner = Dict::from_pairs(vec![
        (
            "hookEventName".to_owned(),
            Value::Str("UserPromptSubmit".to_owned()),
        ),
        ("additionalContext".to_owned(), Value::Str(text)),
    ]);
    let outer = Dict::from_pairs(vec![("hookSpecificOutput".to_owned(), Value::Dict(inner))]);
    Ok(Some(dumps_dict(&outer, EnsureAscii::No, None)))
}

// Stop, SubagentStop: 판정하고, 메인의 Stop 이면 사용자 줄을 낸다
fn judge_tasks(
    hook: &HookEnv,
    input: &Dict,
    path: &str,
    now: f64,
    tempdir: &str,
) -> Result<Option<String>> {
    if !matches!(input.get("background_tasks"), Some(Value::List(_))) {
        return Ok(None);
    }
    let mut st = load(path);
    let before = Value::Dict(st.clone());
    evaluate::evaluate(hook, &mut st, input, now, tempdir)?;

    // User lines go out at main's Stop
    let is_stop = input.get("hook_event_name").and_then(Value::as_str) == Some("Stop");
    let is_main = !input.get("agent_id").is_some_and(Value::truthy);
    let mut out = None;
    if is_stop && is_main && st.get("user").is_some_and(Value::truthy) {
        let lines = texts(st.get("user").unwrap_or(&Value::Null))?;
        let message = Dict::from_pairs(vec![(
            "systemMessage".to_owned(),
            Value::Str(lines.join("\n")),
        )]);
        out = Some(dumps_dict(&message, EnsureAscii::No, None));
        st.insert("user", Value::List(Vec::new()));
    }

    // Write only a changed state
    if !Value::Dict(st.clone()).same_content(&before) {
        save(path, &st)?;
    }
    Ok(out)
}

// python "\n".join(value) 의 조각들(글만)
fn texts(value: &Value) -> Result<Vec<String>> {
    iterate(value)?
        .into_iter()
        .map(|v| {
            v.as_str()
                .map(str::to_owned)
                .ok_or(Stop::Raises("str.join of a value that is not text"))
        })
        .collect()
}

/// python `wrap(items, session_id)`: level 마다 태그 하나(action, warn, info 순서).
///
/// 항목은 `(level, 글)` 두 값이어야 한다. 모르는 level 의 글은 버린다.
fn wrap(hook: &HookEnv, model: &Value, session_id: Option<&Value>) -> Result<String> {
    let mut by_level: Vec<(Value, Vec<Value>)> = Vec::new();
    for item in iterate(model)? {
        let pair = iterate(&item)?;
        let [level, text] = <[Value; 2]>::try_from(pair)
            .map_err(|_| Stop::Raises("unpacking a model item that is not a pair"))?;
        if matches!(level, Value::List(_) | Value::Dict(_)) {
            return Err(Stop::Raises("an unhashable level"));
        }
        match by_level.iter_mut().find(|(l, _)| py_eq(l, &level)) {
            Some((_, texts)) => texts.push(text),
            None => by_level.push((level, vec![text])),
        }
    }

    // One tag per known level
    let mut out = Vec::new();
    for name in LEVELS {
        let Some((_, items)) = by_level.iter().find(|(l, _)| l.as_str() == Some(name)) else {
            continue;
        };
        let attr = hook
            .nonce_attr(session_id)
            .map_err(|_| Stop::Raises("session id has a lone surrogate"))?;
        let body = texts(&Value::List(items.clone()))?.join("\n");
        out.push(format!(
            "<harness-hook name=\"{TAG}\" level=\"{name}\"{attr}>\n{body}\n</harness-hook>"
        ));
    }
    Ok(out.join("\n"))
}
