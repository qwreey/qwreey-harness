//! `hook subagent-slots`: 서브에이전트 고지와 away 슬롯(python `scripts/subagent-slots.py` 와 원장 `subagent_ledger.py`).
//!
//! 이벤트마다 갈래 하나다: PreToolUse(Agent, Task, Workflow) [`pre`], PostToolUse(모든 도구) [`post`], SubagentStart,
//! SubagentStop, Stop [`subagent`]. 세는 법: PreToolUse 에서 예약, PostToolUse(async_launched)와 SubagentStart 에서 실행 중,
//! SubagentStop 에서 뺀다. 어긋나면 [`ledger::live`] 가 바로잡는다.
//!
//! 평소(away 아님)의 PostToolUse 는 [`quick`] 이 원문만 보고 끝낸다. 원장을 고치는 동안의 어떤 실패도 아무것도 막지 않는다
//! (python 은 예외를 삼키고 원장을 쓰지 않는다). 원장을 열기 전의 몇 자리는 python 이 traceback 과 종료 코드 1 로 끝난다.

pub mod agents;
pub mod away;
pub mod call;
pub mod config;
pub mod ledger;
pub mod post;
pub mod pre;
pub mod quick;
pub mod spend;
pub mod store;
pub mod subagent;

use harness_hook::HookEnv;
use harness_hook::py::json_load::{self, Decode};
use harness_hook::py::value::{Dict, Value};
use harness_hook::settings::config_dir;

use crate::pyval::now;
use crate::stop::{Result, Stop};
use call::{Call, Out};
use config::Cfg;
use store::Session;

/// 훅 한 번이 끝나는 꼴.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Exit {
    /// 아무것도 내지 않고 0.
    Quiet,
    /// 이 JSON 글(끝 줄바꿈 없음)을 내고 0.
    Print(String),
    /// python 이 예외를 잡지 않는 자리: 출력 없이 종료 코드 1(stderr 의 traceback 은 옮기지 않는다).
    Crash,
}

/// 이 훅이 맡는 이벤트와 도구.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Handler {
    PreAgent,
    PreWorkflow,
    PostTool,
    SubagentStart,
    SubagentStop,
    Stop,
}

/// 훅 한 번.
pub fn run(hook: &HookEnv, raw: &[u8]) -> Exit {
    // The cheap path for every tool call while not away
    match quick::not_away(hook, raw) {
        Ok(true) => return Exit::Quiet,
        Ok(false) => {}
        Err(quick::Crash) => return Exit::Crash,
    }
    let off = hook
        .var("HARNESS_SUBAGENT_SLOTS")
        .is_some_and(|v| is_off_word(&v.to_lowercase()));
    if off && contains(raw, b"\"PostToolUse\"") {
        return Exit::Quiet;
    }

    // python _late(): the user config folder, or a traceback
    let Ok(home) = config_dir(&hook.env) else {
        return Exit::Crash;
    };
    let home = harness_hook::py::surrogate::from_os(home.as_os_str());
    let Ok(input) = json_load::from_bytes(raw, Decode::SurrogateEscape) else {
        return Exit::Quiet;
    };
    let Ok(input) = input.into_dict() else {
        return Exit::Crash;
    };

    // Which handler; tuple keys with a list or dict raise
    let handler = match handler_of(&input) {
        Ok(Some(handler)) => handler,
        Ok(None) => return Exit::Quiet,
        Err(()) => return Exit::Crash,
    };
    if handler == Handler::PostTool
        && !matches!(
            input.get("tool_name").and_then(Value::as_str),
            Some("Agent" | "Task")
        )
        && input.get("agent_id").is_some_and(Value::truthy)
    {
        return Exit::Quiet;
    }

    match account(hook, &input, handler, &home) {
        Ok(Some(out)) => Exit::Print(out.render()),
        Ok(None) | Err(_) => Exit::Quiet,
    }
}

fn is_off_word(word: &str) -> bool {
    matches!(word, "off" | "0" | "no")
}

fn contains(hay: &[u8], needle: &[u8]) -> bool {
    hay.windows(needle.len()).any(|w| w == needle)
}

// python HANDLERS.get((ev, tool_name)) or HANDLERS.get((ev, None)). 목록이나 dict 가 든 열쇠는 TypeError
fn handler_of(input: &Dict) -> std::result::Result<Option<Handler>, ()> {
    let event = input.get("hook_event_name");
    let tool = input.get("tool_name");
    for part in [event, tool].into_iter().flatten() {
        if matches!(part, Value::List(_) | Value::Dict(_)) {
            return Err(());
        }
    }

    let event = event.and_then(Value::as_str);
    let tool = tool.and_then(Value::as_str);
    Ok(match (event, tool) {
        (Some("PreToolUse"), Some("Agent" | "Task")) => Some(Handler::PreAgent),
        (Some("PreToolUse"), Some("Workflow")) => Some(Handler::PreWorkflow),
        (Some("PostToolUse"), _) => Some(Handler::PostTool),
        (Some("SubagentStart"), _) => Some(Handler::SubagentStart),
        (Some("SubagentStop"), _) => Some(Handler::SubagentStop),
        (Some("Stop"), _) => Some(Handler::Stop),
        _ => None,
    })
}

// python main 의 try 블록: 설정, 원장 잠금, 메인 사용량, 갈래, sweep, 원장 쓰기
fn account(hook: &HookEnv, input: &Dict, handler: Handler, home: &str) -> Result<Option<Out>> {
    let project = match hook.env.get_nonempty("CLAUDE_PROJECT_DIR") {
        Some(dir) => Some(Value::Str(dir.to_owned())),
        None => input.get("cwd").cloned(),
    };
    let cfg = Cfg::load(hook, project.as_ref());
    if is_off_word(&cfg.get("HARNESS_SUBAGENT_SLOTS", "on").to_lowercase()) {
        return Ok(None);
    }

    let tempdir = hook
        .tempdir()
        .ok_or(Stop::Raises("tempfile.gettempdir() found no folder"))?;
    let call = Call {
        hook,
        input,
        cfg: &cfg,
        tempdir,
        home,
        now: now(),
    };
    let (session, mut st) = Session::open(tempdir, input.get("session_id"))?;

    // Main's own usage before PreToolUse and Stop (a subagent's hooks leave main's offset alone)
    let is_main = !input.get("agent_id").is_some_and(Value::truthy);
    if is_main
        && matches!(
            handler,
            Handler::PreAgent | Handler::PreWorkflow | Handler::Stop
        )
    {
        ledger::account_main(&mut st, input.get("transcript_path"))?;
    }
    let out = match handler {
        Handler::PreAgent => pre::agent(&call, &mut st)?,
        Handler::PreWorkflow => pre::workflow(&call, &mut st)?,
        Handler::PostTool => post::tool(&call, &mut st)?,
        Handler::SubagentStart => subagent::start(&call, &mut st).map(|()| None)?,
        Handler::SubagentStop => subagent::stop(&call, &mut st).map(|()| None)?,
        Handler::Stop => subagent::reconcile(&call, &mut st).map(|()| None)?,
    };
    ledger::sweep(&mut st, call.now)?;
    session.save(&mut st)?;
    Ok(out)
}
