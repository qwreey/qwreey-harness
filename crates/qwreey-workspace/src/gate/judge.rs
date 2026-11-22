//! 도구 호출 하나가 다른 저장소를 건드리는가(python `workspace_gate.judge`, `paths_of`).

use harness_hook::HookInput;
use harness_hook::py::value::{Dict, Value};

use super::bash::{self, Kind};
use crate::context::Context;
use crate::paths::{Base, norm};
use crate::pyval::py_str;
use crate::scope::Scope;
use crate::stop::{Result, Stop};

/// 파일을 쓰는 도구(python `WRITE_TOOLS`).
pub const WRITE_TOOLS: &[&str] = &["Edit", "Write", "MultiEdit", "NotebookEdit"];
/// 파일을 읽는 도구(python `READ_TOOLS`).
pub const READ_TOOLS: &[&str] = &["Read", "Grep", "Glob"];

/// 다른 저장소를 건드린 호출.
pub struct Hit {
    pub kind: Kind,
    /// 다른 저장소 루트.
    pub repo: String,
    /// deny.log 에 남길 설명(명령 앞 200 자, 또는 `<도구> <경로>`).
    pub what: String,
}

/// python `judge(data, scope)`. 다른 저장소를 건드리지 않으면 `None`.
pub fn judge(ctx: &Context, input: &HookInput, scope: &Scope) -> Result<Option<Hit>> {
    let tool = input.tool_name().unwrap_or("");
    let empty = Dict::new();
    let ti = match input.get("tool_input") {
        Some(Value::Dict(d)) => d,
        Some(v) if v.truthy() => return Err(Stop::Raises("tool_input is not a dict")),
        _ => &empty,
    };
    let cwd: Base = match input.get("cwd") {
        Some(Value::Str(s)) if !s.is_empty() => Some(s),
        Some(v) if v.truthy() => None,
        _ => Some(&scope.project),
    };

    // Bash: classify the command
    if tool == "Bash" {
        let cmd = match ti.get("command") {
            Some(Value::Str(s)) => s.as_str(),
            Some(v) if v.truthy() => return Err(Stop::Raises("command is not a str")),
            _ => "",
        };
        let what: String = cmd.chars().take(200).collect();
        let verdict = bash::classify(ctx, cmd, cwd, scope)?;
        return Ok(verdict.map(|(kind, repo)| Hit { kind, repo, what }));
    }

    // File tools: the first path inside another repo
    let kind = if WRITE_TOOLS.contains(&tool) {
        Kind::Write
    } else if READ_TOOLS.contains(&tool) {
        Kind::Read
    } else {
        return Ok(None);
    };
    for p in paths_of(ctx, tool, ti, cwd)? {
        if let Some(repo) = scope.sibling(&p)? {
            let what = format!("{tool} {p}");
            return Ok(Some(Hit { kind, repo, what }));
        }
    }
    Ok(None)
}

// python paths_of: 경로 인자들, 읽기 도구는 `/`, `~` 로 시작하는 패턴도. 모두 norm 한 뒤 돌려준다
fn paths_of(ctx: &Context, tool: &str, ti: &Dict, cwd: Base) -> Result<Vec<String>> {
    let mut raw = Vec::new();
    for key in ["file_path", "notebook_path", "path"] {
        if let Some(v) = ti.get(key).filter(|v| v.truthy()) {
            raw.push(py_str(v));
        }
    }

    // 문자열이 아닌 값의 str() 은 `/`, `~` 로 시작하지 않는다
    if READ_TOOLS.contains(&tool) {
        for key in ["pattern", "glob"] {
            if let Some(Value::Str(s)) = ti.get(key)
                && s.starts_with(['/', '~'])
            {
                raw.push(s.clone());
            }
        }
    }

    raw.iter().map(|p| norm(ctx, p, cwd)).collect()
}
