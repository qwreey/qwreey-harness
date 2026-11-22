//! rules-inject(python `hooks/rules_inject.py`): 파일 경로가 이 플러그인 rule 의 `paths` 에 맞으면 그 본문을 additionalContext 로 넣는다.
//!
//! PostToolUse(Read, Edit, Write, MultiEdit, NotebookEdit)에서 맞는 rule 가운데 이 맥락에 아직 안 넣은 것을 넣는다.
//! Read 뒤는 본문만, 쓴 뒤는 "쓴 것을 rule 에 대조하라" 한 문장을 더한다.
//!
//! 맥락 하나는 (session, agent 또는 main, compact 회차)이고 rule 마다 마커 파일 `<상태>.<rule>` 을 O_EXCL 로 만든다.
//! 나란히 도는 두 호출 가운데 하나만 마커를 얻어 두 번 넣지 않는다. python 판과 같은 마커를 쓴다.
//! 플러그인 이름은 바이너리 위 폴더의 `.claude-plugin/plugin.json` 에서 읽는다(coderag 의 팩 대조가 임시 플러그인 폴더에서 부른다).
//!
//! python 판은 본문 전체를 try 로 감싸, 무엇이 틀려도 조용히 0 으로 끝난다. 이 판도 그렇다. 하나 다른 것은 python 이
//! 모듈을 읽을 때 plugin.json 을 보는 자리다: 그 파일이 dict 가 아닌 JSON 이면 python 은 예외로 끝난다([`Plugin::locate`]).

mod glob;
mod paths;
mod rule;

use harness_hook::HookInput;
use harness_hook::epoch;
use harness_hook::output::{EnsureAscii, HookOutput};
use harness_hook::py::fs;
use harness_hook::py::json_load::loads;
use harness_hook::py::path::{basename, dirname, join, normpath};
use harness_hook::py::surrogate::from_os;
use harness_hook::py::value::Value;
use harness_hook::rx::Regex;
use std::sync::LazyLock;

use crate::context::Context;
use crate::edit;
use crate::halt::{Halt, Result};
use crate::pyval;

pub use glob::{compile as compile_glob, rule_matches};
pub use paths::{excluded, getcwd, project_root, skipped_dir};
pub use rule::{Rule, RuleText, load_dir, parse_rule};

/// 이 바이너리가 든 플러그인(python `rules_inject` 의 `PLUGIN`, `RULES_DIR`).
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Plugin {
    /// 플러그인 폴더(`native/` 의 위, python 판은 `hooks/` 의 위).
    pub root: String,
    /// plugin.json 의 `name`, 없으면 폴더 이름.
    pub name: String,
}

impl Plugin {
    /// python `plugin_name()`: plugin.json 의 `name` 이 빈 글이 아니면 그것, 읽지 못하면 폴더 이름.
    ///
    /// plugin.json 이 dict 가 아닌 JSON 이면 python 은 모듈을 읽다 끝난다([`Halt::PyError`]).
    pub fn locate(ctx: &Context) -> Result<Plugin> {
        let root = plugin_root(ctx)?;
        let manifest = join(&join(&root, ".claude-plugin"), "plugin.json");
        let parsed = fs::read_text(&manifest).ok().and_then(|t| loads(&t).ok());
        let name = match &parsed {
            Some(Value::Dict(d)) => match d.get("name") {
                Some(Value::Str(n)) if !n.is_empty() => Some(n.clone()),
                _ => None,
            },
            Some(_) => return Err(Halt::PyError("plugin.json is not an object")),
            None => None,
        };
        let name = name.unwrap_or_else(|| basename(&root).to_owned());
        Ok(Plugin { root, name })
    }

    /// 이 플러그인의 `rules/`.
    pub fn rules_dir(&self) -> String {
        join(&self.root, "rules")
    }

    /// 마커 상태 폴더 이름(python `NS = "claude-%s-rules" % PLUGIN`).
    pub fn namespace(&self) -> String {
        format!("claude-{}-rules", self.name)
    }

    /// 이 맥락의 마커 머리(python `compact_epoch.state_path(PLUGIN, NS, session_id, agent_id)`). 폴더를 만든다.
    pub fn marker_base(&self, ctx: &Context, input: &HookInput) -> Result<String> {
        let sid = pyval::truthy_text(input.get("session_id")).unwrap_or_default();
        let agent = pyval::truthy_text(input.get("agent_id"));
        epoch::state_path(
            ctx.tempdir()?,
            &self.name,
            &self.namespace(),
            &sid,
            agent.as_deref(),
        )
        .map_err(|_| Halt::PyError("cannot create the rules state folder"))
    }
}

/// 이 바이너리가 든 플러그인 폴더: `native/` 의 위(python 판은 `hooks/` 의 위).
pub fn plugin_root(ctx: &Context) -> Result<String> {
    let exe_dir = ctx
        .hook
        .exe_dir
        .as_deref()
        .ok_or(Halt::Unported("no executable folder"))?;
    Ok(dirname(&from_os(exe_dir.as_os_str())).to_owned())
}

/// rules-inject 훅 하나. python 이 조용히 넘기는 실패는 모두 `None` 이다.
pub fn run(ctx: &Context, input: &HookInput) -> Result<Option<String>> {
    let plugin = Plugin::locate(ctx)?;
    Ok(inject(ctx, input, &plugin).unwrap_or(None))
}

fn inject(ctx: &Context, input: &HookInput, plugin: &Plugin) -> Result<Option<String>> {
    if ctx.is_off("HARNESS_CONVENTIONS_RULES") {
        return Ok(None);
    }

    // The file, unless it sits where rules are not shown
    let Some(fp) = paths::edited_path(input.get("tool_input"))? else {
        return Ok(None);
    };
    let root = project_root(ctx, input.get("cwd"))?;
    let abs_path = absolute(&fp, input.get("cwd"), &root)?;
    let tool = input.get("tool_name");
    if paths::should_skip(ctx, tool, &abs_path, &root) {
        return Ok(None);
    }

    // Matching rules not yet shown in this context
    let skip = excluded(&root)?;
    let mut hits = Vec::new();
    for r in load_dir(&plugin.rules_dir())? {
        if !skip.contains(&r.name)
            && rule_matches(&r.regexes, &abs_path, &root)?
            && r.text.switch_on(ctx)
        {
            hits.push(r);
        }
    }
    if hits.is_empty() {
        return Ok(None);
    }
    let base = plugin.marker_base(ctx, input)?;
    let picked: Vec<Rule> = hits.into_iter().filter(|r| claim(&base, &r.name)).collect();
    if picked.is_empty() || input.hook_event_name() != Some("PostToolUse") {
        return Ok(None);
    }

    // One tag with every picked rule
    let bodies: Vec<(String, String)> = picked
        .iter()
        .map(|r| {
            (
                r.name.clone(),
                with_setting(ctx, &r.name, &r.text.body, &abs_path, input),
            )
        })
        .collect();
    let after_write = tool.and_then(Value::as_str) != Some("Read");
    let nonce = ctx.nonce_attr(input.get("session_id"))?;
    let text = injection(
        &plugin.name,
        &nonce,
        basename(&abs_path),
        &bodies,
        after_write,
    );
    Ok(Some(
        HookOutput::context("PostToolUse", text).render(EnsureAscii::No),
    ))
}

// python `fp if os.path.isabs(fp) else os.path.join(data.get("cwd") or root, fp)`
fn absolute(fp: &str, cwd: Option<&Value>, root: &str) -> Result<String> {
    if fp.starts_with('/') {
        return Ok(fp.to_owned());
    }
    match cwd {
        Some(Value::Str(c)) if !c.is_empty() => Ok(join(c, fp)),
        Some(v) if v.truthy() => Err(Halt::PyError("cwd is not a string")),
        _ => Ok(join(root, fp)),
    }
}

/// python `claim(base, name)`: 마커 `<base>.<name>` 를 새로 만들었으면 참(이 호출이 넣는다).
///
/// 이미 있거나 만들지 못하면 거짓이다(상태를 못 쓰면 매번 넣기보다 넣지 않는다).
pub fn claim(base: &str, name: &str) -> bool {
    let Some(path) = fs::os_path(&format!("{base}.{name}")) else {
        return false;
    };
    let mut options = std::fs::OpenOptions::new();
    options.write(true).create_new(true);
    #[cfg(unix)]
    std::os::unix::fs::OpenOptionsExt::mode(&mut options, 0o600);
    options.open(path).is_ok()
}

/// python `injection(files_label, picked, after_write, session_id)`: rules-inject 태그 하나.
pub fn injection(
    plugin: &str,
    nonce: &str,
    label: &str,
    picked: &[(String, String)],
    after_write: bool,
) -> String {
    let verb = if after_write { "wrote" } else { "opened" };
    let tail = if after_write {
        " Check what you wrote against them and fix only what conflicts.\n"
    } else {
        "\n"
    };
    let rules: Vec<String> = picked
        .iter()
        .map(|(name, body)| format!("<rule plugin=\"{plugin}\" name=\"{name}\">\n{body}\n</rule>"))
        .collect();
    format!(
        "<harness-hook name=\"rules-inject\" level=\"info\"{nonce}>\nRules for files matching these paths \
         (shown once per context; you {verb} {label}).{tail}{}\n</harness-hook>",
        rules.join("\n")
    )
}

/// 언어 코드 꼴(python `LANG_CODE`). 값이 모델에게 가는 태그 안에 들어가므로 이 꼴만 받는다.
static LANG_CODE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"[A-Za-z]{2,3}(?:[-_][A-Za-z0-9]{2,8})?\Z"));

/// python `with_setting(...)`: comments rule 이면 제목 줄 아래에 저장소의 comment_language 줄을 넣는다.
///
/// 설정은 conventions-check 가 읽는 곳(편집하는 파일의 저장소)에서 읽는다. 설정이 없거나 읽다 실패하면 본문 그대로.
pub fn with_setting(
    ctx: &Context,
    name: &str,
    body: &str,
    abs_path: &str,
    input: &HookInput,
) -> String {
    if name != "comments" {
        return body.to_owned();
    }
    let Ok(repo) = edit::project_root(&normpath(abs_path), input.get("cwd"), &ctx.hook.env) else {
        return body.to_owned();
    };
    let lang = match paths::repo_config(&repo).get("comment_language") {
        Some(Value::Str(lang)) if LANG_CODE.match_start(lang).is_some() => lang.clone(),
        _ => return body.to_owned(),
    };
    let line = format!(
        "- This repo: comment_language = {lang}. Comments in a new file are written in it, whatever its sibling files use; \
         an existing file keeps the language its comments already use."
    );

    // Right under the title line, or first when there is no title
    let (head, rest) = match body.split_once('\n') {
        Some((head, rest)) => (head, Some(rest)),
        None => (body, None),
    };
    if !head.starts_with('#') {
        return format!("{line}\n{body}");
    }
    match rest {
        Some(rest) => format!("{head}\n{line}\n{rest}"),
        None => format!("{head}\n{line}"),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 읽은 뒤와 쓴 뒤의 문장, rule 블록 꼴.
    #[test]
    fn injection_text_like_python() {
        let picked = vec![("a".to_owned(), "# A\nbody".to_owned())];
        let read = injection("p", "", "x.ts", &picked, false);
        assert_eq!(
            read,
            "<harness-hook name=\"rules-inject\" level=\"info\">\nRules for files matching these paths (shown once per \
             context; you opened x.ts).\n<rule plugin=\"p\" name=\"a\">\n# A\nbody\n</rule>\n</harness-hook>"
        );
        let wrote = injection("p", " nonce=\"n\"", "x.ts", &picked, true);
        assert!(wrote.contains(
            "you wrote x.ts). Check what you wrote against them and fix only what conflicts.\n<rule"
        ));
    }

    /// 마커는 처음 한 번만 얻는다.
    #[test]
    fn claim_once() {
        let base = std::env::temp_dir().join(format!("conv-claim-{}", std::process::id()));
        let base = base.to_str().unwrap();
        assert!(claim(base, "r"));
        assert!(!claim(base, "r"));
        std::fs::remove_file(format!("{base}.r")).unwrap();
    }
}
