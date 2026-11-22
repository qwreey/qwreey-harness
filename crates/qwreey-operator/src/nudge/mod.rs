//! `hook delegate-nudge`: 메인 세션이 한 턴에 코드를 많이 직접 쓰면 백그라운드 서브에이전트 위임을 권한다
//! (python `hooks/delegate-nudge.py`, info, 막지 않음).
//!
//! - 센다: 메인(입력에 agent_id 없음)의 Edit, Write, MultiEdit, NotebookEdit 와 코드 경로에 쓰는 Bash([`bash`]).
//! - 문턱: 한 턴에 쓰기 12회 또는 서로 다른 파일 8개(`HARNESS_OPERATOR_NUDGE_WRITES`, `_FILES`). 넘으면 턴당 한 번.
//! - 되돌림: UserPromptSubmit, Agent, Task, Workflow 호출. 직전 턴이 문턱을 넘었으면 UserPromptSubmit 이 이월 알림을 한 번 낸다.
//! - 끄기: `HARNESS_OPERATOR_NUDGE=off`. 층은 셀 만한 호출에서만 읽는다(PostToolUse 는 모든 도구 호출마다 돈다).

pub mod bash;
pub mod paths;
pub mod state;

use harness_hook::HookEnv;
use harness_hook::py::fs::exists;
use harness_hook::py::json::{EnsureAscii, dumps_dict};
use harness_hook::py::num::parse_int_saturating;
use harness_hook::py::repr::str_value;
use harness_hook::py::value::{Dict, Value};
use harness_hook::tag::Level;

use crate::stop::{Result, Stop};
use crate::switch::switched_off;
use paths::{WRITE_TOOLS, written_paths};

/// 끄기 스위치.
const SWITCH: &str = "HARNESS_OPERATOR_NUDGE";
/// 문턱을 바꾸는 환경 변수와 기본값.
const WRITES: (&str, i128) = ("HARNESS_OPERATOR_NUDGE_WRITES", 12);
const FILES: (&str, i128) = ("HARNESS_OPERATOR_NUDGE_FILES", 8);
/// 턴을 서브에이전트에게 넘긴 것으로 보는 도구.
const RESET_TOOLS: &[&str] = &["Agent", "Task", "Workflow"];

const NUDGE: &str = "Main has written code {n} times across {m} files this turn without a subagent. If what remains is mostly \
                     implementation, a background subagent frees you to talk with the user; \
                     stay if it is nearly done or needs the user midway.";
const CARRY: &str = "Last turn main wrote code {n} times in {m} files directly. If this prompt continues that work and much \
                     implementation remains, consider handing it to a background subagent; carry on in main if it is nearly done.";

/// 입력의 `tool_name`. python 은 집합에 넣어 보므로 목록과 dict 는 TypeError 다.
enum Tool<'a> {
    Name(&'a str),
    Other,
    Unhashable,
}

impl Tool<'_> {
    fn of(value: Option<&Value>) -> Tool<'_> {
        match value {
            Some(Value::Str(name)) => Tool::Name(name),
            Some(Value::List(_) | Value::Dict(_)) => Tool::Unhashable,
            _ => Tool::Other,
        }
    }

    // python `tool in names`
    fn is_in(&self, names: &[&str]) -> Result<bool> {
        match self {
            Tool::Name(name) => Ok(names.contains(name)),
            Tool::Other => Ok(false),
            Tool::Unhashable => Err(Stop::Raises("unhashable tool_name in a set")),
        }
    }
}

/// 훅 한 번. 낼 JSON 글(끝 줄바꿈 없음) 또는 `None`.
pub fn run(hook: &HookEnv, input: &Dict) -> Result<Option<String>> {
    if input.get("agent_id").is_some_and(Value::truthy) {
        return Ok(None);
    }

    // Most tool calls end before the state is opened
    let event = input.get("hook_event_name").and_then(Value::as_str);
    let tool = Tool::of(input.get("tool_name"));
    let is_bash = matches!(tool, Tool::Name("Bash"));
    if event == Some("PostToolUse")
        && !tool.is_in(WRITE_TOOLS)?
        && !is_bash
        && !tool.is_in(RESET_TOOLS)?
    {
        return Ok(None);
    }
    if switched_off(hook, SWITCH, input.get("cwd"))? {
        return Ok(None);
    }

    // State of this session
    let tempdir = hook
        .tempdir()
        .ok_or(Stop::Raises("tempfile.gettempdir() found no folder"))?;
    let path = state::path(tempdir, input.get("session_id"));
    let mut st = state::load(&path)?;

    let out = if event == Some("UserPromptSubmit") {
        let carried = carry_notice(hook, input, &st)?;
        st = Dict::new();
        carried
    } else if tool.is_in(RESET_TOOLS)? {
        st = Dict::new();
        None
    } else {
        let Tool::Name(name) = tool else {
            return Ok(None);
        };
        let written = written_paths(hook, name, input)?;
        if written.is_empty() {
            return Ok(None);
        }
        count_writes(hook, input, &mut st, &written)?
    };

    if !st.is_empty() || exists(&path) {
        state::save(&path, &st)?;
    }
    Ok(out)
}

// 직전 턴이 문턱을 넘었으면 이월 알림
fn carry_notice(hook: &HookEnv, input: &Dict, st: &Dict) -> Result<Option<String>> {
    if !st.get("crossed").is_some_and(Value::truthy) {
        return Ok(None);
    }
    let n = str_value(st.get("n").unwrap_or(&Value::Int(0)));
    let files = state::py_len(st.get("files").unwrap_or(&Value::List(Vec::new())))?;
    let body = CARRY.replace("{n}", &n).replace("{m}", &files.to_string());
    let event = Value::Str("UserPromptSubmit".to_owned());
    message(hook, input, event, &body).map(Some)
}

// 쓰기를 세고, 이 턴에 처음 문턱을 넘으면 알림
fn count_writes(
    hook: &HookEnv,
    input: &Dict,
    st: &mut Dict,
    written: &[Value],
) -> Result<Option<String>> {
    let files = state::merged_files(st.get("files"), written)?;
    let n = state::next_count(st)?;
    let file_count = files.len();
    st.insert("n", n.clone());
    st.insert("files", Value::List(files));

    // Threshold, once per turn
    let crossed = st.get("crossed").is_some_and(Value::truthy);
    if crossed
        || !(state::reaches(&n, threshold(hook, WRITES))
            || file_count as i128 >= threshold(hook, FILES))
    {
        return Ok(None);
    }
    st.insert("crossed", Value::Bool(true));
    let body = NUDGE
        .replace("{n}", &str_value(&n))
        .replace("{m}", &file_count.to_string());
    let event = input.get("hook_event_name").cloned().unwrap_or(Value::Null);
    message(hook, input, event, &body).map(Some)
}

// python `max(1, int(os.environ.get(name, default)))`, 읽지 못하면 기본값. i128 을 넘는 수는 끝 값이다
fn threshold(hook: &HookEnv, (name, default): (&str, i128)) -> i128 {
    hook.var(name)
        .and_then(|text| parse_int_saturating(&text))
        .map_or(default, |n| n.max(1))
}

// info 태그 하나를 additionalContext 로(python `message`). event 는 입력 값 그대로 쓴다(없으면 null)
fn message(hook: &HookEnv, input: &Dict, event: Value, body: &str) -> Result<String> {
    let attr = hook
        .nonce_attr(input.get("session_id"))
        .map_err(|_| Stop::Raises("session id has a lone surrogate"))?;
    let inner = Dict::from_pairs(vec![
        ("hookEventName".to_owned(), event),
        (
            "additionalContext".to_owned(),
            Value::Str(tag_with_attr(&attr, body)),
        ),
    ]);
    let outer = Dict::from_pairs(vec![("hookSpecificOutput".to_owned(), Value::Dict(inner))]);
    Ok(dumps_dict(&outer, EnsureAscii::No, None))
}

fn tag_with_attr(attr: &str, body: &str) -> String {
    format!(
        "<harness-hook name=\"delegate-nudge\" level=\"{}\"{attr}>\n{body}\n</harness-hook>",
        Level::Info.as_str()
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use harness_hook::Env;
    use harness_hook::tag::harness_hook as tag;

    /// 태그는 harness-hook 의 꼴과 같다.
    #[test]
    fn tag_matches_the_shared_form() {
        assert_eq!(
            tag_with_attr("", "b"),
            tag("delegate-nudge", Level::Info, None, "b")
        );
    }

    /// 문턱 환경 변수: 0 이하는 1, 읽지 못하면 기본값, i128 을 넘으면 닿지 않는 값.
    #[test]
    fn thresholds_like_python() {
        let with = |v: &str| {
            HookEnv::new(
                Env::from_pairs([("HARNESS_OPERATOR_NUDGE_WRITES", v)]),
                None,
            )
        };
        assert_eq!(threshold(&with(" 3 "), WRITES), 3);
        assert_eq!(threshold(&with("-4"), WRITES), 1);
        assert_eq!(threshold(&with("x"), WRITES), 12);
        assert_eq!(threshold(&with(&"9".repeat(60)), WRITES), i128::MAX);
        assert_eq!(threshold(&with(&format!("-{}", "9".repeat(60))), WRITES), 1);
    }
}
