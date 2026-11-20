//! `hook readonly-for-reviewers`: 이 플러그인의 리뷰어에게만 읽기 전용 가드를 건다(python `hooks/readonly-for-reviewers.py`
//! 와 그것이 띄우는 `hooks/auditor-readonly-guard.py`).
//!
//! 막는 훅이다. 종료 코드는 python 과 같다: 2 는 막음(사유는 stderr), 0 은 통과, 1 은 python 이 예외로 끝나는 입력
//! (python 은 traceback 과 함께 1 로 끝나고 Claude Code 는 그것을 막지 않는 오류로 본다). 사유 글도 python 과 같은 바이트다.

mod bash;
mod scratch;
mod syntax;

use harness_hook::py::json_load::{self, Decode};
use harness_hook::py::surrogate::from_os;
use harness_hook::py::value::{Dict, Value};

use crate::context::Context;
use crate::outcome::Outcome;
use crate::pylib::repr::repr_str;

use scratch::Scratch;

/// 이 플러그인의 리뷰어 agent_type(플러그인 이름공간과 예전 이름).
const REVIEWERS: &[&str] = &["qwreey-advisor:reviewer", "qwreey-advisor-reviewer"];
const EDIT_TOOLS: &[&str] = &["Write", "Edit", "MultiEdit", "NotebookEdit"];

/// 가드의 판정.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Verdict {
    Pass,
    /// 막는다. 값은 사유 문장(태그와 끝 안내는 [`Guard::deny_text`] 가 단다).
    Deny(String),
    /// python 이 예외로 끝나는 입력(종료 코드 1). 값은 stderr 에 쓸 이유.
    Crash(&'static str),
}

/// `raw` 는 훅 stdin 바이트다(python 은 그 글을 가드에 그대로 넘긴다).
pub fn run(ctx: &Context, raw: &[u8]) -> Outcome {
    // Unreadable input passes
    let Ok(value) = json_load::from_bytes(raw, Decode::SurrogateEscape) else {
        return Outcome::quiet();
    };

    // Only this plugin's reviewers are guarded
    let empty = Dict::new();
    let data = match &value {
        v if !v.truthy() => &empty,
        Value::Dict(d) => d,
        _ => return crash("hook input is not an object"),
    };
    match data.get("agent_type").filter(|v| v.truthy()) {
        None => return Outcome::quiet(),
        Some(Value::Str(agent)) if REVIEWERS.contains(&agent.as_str()) => {}
        Some(Value::List(_) | Value::Dict(_)) => return crash("agent_type is unhashable"),
        Some(_) => return Outcome::quiet(),
    }

    // python hands the text to the guard as strict UTF-8
    if std::str::from_utf8(raw).is_err() {
        return crash("hook input is not UTF-8");
    }

    let guard = Guard::new(ctx, data);
    match guard.check(data) {
        Verdict::Pass => Outcome::quiet(),
        Verdict::Deny(msg) => Outcome::stderr_line(2, &guard.deny_text(&msg)),
        Verdict::Crash(why) => crash(why),
    }
}

fn crash(why: &str) -> Outcome {
    Outcome::stderr_line(1, &format!("readonly-for-reviewers: {why}"))
}

/// 한 호출의 가드: 스크래치 폴더와 nonce 속성.
pub struct Guard {
    scratch: Scratch,
    nonce_attr: String,
}

impl Guard {
    /// 환경(`CLAUDE_AUDIT_SCRATCH`)과 입력의 session_id 로 만든다. nonce 를 만들지 못하면 python 처럼 속성 없이.
    pub fn new(ctx: &Context, data: &Dict) -> Guard {
        let base = ctx
            .env
            .get_os("CLAUDE_AUDIT_SCRATCH")
            .map_or_else(|| "/tmp/claude-audit".to_owned(), from_os);
        let nonce_attr = ctx.nonce_attr(data.get("session_id")).unwrap_or_default();
        Guard {
            scratch: Scratch::new(base, &ctx.env),
            nonce_attr,
        }
    }

    /// python `deny(msg)` 가 stderr 에 쓰는 글(끝 줄바꿈 빼고).
    pub fn deny_text(&self, msg: &str) -> String {
        format!(
            "<harness-hook name=\"auditor-readonly-guard\" level=\"action\"{}>\n{msg}. Reviewers are read-only: \
             make probes only inside {}/<run>/.\n</harness-hook>",
            self.nonce_attr,
            self.scratch.base()
        )
    }

    /// python `main()` 의 판정.
    pub fn check(&self, data: &Dict) -> Verdict {
        // Fields python reads up front
        let tool = match data.get("tool_name") {
            None => "",
            Some(Value::Str(s)) => s.as_str(),
            Some(_) => return Verdict::Crash("tool_name has no startswith"),
        };
        let tool_input = data.get("tool_input").filter(|v| v.truthy());
        let Some(cwd) = cwd_of(data) else {
            return Verdict::Crash("cannot read the current directory");
        };

        // Studio MCP is off limits
        if tool.starts_with("mcp__roblox-studio") {
            return Verdict::Deny(
                "Roblox Studio MCP is not allowed for reviewers; report it as 'needs a Studio measurement'"
                    .to_owned(),
            );
        }

        // Edits only inside the scratch folder
        if EDIT_TOOLS.contains(&tool) {
            let ti = match tool_input {
                None => &Dict::new(),
                Some(Value::Dict(d)) => d,
                Some(_) => return Verdict::Crash("tool_input has no get"),
            };
            return self.check_edit(tool, ti, &cwd);
        }

        // Bash commands
        if tool == "Bash" {
            let command = match tool_input {
                None => "",
                Some(Value::Dict(d)) => match d.get("command") {
                    None => "",
                    Some(Value::Str(s)) => s.as_str(),
                    Some(_) => return Verdict::Crash("command is not a string"),
                },
                Some(_) => return Verdict::Crash("tool_input has no get"),
            };
            return bash::check(&self.scratch, command, &cwd);
        }
        Verdict::Pass
    }

    fn check_edit(&self, tool: &str, ti: &Dict, cwd: &Cwd) -> Verdict {
        let path = ti
            .get("file_path")
            .filter(|v| v.truthy())
            .or_else(|| ti.get("notebook_path").filter(|v| v.truthy()));
        let path = match path {
            None => "",
            Some(Value::Str(s)) => s.as_str(),
            Some(_) => return Verdict::Crash("file_path is not a string"),
        };

        match self.scratch.contains(path, cwd) {
            Ok(true) => Verdict::Pass,
            Ok(false) => Verdict::Deny(format!(
                "{tool} target {} is outside the scratch folder",
                repr_str(path)
            )),
            Err(why) => Verdict::Crash(why),
        }
    }
}

/// python `data.get("cwd") or os.getcwd()`: 글이 아닌 값은 쓰일 때 python 이 TypeError 를 낸다.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Cwd {
    Text(String),
    NotText,
}

// os.getcwd() 를 읽지 못하면 python 은 그 줄에서 예외로 끝난다
fn cwd_of(data: &Dict) -> Option<Cwd> {
    match data.get("cwd").filter(|v| v.truthy()) {
        Some(Value::Str(s)) => Some(Cwd::Text(s.clone())),
        Some(_) => Some(Cwd::NotText),
        None => {
            let dir = std::env::current_dir().ok()?;
            Some(Cwd::Text(from_os(dir.as_os_str())))
        }
    }
}
