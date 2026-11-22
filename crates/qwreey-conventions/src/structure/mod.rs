//! structure-reminder(python `hooks/structure-reminder.py`): 편집한 소스 파일이 길어졌거나 폴더가 평평해지면 알린다.
//!
//! PostToolUse(Write, Edit, MultiEdit, Bash)에서 돈다. 막지 않고 additionalContext 만 낸다. 알림은 모두 회차당 한 번이다:
//! warn(경고 기준), hard(강제 기준, 분리안을 묻게 한다), grow(이번 세션에 크게 늘었다), flat(소스가 많은 평평한 폴더),
//! family(같은 PascalCase 접두의 파일 셋 이상). Bash 는 파일을 바꿨을 법한 명령에 든 소스 경로만 본다([`bash`]).
//! 출력은 python `json.dump(..., ensure_ascii=False)` 와 같은 바이트다(끝 줄바꿈 없음).

mod bash;
mod check;
mod config;
mod exempt;
mod note;
mod num;
mod state;
mod toolkit;

use std::cell::OnceCell;

use harness_hook::HookInput;
use harness_hook::output::{EnsureAscii, HookOutput};
use harness_hook::py::fs;
use harness_hook::py::path::{abspath, expanduser, pathlib_join};
use harness_hook::py::text::strip;
use harness_hook::py::value::{Dict, Value};
use harness_hook::settings::Values;

use crate::context::Context;
use crate::halt::{Halt, Result};
use crate::pyval;
use check::{Created, check_file};
use note::{Note, render};
use state::Ledger;

/// 이 훅만 읽는 harness.env 키의 기본값(python `ENV_DEFAULTS`).
const ENV_DEFAULTS: &[(&str, &str)] = &[("HARNESS_LUAU_KB", "")];
/// 그 가운데 저장소 층이 바꾸지 못하는 키: 계획기는 실행할 스크립트를 이 경로에서 찾는다(python `ENV_USER_ONLY`).
const ENV_USER_ONLY: &[&str] = &["HARNESS_LUAU_KB"];

/// 분리 계획기의 팩 안 경로와 그 팩(플러그인) 이름.
const PLANNER_REL: &str = "skills/luau-style/scripts/split-plan.py";
const PLANNER_PLUGIN: &str = "luau-kb";

/// 첫 알림에 붙이는 기준 문서 안내(python `REF`).
const REF: &str = "the qwreey-conventions rule code-structure (rules/code-structure.md in the plugin; injected when you open a matching file)";

/// 한 번 실행하는 동안의 입력과 harness.env 층(python 의 모듈 전역 `_ENV`).
pub struct Run<'a> {
    ctx: &'a Context,
    input: &'a HookInput,
    tool: &'a str,
    ti: Option<&'a Dict>,
    layers: OnceCell<Values>,
}

impl Run<'_> {
    // python harness_env(): 처음 부를 때 한 번. 읽지 못하면 빈 값
    fn layers(&self) -> &Values {
        self.layers
            .get_or_init(|| self.ctx.load_layers(ENV_DEFAULTS, ENV_USER_ONLY))
    }

    /// `HARNESS_TOOLKITS`: 비어 있지 않으면 그 툴킷만 본다.
    fn toolkits(&self) -> &str {
        self.layers()
            .get("HARNESS_TOOLKITS")
            .map_or("", String::as_str)
    }

    /// python `find_planner()`: split-plan.py 경로. `HARNESS_LUAU_KB` 가 설치된 luau-kb 보다 앞선다. 못 찾으면 `None`.
    fn find_planner(&self) -> Result<Option<String>> {
        let kb_value = self
            .layers()
            .get("HARNESS_LUAU_KB")
            .map_or("", String::as_str);
        let kb = expanduser(strip(kb_value), &self.ctx.env);
        // python 은 두 후보를 튜플로 먼저 만든다: 설치본 찾기의 예외는 kb 가 맞아도 난다
        let installed = crate::plugins::plugin_root(PLANNER_PLUGIN, &self.ctx.env)?;
        for root in std::iter::once(kb).chain(installed) {
            let planner = pathlib_join(&root, PLANNER_REL);
            if !root.is_empty() && fs::is_file(&planner) {
                return Ok(Some(planner));
            }
        }
        Ok(None)
    }
}

/// 훅 하나를 돌려 stdout 글을 돌려준다.
pub fn run(ctx: &Context, input: &HookInput) -> Result<Option<String>> {
    // Tools this hook reads
    let Some(Value::Str(tool)) = input.get("tool_name") else {
        return Ok(None);
    };
    let tool = tool.as_str();
    if !matches!(tool, "Write" | "Edit" | "MultiEdit" | "Bash") {
        return Ok(None);
    }
    let ti = pyval::dict_or_empty(input.get("tool_input"))?;

    // Paths the call touched
    let paths = touched_paths(ctx, input, tool, ti)?;
    if paths.is_empty() {
        return Ok(None);
    }

    // State of this session and epoch
    let sid = pyval::truthy_text(input.get("session_id"));
    let agent = pyval::truthy_text(input.get("agent_id"));
    let mut ledger = Ledger::load(ctx, sid.as_deref(), agent.as_deref())?;

    // Check each path
    let run = Run {
        ctx,
        input,
        tool,
        ti,
        layers: OnceCell::new(),
    };
    let resp = match input.get("tool_response") {
        Some(Value::Dict(d)) => Some(d),
        _ => None,
    };
    let mut notes = Vec::new();
    for path in &paths {
        let Value::Str(path) = path else {
            return Err(Halt::PyError(
                "os.path.abspath of a path that is not a string",
            ));
        };
        let created = if tool == "Write" {
            created(resp, path, &ledger)?
        } else {
            None
        };
        notes.extend(check_file(&run, &mut ledger, path, created)?);
    }

    // The reference once, then save
    if !notes.is_empty() && ledger.take_ref()? {
        notes.push(Note {
            level: None,
            text: format!(
                "Limits and how to split: {REF}. The repo's .claude/structure.json can change the limits and the toolkit table."
            ),
        });
    }
    ledger.save()?;
    if notes.is_empty() {
        return Ok(None);
    }

    let nonce = ctx.nonce_attr(input.get("session_id"))?;
    let out = HookOutput::context("PostToolUse", render(&notes, &nonce)).render(EnsureAscii::No);
    Ok(Some(out))
}

// Write, Edit, MultiEdit 은 file_path 하나, Bash 는 명령이 바꿨을 법한 경로들. python 에서 거짓인 값은 뺀다
fn touched_paths(
    ctx: &Context,
    input: &HookInput,
    tool: &str,
    ti: Option<&Dict>,
) -> Result<Vec<Value>> {
    if tool != "Bash" {
        return Ok(pyval::get(ti, "file_path")
            .filter(|v| v.truthy())
            .cloned()
            .into_iter()
            .collect());
    }

    // python 은 `os.getcwd()` 를 인자로 먼저 부르고, 글이 아닌 cwd 는 쓰는 자리에서 끝난다
    let cwd = match input.get("cwd") {
        Some(Value::Str(c)) if !c.is_empty() => Ok(c.clone()),
        Some(v) if v.truthy() => Err(Halt::PyError("cwd is not a string")),
        _ => Ok(getcwd()?),
    };
    let cmd = pyval::str_or_empty(pyval::get(ti, "command"))?;
    let found = bash::bash_paths(cmd, &cwd, &ctx.env)?;
    Ok(found.into_iter().map(Value::Str).collect())
}

fn getcwd() -> Result<String> {
    std::env::current_dir()
        .map(|d| harness_hook::py::surrogate::from_os(d.as_os_str()))
        .map_err(|_| Halt::PyError("os.getcwd failed"))
}

// Write 가 새 파일을 만들었나: 응답이 create 면 확실, 응답에 type 이 없고 이 회차에 처음 보는 파일이면 짐작
fn created(resp: Option<&Dict>, path: &str, ledger: &Ledger) -> Result<Option<Created>> {
    match pyval::get(resp, "type") {
        Some(Value::Str(t)) if t == "create" => Ok(Some(Created::Sure)),
        None | Some(Value::Null) => {
            let path = abspath(path).ok_or(Halt::PyError("os.getcwd failed"))?;
            Ok((!ledger.knows_file(&path)?).then_some(Created::Guess))
        }
        Some(_) => Ok(None),
    }
}
