//! `hook ambient UserPromptSubmit`: 플러그인 상시 규약(ambient)의 보충 주입(python `hooks/ambient.py` 의 UserPromptSubmit 갈래,
//! 정본 `lib/ambient.py`).
//!
//! SessionStart 가 돌지 않은 세션(플러그인을 세션 중간에 켬)에 (세션, compact 회차)마다 한 번 `context/ambient.md` 를 싣고
//! 표지를 둔다. SessionStart 도 같은 표지를 두므로 겹치지 않는다. SessionStart, SubagentStart, PreCompact 갈래는 python 그대로다
//! (규칙 줄의 claim, 요약기 안내 줄). 어떤 실패든 아무것도 내지 않고 0 으로 끝난다.

use harness_hook::py::json::EnsureAscii;
use harness_hook::py::path::join;
use harness_hook::py::surrogate::from_os;
use harness_hook::py::text::strip;
use harness_hook::py::value::{Dict, Value};
use harness_hook::settings::{self, LoadRequest, Project};

use crate::context::Context;
use crate::epoch::{self, sanitize};
use crate::hookio::{context_output, load_dict, parse_object, truthy};
use crate::outcome::Outcome;
use crate::pylib::fs::{FsError, makedirs, read_bytes, read_text, write_text};

const EVENT: &str = "UserPromptSubmit";
const EVENTS: &[&str] = &[
    "SessionStart",
    "SubagentStart",
    "UserPromptSubmit",
    "PreCompact",
];

/// `context/ambient.json` 가운데 이 갈래가 쓰는 것.
struct Config {
    plugin: String,
    events: Vec<String>,
    /// 끄기 스위치 이름. python 은 글이 아닌 참 값에서 예외로 끝난다: 그런 설정은 읽지 않는다.
    off_switch: Option<String>,
    /// compact 회차 이름공간(python `str(cfg["epoch"])`).
    epoch: String,
}

/// 훅 한 번.
pub fn run(ctx: &Context, raw: &[u8]) -> Outcome {
    // Plugin config and text
    let Some(context_dir) = ctx.plugin_root().map(|root| join(&root, "context")) else {
        return Outcome::quiet();
    };
    let Some(cfg) = load_config(&context_dir) else {
        return Outcome::quiet();
    };
    let data = load_dict(raw).unwrap_or_default();
    if is_off(ctx, cfg.off_switch.as_deref(), data.get("cwd")) {
        return Outcome::quiet();
    }
    let main_text = match read_text(&join(&context_dir, "ambient.md")) {
        Ok(text) => text,
        Err(FsError::Os) => String::new(),
        Err(FsError::Value) => return Outcome::quiet(),
    };

    build(ctx, &cfg, &data, &main_text)
        .and_then(|out| Outcome::printed(&out))
        .unwrap_or_default()
}

fn load_config(context_dir: &str) -> Option<Config> {
    let bytes = read_bytes(&join(context_dir, "ambient.json")).ok()?;
    let cfg = parse_object(&bytes).ok()?;

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
        Some(v) => v.scalar_str()?,
    };
    Some(Config {
        plugin,
        events,
        off_switch,
        epoch,
    })
}

/// python `is_off(name, cwd)`: 환경 변수가 이기고, 없으면 harness.env 층과 플러그인 옵션. 값이 off 면 끈다.
fn is_off(ctx: &Context, name: Option<&str>, cwd: Option<&Value>) -> bool {
    let Some(name) = name else {
        return false;
    };
    if let Some(value) = ctx.env.get_os(name) {
        return strip(&from_os(value)).to_lowercase() == "off";
    }

    // python Path(cwd) fails on a non-text cwd, and the except reads it as on
    let project = match ctx.env.get_nonempty("CLAUDE_PROJECT_DIR") {
        Some(dir) => Project::Dir(dir.to_owned()),
        None => match cwd.filter(|v| v.truthy()) {
            None => Project::FromEnv,
            Some(Value::Str(dir)) => Project::Dir(dir.clone()),
            Some(_) => return false,
        },
    };
    let defaults = [(name, "on")];
    let settings_dir = ctx.settings_dir();
    let request = LoadRequest {
        project,
        defaults: &defaults,
        plugin_dir: settings_dir.as_deref(),
        ..LoadRequest::default()
    };
    match settings::load_layers(&ctx.env, &request) {
        Ok(layers) => strip(layers.get(name).unwrap_or("")).to_lowercase() == "off",
        Err(_) => false,
    }
}

/// python `build(cfg, "UserPromptSubmit", data, main_text)`: 낼 JSON 글. 내지 않으면 `None`.
fn build(ctx: &Context, cfg: &Config, data: &Dict, main_text: &str) -> Option<String> {
    if !cfg.events.iter().any(|e| e == EVENT) || strip(main_text).is_empty() {
        return None;
    }

    // Once per (session, compact epoch), never inside subagents
    let sid = data.get("session_id");
    let sid_text = session_text(sid)?;
    let tempdir = ctx.tempdir();
    if truthy(data, "agent_id").is_some() || injected(tempdir, cfg, &sid_text) {
        return None;
    }
    mark(tempdir, cfg, &sid_text);

    // The block with this session's nonce
    let attr = ctx.nonce_attr(sid).ok()?;
    let block = format!(
        "<plugin name=\"{}\"{attr}>\n{}\n</plugin>",
        cfg.plugin,
        main_text.trim_matches('\n')
    );
    Some(context_output(EVENT, &block, EnsureAscii::No))
}

// python str(sid or "nosession") 의 글. 목록, dict 는 repr 이라 옮기지 않는다
fn session_text(sid: Option<&Value>) -> Option<String> {
    match sid.filter(|v| v.truthy()) {
        None => Some(String::new()),
        Some(v) => v.scalar_str(),
    }
}

fn marker(tempdir: &str, cfg: &Config, sid: &str) -> String {
    let dir = join(
        tempdir,
        &format!("claude-{}-ambient", sanitize(&cfg.plugin)),
    );
    join(&dir, &format!("{}.json", sanitize(sid)))
}

fn current_epoch(tempdir: &str, cfg: &Config, sid: &str) -> i128 {
    epoch::epoch(tempdir, &cfg.epoch, sid)
}

/// python `injected`: 표지의 epoch 가 지금 회차와 같은가. 무엇이든 실패면 거짓.
fn injected(tempdir: Option<&str>, cfg: &Config, sid: &str) -> bool {
    let Some(tempdir) = tempdir else {
        return false;
    };
    let Ok(bytes) = read_bytes(&marker(tempdir, cfg, sid)) else {
        return false;
    };
    let Ok(mark) = parse_object(&bytes) else {
        return false;
    };

    let now = current_epoch(tempdir, cfg, sid);
    match mark.get("epoch") {
        Some(Value::Int(n)) => *n == now,
        Some(Value::Bool(b)) => i128::from(*b) == now,
        // python 의 int 와 float 비교는 정확하다: 큰 회차는 float 로 옮기지 않는다
        Some(Value::Float(f)) => now.abs() < (1 << 53) && *f == now as f64,
        _ => false,
    }
}

/// python `mark`: 표지를 쓴다. 쓰지 못하면 넘긴다.
fn mark(tempdir: Option<&str>, cfg: &Config, sid: &str) {
    let Some(tempdir) = tempdir else {
        return;
    };
    let path = marker(tempdir, cfg, sid);
    let dir = join(
        tempdir,
        &format!("claude-{}-ambient", sanitize(&cfg.plugin)),
    );
    if makedirs(&dir).is_ok() {
        let _ = write_text(
            &path,
            &format!("{{\"epoch\": {}}}", current_epoch(tempdir, cfg, sid)),
        );
    }
}
