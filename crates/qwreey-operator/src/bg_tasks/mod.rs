//! `hook subagent-bg-tasks`: 서브에이전트가 자기 백그라운드 작업을 돌려 둔 채 끝내려 하면 한 번 알린다
//! (python `hooks/subagent-bg-tasks.py`, warn).
//!
//! - 그 서브에이전트의 작업: 자기 트랜스크립트의 tool_result 에 id 가 나온 것([`transcript`]). 못 읽으면 알리지 않는다.
//!   그 가운데 status 가 running 이고 type 이 monitor 가 아닌 것.
//! - 통과: stop_hook_active, 남은 작업 없음, 빈 답이나 오류로 끝난 턴, agent_id 없음, 이미 알린 서브에이전트, 끄기 스위치.
//! - 한 번: (session_id, agent_id, compact 회차) 상태 파일을 O_EXCL 로 만든 쪽만 낸다.
//! - 끄기: `HARNESS_OPERATOR_SUBAGENT_BG=off`.

pub mod transcript;

use std::sync::LazyLock;

use harness_hook::HookEnv;
use harness_hook::epoch;
use harness_hook::output::HookOutput;
use harness_hook::py::fs::os_path;
use harness_hook::py::json::{EnsureAscii, to_string};
use harness_hook::py::re::Flags;
use harness_hook::py::repr::{str_value, truthy_str};
use harness_hook::py::text::{split_whitespace, strip};
use harness_hook::py::value::{Dict, Value};
use harness_hook::rx::Regex;

use crate::stop::{Result, Stop};
use crate::switch::switched_off;

/// 이 플러그인의 이름(compact 회차 폴더 `claude-qwreey-operator-epoch`).
const PLUGIN: &str = "qwreey-operator";
/// 알린 서브에이전트의 표지 폴더.
const NAMESPACE: &str = "claude-qwreey-operator-subagent-bg";
/// 끄기 스위치.
const SWITCH: &str = "HARNESS_OPERATOR_SUBAGENT_BG";
/// 작업 설명은 한 줄로 자른다(서브에이전트가 쓴 글이라 길이 제한이 없다).
const DESC_MAX: usize = 80;

// sync-copies 가 이 줄을 한 줄로 쓴다. rustfmt 가 접지 않게 한다
#[rustfmt::skip]
// @start-replace: lib/harness_texts.py#STOP_ERROR value=string template="const STOP_ERROR_PATTERN: &str = {value};"
const STOP_ERROR_PATTERN: &str = "^\\s*(API Error|Prompt is too long|Context limit|Request timed out|Credit balance)";
// @end-replace

static STOP_ERROR: LazyLock<Regex> =
    LazyLock::new(|| Regex::with_flags(STOP_ERROR_PATTERN, Flags::IGNORECASE));

const BODY_HEAD: &str =
    "You are about to finish while background work you started is still running:";
const BODY_TAIL: &str = "Collect their results, or stop them with TaskStop, unless your brief explicitly says to leave them running. \
                         Then give your final report again in full: your caller receives only your last message.";

/// 훅 한 번. 낼 JSON 글(끝 줄바꿈 없음) 또는 `None`.
pub fn run(hook: &HookEnv, input: &Dict) -> Result<Option<String>> {
    let truthy = |key: &str| input.get(key).filter(|v| v.truthy());
    if input.get("hook_event_name").and_then(Value::as_str) != Some("SubagentStop")
        || truthy("stop_hook_active").is_some()
    {
        return Ok(None);
    }
    let (Some(sid), Some(aid)) = (truthy("session_id"), truthy("agent_id")) else {
        return Ok(None);
    };

    // A turn that ended empty or on an error is not a report
    if let Some(Value::Str(msg)) = input.get("last_assistant_message")
        && (strip(msg).is_empty() || STOP_ERROR.match_start(msg).is_some())
    {
        return Ok(None);
    }

    // Running tasks this subagent started
    let mut tasks = running_tasks(input);
    if !tasks.is_empty() {
        tasks = own_tasks(input, tasks)?;
    }
    if tasks.is_empty() || switched_off(hook, SWITCH, input.get("cwd"))? || !claim(hook, sid, aid)?
    {
        return Ok(None);
    }

    // One warn tag with a line per task
    let attr = hook
        .nonce_attr(Some(sid))
        .map_err(|_| Stop::Raises("session id has a lone surrogate"))?;
    let lines: Vec<String> = tasks.iter().map(|t| task_line(t)).collect::<Result<_>>()?;
    let body = format!("{BODY_HEAD}\n{}\n{BODY_TAIL}", lines.join("\n"));
    let text = format!(
        "<harness-hook name=\"subagent-bg-tasks\" level=\"warn\"{attr}>\n{body}\n</harness-hook>"
    );
    Ok(Some(
        HookOutput::context("SubagentStop", text).render(EnsureAscii::No),
    ))
}

/// python `running_tasks`: 실행 중이고 monitor 가 아니며 id 가 글인(자기 자신이 아닌) 작업.
fn running_tasks(input: &Dict) -> Vec<&Dict> {
    let Some(Value::List(tasks)) = input.get("background_tasks") else {
        return Vec::new();
    };
    let me = input.get("agent_id");
    tasks
        .iter()
        .filter_map(Value::as_dict)
        .filter(|t| t.get("status").and_then(Value::as_str) == Some("running"))
        .filter(|t| t.get("type").and_then(Value::as_str) != Some("monitor"))
        .filter(|t| match t.get("id") {
            Some(Value::Str(id)) => !id.is_empty() && me.and_then(Value::as_str) != Some(id),
            _ => false,
        })
        .collect()
}

/// python `own_tasks`: 자기 tool_result 에 id 가 나온 작업.
fn own_tasks<'a>(input: &Dict, tasks: Vec<&'a Dict>) -> Result<Vec<&'a Dict>> {
    let text = transcript::tool_result_text(input.get("agent_transcript_path"))?;
    let Some(text) = text.filter(|t| !t.is_empty()) else {
        return Ok(Vec::new());
    };
    Ok(tasks
        .into_iter()
        .filter(|t| {
            let id = t.get("id").and_then(Value::as_str).unwrap_or("");
            transcript::mentions(&text, id)
        })
        .collect())
}

/// 이 서브에이전트에게 처음이면 참. 상태 파일을 O_EXCL 로 만들어 병렬로 불려도 한 번만 낸다.
fn claim(hook: &HookEnv, sid: &Value, aid: &Value) -> Result<bool> {
    let tempdir = hook
        .tempdir()
        .ok_or(Stop::Raises("tempfile.gettempdir() found no folder"))?;
    let path = epoch::state_path(
        tempdir,
        PLUGIN,
        NAMESPACE,
        &str_value(sid),
        Some(&str_value(aid)),
    )
    .map_err(|_| Stop::Raises("cannot make the state folder"))?;

    let os = os_path(&path).ok_or(Stop::Raises("bad state path"))?;
    let mut options = std::fs::OpenOptions::new();
    options.write(true).create_new(true);
    #[cfg(unix)]
    std::os::unix::fs::OpenOptionsExt::mode(&mut options, 0o600);
    match options.open(os) {
        Ok(_) => Ok(true),
        Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => Ok(false),
        Err(_) => Err(Stop::Raises("os.open of the claim file failed")),
    }
}

/// python `one_line(value)`: 공백을 하나로, 80 자를 넘으면 77 자와 `...`.
fn one_line(value: Option<&Value>) -> String {
    let text = truthy_str(value);
    let joined = split_whitespace(&text).collect::<Vec<_>>().join(" ");
    if joined.chars().count() <= DESC_MAX {
        return joined;
    }
    let head: String = joined.chars().take(DESC_MAX - 3).collect();
    format!("{head}...")
}

/// python `task_line(t)`: `- <type> <id>: "<설명>"`(설명은 JSON 글).
fn task_line(task: &Dict) -> Result<String> {
    let first = |keys: &[&str]| {
        keys.iter()
            .map(|k| task.get(k))
            .find(|v| v.is_some_and(Value::truthy))
            .flatten()
            .or_else(|| task.get(keys[keys.len() - 1]))
    };
    let desc = one_line(first(&["description", "name", "agent_type"]));
    let kind = match task.get("type").filter(|v| v.truthy()) {
        Some(v) => one_line(Some(v)),
        None => "task".to_owned(),
    };
    let quoted = to_string(&desc, EnsureAscii::No).map_err(|_| Stop::Raises("json.dumps"))?;
    Ok(format!("- {kind} {}: {quoted}", one_line(task.get("id"))))
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 설명은 공백을 하나로 모으고 80 자에서 자른다.
    #[test]
    fn one_line_folds_and_cuts() {
        assert_eq!(one_line(Some(&Value::Str(" a \n b\t".into()))), "a b");
        let long = Value::Str("x".repeat(81));
        assert_eq!(one_line(Some(&long)), format!("{}...", "x".repeat(77)));
        assert_eq!(one_line(Some(&Value::Int(0))), "");
    }

    /// 설명이 없으면 name, agent_type 순서로, 따옴표는 JSON escape 다.
    #[test]
    fn task_line_like_python() {
        let task = Dict::from_pairs(vec![
            ("id".to_owned(), Value::Str("b1".into())),
            ("type".to_owned(), Value::Str("shell".into())),
            ("description".to_owned(), Value::Str(String::new())),
            ("name".to_owned(), Value::Str("say \"hi\"".into())),
        ]);
        assert_eq!(task_line(&task).unwrap(), r#"- shell b1: "say \"hi\"""#);
    }
}
