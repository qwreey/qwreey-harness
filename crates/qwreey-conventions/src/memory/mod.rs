//! memory-placement(python `hooks/memory-placement.py`): auto memory 에 쓴 글이 저장소 지식으로 보이면 알린다.
//!
//! PostToolUse(Write, Edit, MultiEdit)에서 돈다. `file_path` 가 auto memory 폴더 안의 `.md`(MEMORY.md 말고)일 때만
//! 디스크 글을 [`signals`] 로 가른다. 같은 파일은 (session_id, 호출한 쪽, compact 회차)마다 한 번만 알린다.
//! python 판은 본문 전체를 `try/except Exception` 으로 감싸, 어떤 예외든 아무것도 내지 않고 0 으로 끝난다.
//! 출력은 `print(json.dumps(out))`(ensure_ascii, 끝 줄바꿈)와 같다.

mod location;
mod signals;

use harness_hook::HookInput;
use harness_hook::epoch;
use harness_hook::output::{EnsureAscii, HookOutput};
use harness_hook::py::fs;
use harness_hook::py::json::dumps;
use harness_hook::py::json_load::loads;
use harness_hook::py::path::{basename, pathlib_str};
use harness_hook::py::value::{Dict, Value};

use crate::context::{Context, PLUGIN};
use crate::halt::{Halt, Result};
use crate::pyval;

/// 상태 폴더 이름(python `NS`).
const NAMESPACE: &str = "claude-memory-placement";
/// 이만큼(글자)까지만 가른다.
const MAX_CHARS: usize = 200_000;

/// 훅 하나를 돌려 stdout 글을 돌려준다.
pub fn run(ctx: &Context, input: &HookInput) -> Result<Option<String>> {
    // python 은 무엇이든 잡아 조용히 끝난다
    match placement(ctx, input) {
        Err(Halt::PyError(_)) => Ok(None),
        other => other,
    }
}

fn placement(ctx: &Context, input: &HookInput) -> Result<Option<String>> {
    // A memory file other than the index
    let ti = pyval::dict_or_empty(input.get("tool_input"))?;
    let fp = match pyval::get(ti, "file_path") {
        Some(Value::Str(s)) if !s.is_empty() => s.as_str(),
        Some(v) if v.truthy() => return Ok(None),
        _ => return Ok(None),
    };
    let name = basename(&pathlib_str(fp)).to_owned();
    if name == "MEMORY.md" || !fp.ends_with(".md") {
        return Ok(None);
    }
    let raised = |_| Halt::PyError("memory_signals raised");
    if !location::is_memory_path(fp, input.get("cwd"), &ctx.hook.env).map_err(raised)? {
        return Ok(None);
    }

    // Does it read as repo knowledge
    let text = fs::read_text_replace(fp).map_err(|_| Halt::PyError("read_text failed"))?;
    let text: String = text.chars().take(MAX_CHARS).collect();
    let (is_repo, sig) = signals::classify(&text);
    if !is_repo || seen_before(ctx, input, fp)? {
        return Ok(None);
    }

    let nonce = ctx.nonce_attr(input.get("session_id"))?;
    let text = message(&name, &signals::describe(&sig), &nonce);
    let out = HookOutput::context("PostToolUse", text).render(EnsureAscii::Yes);
    Ok(Some(format!("{out}\n")))
}

/// python `seen_before(data, file_path)`: 이 (세션, 호출한 쪽, 회차)에 이 파일을 이미 알렸나. 아니면 적어 둔다.
///
/// 상태 경로를 만들지 못하면 python 은 처음 보는 것으로 친다. dict 가 아닌 상태는 python 이 `in` 이나 대입에서 끝난다.
fn seen_before(ctx: &Context, input: &HookInput, fp: &str) -> Result<bool> {
    let sid = pyval::truthy_text(input.get("session_id"));
    let agent = pyval::truthy_text(input.get("agent_id"));
    let Ok(tmp) = ctx.tempdir() else {
        return Ok(false);
    };
    let Ok(path) = epoch::state_path(
        tmp,
        PLUGIN,
        NAMESPACE,
        sid.as_deref().unwrap_or(""),
        agent.as_deref(),
    ) else {
        return Ok(false);
    };

    // The state of this epoch
    let state = match fs::read_text(&path).map(|t| loads(&t)) {
        Ok(Ok(value)) => value,
        _ => Value::Dict(Dict::new()),
    };
    let Ok(mut state) = state.into_dict() else {
        return Err(Halt::PyError("the state is not a dict"));
    };
    if state.get(fp).is_some() {
        return Ok(true);
    }

    // Record this file
    state.insert(fp, Value::Int(1));
    match fs::write_text(&path, &dumps(&Value::Dict(state), EnsureAscii::Yes, None)) {
        Ok(()) | Err(fs::FsError::Os(_)) => Ok(false),
        Err(fs::FsError::Value) => Err(Halt::PyError("write_text failed")),
    }
}

/// python `message(name, evidence, session_id)`: warn 태그 하나.
fn message(name: &str, evidence: &str, nonce: &str) -> String {
    format!(
        "<harness-hook name=\"memory-placement\" level=\"warn\"{nonce}>\n\
         Memory file {name} looks like repo knowledge ({evidence}). Auto memory is machine-local: it does not travel with the repo, \
         to another clone or machine, or to teammates, and it detaches if the folder moves. \
         Before continuing, propose moving the repo-specific part to the repo (CLAUDE.md, .claude/rules/<topic>.md, or docs/), \
         or to the coderag project layer if the project uses it; toolkit-general facts belong in a shared pack, company-wide facts in coderag team. \
         Ask the user before editing repo files; keep only personal preferences and this-machine/environment notes in memory. \
         If this note is in fact personal or environment-specific, say so in one line and continue.\n\
         </harness-hook>"
    )
}
