//! 플러그인 상시 규약(ambient)의 UserPromptSubmit 보충 주입(정본 `lib/ambient.py` 의 UserPromptSubmit 갈래).
//!
//! SessionStart 가 돌지 않은 세션(플러그인을 세션 중간에 켬)에 (세션, compact 회차)마다 한 번 `context/ambient.md` 를 싣고
//! 표지를 둔다. SessionStart 도 같은 표지를 두므로 겹치지 않는다. 플러그인마다 다른 것은 플러그인 폴더의 `context/` 에 있다
//! (`ambient.json` 의 plugin, events, off_switch, epoch). SessionStart, SubagentStart, PreCompact 갈래는 python 그대로다
//! (규칙 줄의 claim, 요약기 안내 줄). 어떤 실패든 아무것도 내지 않는다.

use crate::HookEnv;
use crate::epoch::{self, sanitize};
use crate::py::fs::{FsError, os_path, read_bytes, read_text, write_text};
use crate::py::json::{EnsureAscii, dumps_dict};
use crate::py::json_load::{self, Decode};
use crate::py::path::join;
use crate::py::repr::{str_value, truthy_str};
use crate::py::surrogate::encode_os;
use crate::py::text::strip;
use crate::py::value::{Dict, Value};
use crate::settings::{self, LoadRequest};

const EVENT: &str = "UserPromptSubmit";
const EVENTS: &[&str] = &[
    "SessionStart",
    "SubagentStart",
    "UserPromptSubmit",
    "PreCompact",
];

/// `context/ambient.json` 가운데 이 갈래가 쓰는 것(python `load_config` 가 고친 dict).
struct Config {
    plugin: String,
    events: Vec<String>,
    /// 끄기 스위치 이름. 글이 아닌 참 값이면 python 은 `name in os.environ` 에서 예외로 끝난다: 그런 설정은 읽지 않는다.
    off_switch: Option<String>,
    /// compact 회차 이름공간(python `cfg.get("epoch") or cfg["plugin"]` 의 `str()`).
    epoch: String,
}

/// `hook ambient UserPromptSubmit` 한 번: python `print(out)` 의 stdout 바이트(끝 줄바꿈 포함), 내지 않으면 `None`.
///
/// `raw` 는 훅 stdin 이다. JSON 객체가 아니면 python 처럼 빈 입력으로 본다.
pub fn prompt_supplement(hook: &HookEnv, raw: &[u8]) -> Option<Vec<u8>> {
    // Plugin config and text
    let context_dir = join(&hook.plugin_root()?, "context");
    let cfg = load_config(&context_dir)?;
    let data = json_load::from_bytes(raw, Decode::SurrogateEscape)
        .ok()
        .and_then(|v| v.into_dict().ok())
        .unwrap_or_default();
    if is_off(hook, cfg.off_switch.as_deref(), data.get("cwd")) {
        return None;
    }
    let main_text = match read_text(&join(&context_dir, "ambient.md")) {
        Ok(text) => text,
        Err(FsError::Os(_)) => String::new(),
        Err(FsError::Value) => return None,
    };

    // python print(): UTF-8 with surrogateescape, nothing if it cannot encode
    let out = build(hook, &cfg, &data, &main_text)?;
    let mut bytes = encode_os(&out)?;
    bytes.push(b'\n');
    Some(bytes)
}

fn load_config(context_dir: &str) -> Option<Config> {
    let bytes = read_bytes(&join(context_dir, "ambient.json")).ok()?;
    let cfg = json_load::from_bytes(&bytes, Decode::Strict)
        .ok()?
        .into_dict()
        .ok()?;

    // plugin is required, events keep the known names
    let plugin = cfg
        .get("plugin")?
        .as_str()
        .filter(|p| !p.is_empty())?
        .to_owned();
    let events = match cfg.get("events") {
        Some(Value::List(list)) => list
            .iter()
            .filter_map(Value::as_str)
            .filter(|e| EVENTS.contains(e))
            .map(str::to_owned)
            .collect(),
        _ => Vec::new(),
    };

    // Optional switch and epoch namespace
    let off_switch = match truthy(&cfg, "off_switch") {
        None => None,
        Some(Value::Str(s)) => Some(s.clone()),
        Some(_) => return None,
    };
    let epoch = match truthy(&cfg, "epoch") {
        None => plugin.clone(),
        Some(v) => str_value(v),
    };
    Some(Config {
        plugin,
        events,
        off_switch,
        epoch,
    })
}

fn truthy<'a>(dict: &'a Dict, key: &str) -> Option<&'a Value> {
    dict.get(key).filter(|v| v.truthy())
}

/// python `is_off(name, cwd)`: 환경 변수가 이기고, 없으면 harness.env 층과 플러그인 옵션. 값이 off 면 끈다.
///
/// 층을 읽다 난 예외(`Path(cwd)`, `Path.home()`)는 python 이 켠 것으로 본다.
fn is_off(hook: &HookEnv, name: Option<&str>, cwd: Option<&Value>) -> bool {
    let Some(name) = name else {
        return false;
    };
    if let Some(value) = hook.var(name) {
        return strip(&value).to_lowercase() == "off";
    }

    // Layers with the switch on by default
    let Ok(project) = hook.project(cwd) else {
        return false;
    };
    let defaults = [(name, "on")];
    let settings_dir = hook.settings_dir();
    let request = LoadRequest {
        project,
        defaults: &defaults,
        plugin_dir: settings_dir.as_deref(),
        ..LoadRequest::default()
    };
    match settings::load_layers(&hook.env, &request) {
        Ok(layers) => strip(layers.get(name).unwrap_or("")).to_lowercase() == "off",
        Err(_) => false,
    }
}

/// python `build(cfg, "UserPromptSubmit", data, main_text)`: 낼 JSON 글. 내지 않으면 `None`.
fn build(hook: &HookEnv, cfg: &Config, data: &Dict, main_text: &str) -> Option<String> {
    if !cfg.events.iter().any(|e| e == EVENT) || strip(main_text).is_empty() {
        return None;
    }

    // Once per (session, compact epoch), never inside subagents
    let sid = data.get("session_id");
    let sid_text = truthy_str(sid);
    let tempdir = hook.tempdir();
    if truthy(data, "agent_id").is_some() || injected(tempdir, cfg, &sid_text) {
        return None;
    }
    mark(tempdir, cfg, &sid_text);

    // The block with this session's nonce
    let attr = hook.nonce_attr(sid).ok()?;
    let block = format!(
        "<plugin name=\"{}\"{attr}>\n{}\n</plugin>",
        cfg.plugin,
        main_text.trim_matches('\n')
    );
    let inner = Dict::from_pairs(vec![
        ("hookEventName".to_owned(), Value::Str(EVENT.to_owned())),
        ("additionalContext".to_owned(), Value::Str(block)),
    ]);
    let outer = Dict::from_pairs(vec![("hookSpecificOutput".to_owned(), Value::Dict(inner))]);
    Some(dumps_dict(&outer, EnsureAscii::No, None))
}

fn marker_dir(tempdir: &str, cfg: &Config) -> String {
    join(
        tempdir,
        &format!("claude-{}-ambient", sanitize(&cfg.plugin)),
    )
}

fn marker(tempdir: &str, cfg: &Config, sid: &str) -> String {
    join(
        &marker_dir(tempdir, cfg),
        &format!("{}.json", sanitize(sid)),
    )
}

/// python `injected`: 표지의 epoch 가 지금 회차와 같은가. 무엇이든 실패면 거짓.
fn injected(tempdir: Option<&str>, cfg: &Config, sid: &str) -> bool {
    let Some(tempdir) = tempdir else {
        return false;
    };
    let Ok(bytes) = read_bytes(&marker(tempdir, cfg, sid)) else {
        return false;
    };
    let Some(mark) = json_load::from_bytes(&bytes, Decode::Strict)
        .ok()
        .and_then(|v| v.into_dict().ok())
    else {
        return false;
    };

    let now = epoch::epoch(tempdir, &cfg.epoch, sid);
    match mark.get("epoch") {
        Some(Value::Int(n)) => *n == now,
        Some(Value::Bool(b)) => i128::from(*b) == now,
        // python 의 int 와 float 비교는 정확하다: 큰 회차는 float 로 옮기지 않는다
        Some(Value::Float(f)) => now.abs() < (1 << 53) && *f == now as f64,
        _ => false,
    }
}

/// python `mark`: 표지 `{"epoch": N}` 을 쓴다. 쓰지 못하면 넘긴다.
fn mark(tempdir: Option<&str>, cfg: &Config, sid: &str) {
    let Some(tempdir) = tempdir else {
        return;
    };
    let Some(dir) = os_path(&marker_dir(tempdir, cfg)) else {
        return;
    };
    if std::fs::create_dir_all(dir).is_ok() {
        let now = epoch::epoch(tempdir, &cfg.epoch, sid);
        let _ = write_text(&marker(tempdir, cfg, sid), &format!("{{\"epoch\": {now}}}"));
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::Env;

    /// 세션과 회차마다 한 번 싣고, 서브에이전트와 끈 스위치에서는 싣지 않는다.
    #[test]
    fn supplements_once_per_epoch() {
        let base = std::env::temp_dir().join(format!("hh-ambient-{}", std::process::id()));
        let root = base.join("plugin");
        std::fs::create_dir_all(root.join("context")).unwrap();
        std::fs::create_dir_all(base.join("tmp")).unwrap();
        let cfg = r#"{"plugin": "p", "events": ["UserPromptSubmit"], "off_switch": "P_SWITCH"}"#;
        std::fs::write(root.join("context/ambient.json"), cfg).unwrap();
        std::fs::write(root.join("context/ambient.md"), "\nrule\n").unwrap();
        std::fs::write(base.join("salt"), "00".repeat(32)).unwrap();
        let hook = |switch: &str| {
            HookEnv::new(
                Env::from_pairs([
                    ("CLAUDE_PLUGIN_ROOT", root.as_os_str()),
                    ("TMPDIR", base.join("tmp").as_os_str()),
                    ("P_SWITCH", std::ffi::OsStr::new(switch)),
                    ("QWREEY_HARNESS_SALT_FILE", base.join("salt").as_os_str()),
                ]),
                None,
            )
        };

        // Off switch, subagent, then the first and second prompt
        assert_eq!(
            prompt_supplement(&hook("off"), br#"{"session_id": "s"}"#),
            None
        );
        let sub = br#"{"session_id": "s", "agent_id": "a"}"#;
        assert_eq!(prompt_supplement(&hook("on"), sub), None);
        let first = prompt_supplement(&hook("on"), br#"{"session_id": "s"}"#).unwrap();
        let nonce = crate::Nonce::from_salt(&"00".repeat(32), "s");
        let want = format!(
            "{{\"hookSpecificOutput\": {{\"hookEventName\": \"UserPromptSubmit\", \
             \"additionalContext\": \"<plugin name=\\\"p\\\" nonce=\\\"{}\\\">\\nrule\\n</plugin>\"}}}}\n",
            nonce.as_str()
        );
        assert_eq!(String::from_utf8(first).unwrap(), want);
        assert_eq!(
            prompt_supplement(&hook("on"), br#"{"session_id": "s"}"#),
            None
        );

        // A new compact epoch supplements again
        std::fs::create_dir_all(base.join("tmp/claude-p-epoch")).unwrap();
        std::fs::write(base.join("tmp/claude-p-epoch/s"), "1").unwrap();
        assert!(prompt_supplement(&hook("on"), br#"{"session_id": "s"}"#).is_some());
        std::fs::remove_dir_all(&base).unwrap();
    }
}
