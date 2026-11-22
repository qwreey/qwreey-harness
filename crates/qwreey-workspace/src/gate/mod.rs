//! workspace-gate(python `scripts/workspace_gate.py`): 다른 저장소 쓰기를 스킬을 부르기 전까지 막는다.
//!
//! 규칙(context/ambient.md): 이 세션의 저장소가 아닌 다른 git 저장소는 읽기 전용이고 고치기 전에 묻는다.
//! - 쓰기(Edit, Write, MultiEdit, NotebookEdit, 쓰기로 분류된 Bash)가 다른 저장소를 건드리고 (세션, agent_id, compact 회차)에
//!   qwreey-workspace:workspace 스킬 로드 표시가 없으면 deny(level=action).
//! - 읽기(Read, Grep, Glob, 그 밖의 Bash)는 compact 회차마다 한 번 info.
//! - 로드 표시: PostToolUse(Skill) 의 `tool_input.skill`, 슬래시로 치면 UserPromptExpansion 의 `command_name`.
//! - 끄기: `HARNESS_WORKSPACE_GATE=off`(옵션, 사용자 harness.env, 환경 변수. 저장소 층은 못 바꾼다).
//! - 비용: 이 세션 저장소 안 경로만 만지는 호출은 `.git` 을 stat 할 뿐 설정도 상태 파일도 읽지 않는다.

pub mod bash;
mod judge;
mod state;

use std::sync::LazyLock;

use harness_hook::py::ospath::join;
use harness_hook::py::value::Value;
use harness_hook::rx::Regex;
use harness_hook::{EnsureAscii, HookInput, HookOutput};

use crate::context::Context;
use crate::paths::shown;
use crate::pyval::py_str;
use crate::scope::Scope;
use crate::stop::{Result, Stop};
use bash::Kind;
use judge::{READ_TOOLS, WRITE_TOOLS};
use state::State;

/// 상태 파일 폴더 이름(임시 폴더 아래).
const NS: &str = "claude-workspace-gate";
/// 게이트 스위치.
const SWITCH: &str = "HARNESS_WORKSPACE_GATE";

// 플러그인 스킬은 `<플러그인>:<스킬>` 이다
static SKILL: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"^(?:[\w.-]+:)?workspace$"));

/// 훅 하나를 돌려 stdout 에 쓸 글을 낸다. `event` 는 명령 인자(python `sys.argv[1]`)다.
pub fn run(ctx: &Context, event: &str, input: &HookInput) -> Result<Option<String>> {
    match event {
        "PreToolUse" => pre(ctx, input),
        "PostToolUse" => post_skill(ctx, input).map(|()| None),
        "UserPromptExpansion" => {
            mark_if_workspace(ctx, input, input.get("command_name")).map(|()| None)
        }
        _ => Ok(None),
    }
}

// PostToolUse(Skill): 부른 스킬이 workspace 스킬이면 로드 표시
fn post_skill(ctx: &Context, input: &HookInput) -> Result<()> {
    if input.tool_name() != Some("Skill") {
        return Ok(());
    }
    let skill = match input.get("tool_input") {
        Some(Value::Dict(d)) => d.get("skill"),
        Some(v) if v.truthy() => return Err(Stop::Raises("tool_input is not a dict")),
        _ => None,
    };
    mark_if_workspace(ctx, input, skill)
}

// 스킬 이름이 workspace 스킬이면 로드 표시. 문자열이 아닌 값의 str() 은 그 꼴이 될 수 없다
fn mark_if_workspace(ctx: &Context, input: &HookInput, name: Option<&Value>) -> Result<()> {
    let Some(Value::Str(name)) = name else {
        return Ok(());
    };
    if SKILL.match_start(name).is_none() {
        return Ok(());
    }
    let mut st = State::read(state_path(ctx, input)?);
    st.set_and_write("loaded")
}

// python pre(data): 쓰기는 deny, 읽기는 회차마다 한 번 info
fn pre(ctx: &Context, input: &HookInput) -> Result<Option<String>> {
    let tool = input.tool_name().unwrap_or("");
    if tool != "Bash" && !WRITE_TOOLS.contains(&tool) && !READ_TOOLS.contains(&tool) {
        return Ok(None);
    }

    // Judge the call against this session's repo
    let scope = Scope::new(ctx, &project(ctx, input)?, input.get("cwd"))?;
    let Some(hit) = judge::judge(ctx, input, &scope)? else {
        return Ok(None);
    };
    if ctx.is_off(SWITCH, scope.settings()) {
        return Ok(None);
    }
    let mut st = State::read(state_path(ctx, input)?);

    // Write: deny until the skill is loaded
    if hit.kind == Kind::Write {
        if st.flag("loaded")? {
            return Ok(None);
        }
        log(ctx, input, &hit)?;
        let reason = deny_text(
            &shown(ctx, &hit.repo),
            &ctx.nonce_attr(input.get("session_id"))?,
        );
        return Ok(Some(HookOutput::deny(reason).render(EnsureAscii::Yes)));
    }

    // Read: one note per epoch
    if st.flag("loaded")? || st.flag("warned")? {
        return Ok(None);
    }
    st.set_and_write("warned")?;
    let text = read_text(
        &shown(ctx, &hit.repo),
        &ctx.nonce_attr(input.get("session_id"))?,
    );
    Ok(Some(
        HookOutput::context("PreToolUse", text).render(EnsureAscii::Yes),
    ))
}

// 이 세션의 저장소 자리: `$CLAUDE_PROJECT_DIR`, 없으면 입력의 cwd(문자열이 아닌 참 값이면 python normpath 의 TypeError)
fn project(ctx: &Context, input: &HookInput) -> Result<String> {
    if let Some(dir) = ctx.env_var("CLAUDE_PROJECT_DIR").filter(|d| !d.is_empty()) {
        return Ok(dir);
    }
    match input.get("cwd") {
        Some(Value::Str(s)) => Ok(s.clone()),
        Some(v) if v.truthy() => Err(Stop::Raises("os.path.normpath on a cwd that is not a str")),
        _ => Ok(String::new()),
    }
}

fn state_path(ctx: &Context, input: &HookInput) -> Result<String> {
    ctx.state_path(NS, input.get("session_id"), input.get("agent_id"))
}

// deny.log 한 줄. 값은 python f-string 의 str() 이다(옮기지 않은 repr 은 대신 JSON 꼴로 남긴다: 기록일 뿐이다)
fn log(ctx: &Context, input: &HookInput, hit: &judge::Hit) -> Result<()> {
    let text = |key: &str| match input.get(key) {
        None => "None".to_owned(),
        Some(v) => {
            py_str(v).unwrap_or_else(|_| harness_hook::py::json::dumps(v, EnsureAscii::No, None))
        }
    };
    let dir = join(ctx.tempdir()?, NS);
    state::log_deny(
        &dir,
        &text("session_id"),
        &text("agent_id"),
        &hit.repo,
        &hit.what,
    );
    Ok(())
}

/// deny 사유(python `DENY`). `repo` 는 [`shown`] 한 경로, `nonce` 는 ` nonce="N"` 또는 빈 글.
pub fn deny_text(repo: &str, nonce: &str) -> String {
    format!(
        "<harness-hook name=\"workspace-gate\" level=\"action\"{nonce}>\n\
         This changes the repo `{repo}`, which is outside this session's repo. Repos other than this session's are \
         read-only unless the user approves a change; other sessions may be working there, and `.claude/worktrees/*` \
         entries must not be deleted before checking the lock file and live sessions. \
         Load the qwreey-workspace:workspace skill (Skill tool), then retry; if the user has not approved this change, ask first.\n\
         </harness-hook>"
    )
}

/// 읽기 알림(python `READ_INFO`).
pub fn read_text(repo: &str, nonce: &str) -> String {
    format!(
        "<harness-hook name=\"workspace-gate\" level=\"info\"{nonce}>\n\
         Reading `{repo}` is fine; changing it needs the user's approval and the qwreey-workspace:workspace skill first.\n\
         </harness-hook>"
    )
}
