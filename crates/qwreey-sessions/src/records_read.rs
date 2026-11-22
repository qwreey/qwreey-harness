//! 기록 읽기 훅(python `scripts/records_read.py`).
//!
//! - PreToolUse(Read): 기록(외부 저장소의 세션 기록, 저장소 보관 폴더, 어느 저장소든 `.claude/` 스냅숏 폴더)을 offset, limit
//!   없이 Read 하는데 파일이 `SESSION_LOG_READ_GATE_KB`(기본 32 KiB) 이상이면 deny 하고 부분 읽기를 안내한다.
//! - PostToolUse(Read, Grep): 세션 기록을 읽으면 스냅숏 경고를 (session_id, agent_id 또는 main, compact 회차)마다 한 번.
//!
//! 모든 Read 에서 불리므로 글자 검사를 먼저 하고 stat 은 기록 경로일 때만 한다. 어떤 실패든 아무것도 내지 않는다.

use std::fs::OpenOptions;

use harness_hook::py::num::integral_float_text;
use harness_hook::py::path::{join, normpath, splitext, which};
use harness_hook::py::surrogate::from_os;
use harness_hook::py::value::{Dict, Value};
use harness_hook::tag::Level;
use harness_hook::{EnsureAscii, HookInput, HookOutput};

use crate::abort::{Abort, Result};
use crate::config::{Key, claude_config_dir, home_claude_dir};
use crate::context::Context;
use crate::epoch;
use crate::fsx::{self, FsError};
use crate::messages;
use crate::pyval::truthy_str;
use crate::records_home::{self, is_snapshot, is_under};

/// Read 가 offset/limit 으로 나눠 읽지 못하는 파일(그림은 통째로, PDF 는 pages 로). 막으면 읽을 길이 없다.
const NOT_TEXT: &[&str] = &[
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".pdf", ".ipynb",
];
/// 회차마다 한 번 알린 표식을 두는 임시 폴더 이름.
const MARKER_DIR: &str = "claude-sessions-records-read";

/// 하위 명령의 이벤트. `PreToolUse` 가 아니면 모두 PostToolUse 로 본다(python 판과 같다).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Event {
    PreToolUse,
    PostToolUse,
}

impl Event {
    /// 하위 명령 인자(없으면 PostToolUse).
    pub fn from_arg(arg: Option<&str>) -> Event {
        if arg == Some("PreToolUse") {
            Event::PreToolUse
        } else {
            Event::PostToolUse
        }
    }
}

/// 훅 하나를 돌려 stdout 글을 돌려준다. 낼 것이 없거나 python 에서 예외가 나는 입력이면 `None`.
pub fn run(ctx: &Context, event: Event, input: &HookInput) -> Option<String> {
    let data = input.raw();
    let Some(Value::Dict(tool_input)) = data.get("tool_input") else {
        return None;
    };

    // 절대 경로 하나(file_path, 없으면 path)
    let path = [tool_input.get("file_path"), tool_input.get("path")]
        .into_iter()
        .flatten()
        .find(|v| v.truthy())?;
    let Value::Str(path) = path else {
        return None;
    };
    if !path.starts_with('/') || ctx.hook.env.get_os_nonempty("SESSION_LOG_NESTED").is_some() {
        return None;
    }
    let path = normpath(path);

    let output = match event {
        Event::PreToolUse => gate(ctx, data, tool_input, &path),
        Event::PostToolUse => notice(ctx, data, &path),
    };
    output
        .ok()
        .flatten()
        .map(|out| out.render(EnsureAscii::Yes))
}

// 저장소에 정해 둔 보관 폴더(.claude/session-log.json 의 records_home) 아래인가
fn in_records_home(ctx: &Context, data: &Dict, path: &str) -> Result<bool> {
    let root = match ctx.hook.env.get_os_nonempty("CLAUDE_PROJECT_DIR") {
        Some(dir) => from_os(dir),
        None => match data.get("cwd") {
            Some(Value::Str(cwd)) => cwd.clone(),
            Some(v) if v.truthy() => return Err(Abort("cwd is not a string")),
            _ => String::new(),
        },
    };
    if root.is_empty() || !path.starts_with(&format!("{}/", normpath(&root))) {
        return Ok(false);
    }
    let Some(home) = records_home::home_rel(&root) else {
        return Ok(false);
    };
    Ok(is_under(path, &join(&normpath(&root), &home)))
}

/// PreToolUse(Read): 큰 기록 통째 읽기를 막는다.
fn gate(ctx: &Context, data: &Dict, input: &Dict, path: &str) -> Result<Option<HookOutput>> {
    // 통째 읽기만, 나눠 읽을 수 있는 파일만
    let given = |key: &str| input.get(key).is_some_and(|v| *v != Value::Null);
    let read_whole = data.get("tool_name").and_then(Value::as_str) == Some("Read")
        && !given("offset")
        && !given("limit")
        && !input.get("pages").is_some_and(Value::truthy);
    if !read_whole || NOT_TEXT.contains(&splitext(path).1.to_lowercase().as_str()) {
        return Ok(None);
    }
    let config = ctx.config();
    if config.disabled() || config.read_gate_off() {
        return Ok(None);
    }

    // 기록 경로인가
    let env = &ctx.hook.env;
    let in_store = is_under(path, &config.home(env));
    let config_dirs = [claude_config_dir(env), home_claude_dir(env)];
    if !in_store && !is_snapshot(path, &config_dirs) && !in_records_home(ctx, data, path)? {
        return Ok(None);
    }

    // 크기
    let gate_kb = config.num(Key::ReadGateKb);
    if gate_kb <= 0.0 {
        return Ok(None);
    }
    let size = match fsx::getsize(path) {
        Ok(size) => size,
        Err(FsError::Os(_)) => return Ok(None),
        Err(FsError::Value) => return Err(Abort("unencodable path")),
    };
    if (size as f64) < gate_kb * 1024.0 {
        return Ok(None);
    }

    // 막고 나눠 읽기를 안내. python `int(gate_kb)` 는 NaN, 무한대에서 예외
    if !gate_kb.is_finite() {
        return Err(Abort("gate size is not finite"));
    }
    let coderag = !in_store && which("coderag", env).is_some();
    let text = messages::record_read_gate(
        size / 1024,
        &integral_float_text(gate_kb.trunc()),
        path,
        coderag,
    );
    let nonce_sid = truthy_str(data.get("session_id"), "session_id")?;
    let reason = messages::wrap(
        &text,
        Level::Action,
        ctx.nonce(nonce_sid.as_deref())?.as_ref(),
    );
    Ok(Some(HookOutput::deny(reason)))
}

/// PostToolUse(Read, Grep): 세션 기록을 읽었으면 스냅숏 경고를 회차마다 한 번.
fn notice(ctx: &Context, data: &Dict, path: &str) -> Result<Option<HookOutput>> {
    let config = ctx.config();
    if config.disabled() {
        return Ok(None);
    }
    if !is_under(path, &config.home(&ctx.hook.env)) && !in_records_home(ctx, data, path)? {
        return Ok(None);
    }
    let Some(sid) = truthy_str(data.get("session_id"), "session_id")? else {
        return Ok(None);
    };

    // (세션, 에이전트, 회차) 표식을 먼저 만든 쪽만 알린다. 못 만들면 알리지 않는다
    let agent = truthy_str(data.get("agent_id"), "agent_id")?;
    let marker = epoch::state_path(ctx.tempdir(), MARKER_DIR, &sid, agent.as_deref())?;
    let os = fsx::os_path(&marker).ok_or(Abort("unencodable marker"))?;
    let mut options = OpenOptions::new();
    options.write(true).create_new(true);
    #[cfg(unix)]
    std::os::unix::fs::OpenOptionsExt::mode(&mut options, 0o777);
    if options.open(os).is_err() {
        return Ok(None);
    }

    let text = messages::wrap(
        messages::RECORD_READ,
        Level::Info,
        ctx.nonce(Some(&sid))?.as_ref(),
    );
    Ok(Some(HookOutput::context("PostToolUse", text)))
}
