//! sibling-notice(python `scripts/sibling_notice.py`): 이 저장소의 기록에 형제 저장소 안 경로를 쓰면 info 한 줄.
//!
//! 그 내부를 이 저장소가 정말 필요로 하는지, 그 저장소가 이 저장소만큼 공개인지 확인하게 하는 알림이다. 판단은 모델이 한다.
//! - 기록: 기록 뿌리(이 세션 저장소, 또는 그 안 `.claude/worktrees/<이름>`)의 `.claude/` 아래 파일. 설정, 규약 폴더는 뺀다.
//! - 형제: known_repos 의 저장소들(이 세션 저장소는 뺀다). 이름은 폴더 이름이다.
//! - 쓴 글만 본다: Write 의 content, Edit 의 new_string, MultiEdit 의 edits[].new_string.
//! - 한 번: (쓴 파일, 형제)마다 (세션, agent_id, compact 회차)에 한 번.
//! - 끄기: `HARNESS_WORKSPACE_SIBLING_NOTICE=off`(옵션, 환경 변수, harness.env 의 사용자, 저장소 층).

pub mod hits;
mod records;
mod seen;

use harness_hook::py::ospath::{dirname, join, normpath};
use harness_hook::py::value::{Dict, Value};
use harness_hook::{EnsureAscii, HookInput, HookOutput, known_repos};

use crate::context::Context;
use crate::paths::{Base, norm};
use crate::pyval::truthy_text;
use crate::stop::{Result, Stop};
use hits::find_hits;
use seen::Seen;

/// 알림 스위치.
const SWITCH: &str = "HARNESS_WORKSPACE_SIBLING_NOTICE";
/// 상태 파일 폴더 이름(임시 폴더 아래).
const NS: &str = "claude-workspace-sibling";
/// 보는 도구.
const TOOLS: &[&str] = &["Write", "Edit", "MultiEdit"];
/// 알림에 보이는 예의 최대 글자 수.
const EXAMPLE_MAX: usize = 80;

/// 훅 하나를 돌려 stdout 에 쓸 글을 낸다.
pub fn run(ctx: &Context, input: &HookInput) -> Result<Option<String>> {
    let Some(text) = notice(ctx, input)? else {
        return Ok(None);
    };
    Ok(Some(
        HookOutput::context("PostToolUse", text).render(EnsureAscii::Yes),
    ))
}

// python run(data): 알림 글, 낼 것이 없으면 None
fn notice(ctx: &Context, input: &HookInput) -> Result<Option<String>> {
    let tool = input.tool_name().unwrap_or("");
    if !TOOLS.contains(&tool) {
        return Ok(None);
    }
    let empty = Dict::new();
    let ti = input.tool_input().unwrap_or(&empty);
    let file = truthy_text(ti.get("file_path"));
    let text = written_text(tool, ti)?;
    if file.is_empty() || text.is_empty() || !file.contains(".claude") {
        return Ok(None);
    }

    // Only a record of this repo
    let cwd = input.get("cwd").filter(|v| v.truthy());
    let project = normpath(&project(ctx, cwd)?);
    if project.is_empty() || project == dirname(&project) {
        return Ok(None);
    }
    let base: Base = match cwd {
        Some(Value::Str(s)) => Some(s),
        Some(_) => None,
        None => Some(&project),
    };
    let path = norm(ctx, &file, base)?;
    if records::records_rel(&path, &project)?.is_none() {
        return Ok(None);
    }
    if ctx.is_off(SWITCH, &ctx.load_env(cwd)) {
        return Ok(None);
    }

    // Sibling paths in what was written
    let repos = known_repos::repos(&ctx.env, ctx.exe_dir.as_deref())
        .map_err(|_| Stop::Raises("known_repos.repos"))?;
    let sibs = records::siblings(&project, &repos)?;
    let local_dirs = [
        project.clone(),
        join(&project, ".claude"),
        dirname(&path).to_owned(),
    ];
    let found = find_hits(ctx, &text, &sibs, &local_dirs)?;
    if found.is_empty() {
        return Ok(None);
    }

    // Once per (file, sibling, epoch)
    let sid = input.get("session_id");
    let state = ctx.state_path(NS, sid, input.get("agent_id"))?;
    let seen = Seen::read(&state)?;
    let fresh: Vec<(&String, &Vec<(String, String)>)> = found
        .iter()
        .filter(|(name, _)| !seen.contains(&format!("{path}\t{name}")))
        .collect();
    if fresh.is_empty() {
        return Ok(None);
    }
    seen.write_with(
        &state,
        fresh.iter().map(|(name, _)| format!("{path}\t{name}")),
    )?;

    let nonce = ctx.nonce_attr(sid)?;
    Ok(Some(format!(
        "<harness-hook name=\"sibling-internals\" level=\"info\"{nonce}>\n{}\n</harness-hook>",
        message(&fresh)
    )))
}

// 이 세션의 저장소 자리: `$CLAUDE_PROJECT_DIR`, 없으면 입력의 cwd(문자열이 아닌 값이면 python normpath 의 TypeError)
fn project(ctx: &Context, cwd: Option<&Value>) -> Result<String> {
    if let Some(dir) = ctx.env_var("CLAUDE_PROJECT_DIR").filter(|d| !d.is_empty()) {
        return Ok(dir);
    }
    match cwd {
        Some(Value::Str(s)) => Ok(s.clone()),
        Some(_) => Err(Stop::Raises("os.path.normpath on a cwd that is not a str")),
        None => Ok(String::new()),
    }
}

// python written_text: 쓴 글만. MultiEdit 는 dict 인 편집마다 new_string 을 줄바꿈으로 잇는다
fn written_text(tool: &str, ti: &Dict) -> Result<String> {
    match tool {
        "Write" => return Ok(truthy_text(ti.get("content"))),
        "Edit" => return Ok(truthy_text(ti.get("new_string"))),
        _ => {}
    }

    let Some(Value::List(edits)) = ti.get("edits") else {
        return Ok(String::new());
    };
    let mut parts = Vec::new();
    for edit in edits {
        if let Value::Dict(e) = edit {
            parts.push(truthy_text(e.get("new_string")));
        }
    }
    Ok(parts.join("\n"))
}

// python message(hits): 형제 하나면 그 이름과 수, 여럿이면 형제마다 수와 예
fn message(hits: &[(&String, &Vec<(String, String)>)]) -> String {
    // One sibling
    if let [(name, rels)] = hits {
        let n = rels.len();
        let (plural, pronoun) = if n == 1 { ("", "it") } else { ("s", "them") };
        return format!(
            "This record names {n} internal path{plural} of sibling repo `{name}` (e.g. `{}`). Check that this repo needs \
             {pronoun} and that `{name}` is at least as public as this repo (remote, LICENSE); if unsure, ask the user, \
             else keep only the conclusion.",
            example(&rels[0].1)
        );
    }

    // Several siblings
    let parts: Vec<String> = hits
        .iter()
        .map(|(name, rels)| format!("`{name}` ({}, e.g. `{}`)", rels.len(), example(&rels[0].1)))
        .collect();
    format!(
        "This record names internal paths of sibling repos {}. Check that this repo needs them and that each is at least \
         as public as this repo (remote, LICENSE); if unsure, ask the user, else keep only the conclusion.",
        parts.join(", ")
    )
}

// python _example: 80 글자까지, 넘으면 77 글자와 `...`
fn example(s: &str) -> String {
    if s.chars().count() <= EXAMPLE_MAX {
        return s.to_owned();
    }
    let head: String = s.chars().take(EXAMPLE_MAX - 3).collect();
    format!("{head}...")
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 긴 예는 77 글자와 `...` 로 줄인다.
    #[test]
    fn example_is_truncated() {
        let long = format!("../other/{}", "a".repeat(200));
        let rels = vec![("x".to_owned(), long)];
        let name = "other".to_owned();
        let msg = message(&[(&name, &rels)]);
        assert!(msg.contains("...`)"), "{msg}");
        assert_eq!(example("short"), "short");
    }
}
