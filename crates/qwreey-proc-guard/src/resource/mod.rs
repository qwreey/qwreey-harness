//! resource-guard(PreToolUse, PostToolUse, PostToolUseFailure Bash): 디스크 여유 공간과 명령이 남긴 core dump 를 알린다
//! (`hooks/resource-guard.py`).
//!
//! 디스크: 명령 앞뒤로 cwd 와 임시 폴더의 파일 시스템을 잰다. 여유가 문턱 아래거나 명령 중 크게 줄면 warn, 같은 경고는 세션에 한 번.
//! core dump(Linux): 명령 뒤에 Pre 시각 이후 생긴 core 를 찾는다([`core`]). 프로그램이 명령에 있거나 명령이 크래시했고 프로그램을
//! 모르면 지우라는 action, 그 밖은 남기고 알리라는 warn.
//! 막지 않는다. 어떤 실패든 아무것도 내지 않는다. 하위 프로세스를 띄우지 않는다. 상태 파일은 [`state`].

pub mod config;
pub mod core;
pub mod disk;
pub mod num;
pub mod report;
pub mod state;

use std::time::{SystemTime, UNIX_EPOCH};

use harness_hook::py::value::{Dict, Value};
use harness_hook::settings::{self, Project};
use harness_hook::tag::{Level, Notices};
use harness_hook::{HookInput, HookOutput};

use crate::context::{Context, py_str};
use config::{ENV_DEFAULTS, ENV_USER_ONLY, switch, thresholds};
use core::Found;

const TAG: &str = "resource-guard";
const EVENTS: &[&str] = &["PreToolUse", "PostToolUse", "PostToolUseFailure"];
const PRE_TTL_SEC: f64 = 86400.0;
const SESSION_TTL_SEC: f64 = 7.0 * 86400.0;
const REPORTED_KEEP: usize = 50;

/// python 판에서 예외가 나는 자리. 훅은 아무것도 내지 않고 끝난다(그 전에 쓴 상태 파일은 남는다).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Abort;

/// 훅 하나를 돌린다.
pub fn run(ctx: &Context, input: &HookInput) -> Option<HookOutput> {
    let text = handle(ctx, input).ok().flatten()?;
    let event = input.hook_event_name()?;
    Some(HookOutput::context(event, text))
}

/// additionalContext 글, 낼 것이 없으면 `None`.
pub fn handle(ctx: &Context, input: &HookInput) -> Result<Option<String>, Abort> {
    let raw = input.raw();
    let env = &ctx.env;
    match raw.get("tool_name") {
        None | Some(serde_json::Value::Null) => {}
        Some(serde_json::Value::String(s)) if s == "Bash" => {}
        Some(_) => return Ok(None),
    }
    let Some(event) = input.hook_event_name().filter(|e| EVENTS.contains(e)) else {
        return Ok(None);
    };
    let cwd = match input.cwd().filter(|c| !c.is_empty()) {
        Some(c) => c.to_owned(),
        None => current_dir()?,
    };

    // 설정: 스위치는 모든 층, 문턱은 저장소 층이 엄하게만
    let all = ctx.layers(
        settings::project_dir(env, Some(&cwd)),
        ENV_DEFAULTS,
        ENV_USER_ONLY,
    );
    let (disk_on, core_on) = (
        switch(&all, "PROC_GUARD_DISK"),
        switch(&all, "PROC_GUARD_CORE"),
    );
    if !(disk_on || core_on) {
        return Ok(None);
    }
    let limits = thresholds(
        &all,
        &ctx.layers(Project::Skip, ENV_DEFAULTS, ENV_USER_ONLY),
    );

    // 재기(잠금 밖에서)
    let disk = if disk_on {
        let tmp = harness_hook::py::tempfile::gettempdir(env).ok_or(Abort)?;
        disk::measure(&[&cwd, &tmp])
    } else {
        Vec::new()
    };
    let key = state::session_key(raw.get("session_id"));
    let pre_path = match state::tool_use_key(raw.get("tool_use_id")) {
        Some(tid) => Some(state::pre_path(&state::state_dir(env)?, &key, &tid)),
        None => None,
    };

    // Pre: 측정을 Post 에 남긴다. Post: 그것과 견주고 core 를 찾는다
    let mut info = Vec::new();
    let (before, when, cores) = if event == "PreToolUse" {
        if let Some(pp) = &pre_path {
            write_pre(env, pp, &cwd, &disk)?;
        }
        (None, "before this command", Vec::new())
    } else {
        let pre = pre_path
            .as_deref()
            .map(state::read_json)
            .unwrap_or_default();
        if let Some(pp) = &pre_path {
            let _ = std::fs::remove_file(pp);
        }
        let cores = if core_on && state::state_trusted(env)? {
            core_scan(raw, &pre, &cwd, &mut info)
        } else {
            Vec::new()
        };
        (pre.get("disk").cloned(), "after this command", cores)
    };

    // 이 세션의 기록과 견줘 되풀이를 뺀다(잠금 안에서)
    let spath = state::join(&state::state_dir(env)?, &format!("s-{key}.json"));
    let (lines, kinds, cores) = {
        let _lock = state::lock(&format!("{spath}.lock"));
        let mut session = state::read_json(&spath);
        let loaded = session.clone();
        let (lines, kinds) = disk::findings(&disk, before.as_ref(), limits, &mut session, when)?;
        let cores = unreported(cores, &mut session)?;
        if !session.same_content(&loaded) {
            state::write_json(&spath, &session);
        }
        (lines, kinds, cores)
    };

    // core 를 이 명령과 이어 주는 것으로 가른다
    let command = command_text(raw)?;
    let crashed = !report::crash_evidence(raw).is_empty();
    let (mine, others): (Vec<&Found>, Vec<&Found>) = cores.iter().partition(|c| {
        report::program_in_command(&c.info, &command)
            || (crashed && c.info.program.is_empty() && c.info.args.is_empty())
    });

    // level 마다 태그 하나
    let mut notices = Notices::new();
    if !mine.is_empty() {
        notices.push(Level::Action, report::core_action(&mine));
    }
    if !lines.is_empty() {
        for line in lines {
            notices.push(Level::Warn, line);
        }
        notices.push(Level::Warn, disk::advice(&kinds));
    }
    if !others.is_empty() {
        notices.push(Level::Warn, report::core_notice(&others));
    }
    for line in info {
        notices.push(Level::Info, line);
    }
    if notices.is_empty() {
        return Ok(None);
    }
    Ok(Some(notices.render(TAG, ctx.nonce(input).as_ref())))
}

fn current_dir() -> Result<String, Abort> {
    let dir = std::env::current_dir().map_err(|_| Abort)?;
    dir.into_os_string().into_string().map_err(|_| Abort)
}

fn now_ns() -> i128 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_or(0, |d| d.as_nanos() as i128)
}

// Pre 기록을 쓰고, 하루 지난 Pre 기록과 일주일 지난 세션 기록을 지운다
fn write_pre(
    env: &harness_hook::Env,
    pp: &str,
    cwd: &str,
    disk: &[disk::Reading],
) -> Result<(), Abort> {
    let mut record = Dict::new();
    record.insert("t_ns", Value::Int(now_ns()));
    record.insert("cwd", Value::Str(cwd.to_owned()));
    record.insert("disk", Value::Dict(disk::to_dict(disk)));
    state::write_json(pp, &record);

    let now = state::secs(SystemTime::now());
    state::prune(&state::dirname(pp), PRE_TTL_SEC, now);
    state::prune(&state::state_dir(env)?, SESSION_TTL_SEC, now);
    Ok(())
}

// Pre 이후 생긴 core 목록. core_pattern 이 처리기면 info 에 안내를 더하고 빈 목록
fn core_scan(
    raw: &serde_json::Map<String, serde_json::Value>,
    pre: &Dict,
    cwd: &str,
    info: &mut Vec<String>,
) -> Vec<Found> {
    let Some((pattern, uses_pid)) = core::read_core_pattern() else {
        return Vec::new();
    };

    // Pre 시각, 없으면 지금에서 명령 시간을 뺀 시각(python 에서 bool 도 int 다)
    let since_ns = match pre.get("t_ns") {
        Some(Value::Int(t)) => *t,
        Some(Value::Bool(b)) => i128::from(*b),
        _ => match raw.get("duration_ms") {
            Some(serde_json::Value::Number(n)) => {
                now_ns() - (n.as_f64().unwrap_or(0.0) * 1e6) as i128
            }
            Some(serde_json::Value::Bool(b)) => now_ns() - i128::from(*b) * 1_000_000,
            _ => return Vec::new(),
        },
    };

    let evidence = report::crash_evidence(raw);
    if pattern.starts_with('|') {
        if !evidence.is_empty() {
            info.push(report::handler_message(&pattern, &evidence));
        }
        return Vec::new();
    }

    let mut roots = vec![cwd];
    if let Some(Value::Str(pre_cwd)) = pre.get("cwd")
        && pre_cwd != cwd
    {
        roots.push(pre_cwd);
    }
    core::find_cores(
        &roots,
        &pattern,
        uses_pid,
        since_ns,
        !evidence.is_empty(),
        my_uid(),
    )
}

#[cfg(unix)]
fn my_uid() -> Option<u32> {
    Some(rustix::process::getuid().as_raw())
}

#[cfg(not(unix))]
fn my_uid() -> Option<u32> {
    None
}

// 이 세션이 아직 알리지 않은 core 만. 알린 것은 state["cores"] 에 "경로:mtime_ns" 로 남긴다(겹쳐 돈 다른 Post 가 다시 알리지 않게)
fn unreported(cores: Vec<Found>, session: &mut Dict) -> Result<Vec<Found>, Abort> {
    // python `list(state.get("cores") or [])`
    let mut reported: Vec<Value> = match session.get("cores") {
        Some(v) if !v.truthy() => Vec::new(),
        None => Vec::new(),
        Some(Value::List(items)) => items.clone(),
        Some(Value::Str(s)) => s.chars().map(|c| Value::Str(c.to_string())).collect(),
        Some(Value::Dict(d)) => d.iter().map(|(k, _)| Value::Str(k.to_owned())).collect(),
        Some(_) => return Err(Abort),
    };

    let mut out = Vec::new();
    for c in cores {
        let key = Value::Str(format!("{}:{}", c.path, c.mtime_ns));
        if !reported.contains(&key) {
            reported.push(key);
            out.push(c);
        }
    }
    if !out.is_empty() {
        let keep = reported.split_off(reported.len().saturating_sub(REPORTED_KEEP));
        session.insert("cores", Value::List(keep));
    }
    Ok(out)
}

// python `str((data.get("tool_input") or {}).get("command") or "")`. 참인 tool_input 이 dict 가 아니면 예외
fn command_text(raw: &serde_json::Map<String, serde_json::Value>) -> Result<String, Abort> {
    let tool_input = match raw.get("tool_input") {
        Some(v) if crate::context::truthy(v) => v.as_object().ok_or(Abort)?,
        _ => return Ok(String::new()),
    };
    Ok(tool_input
        .get("command")
        .and_then(py_str)
        .unwrap_or_default())
}
