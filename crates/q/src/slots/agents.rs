//! 띄울 에이전트의 모델 계열(python `spawn_family`, `agent_model`): 호출의 model, 사용자 정의 에이전트 frontmatter 의 model,
//! 메인의 모델 순서로 본다.

use std::sync::LazyLock;

use harness_hook::py::fs::{FsError, is_dir, listdir, read_text};
use harness_hook::py::path::{join, pathlib_join, splitext};
use harness_hook::py::re::Flags;
use harness_hook::py::text::strip;
use harness_hook::py::value::{Dict, Value};
use harness_hook::rx::Regex;

use super::spend::family;
use crate::stop::{Result, Stop};

/// Claude Code 에 든 에이전트 형식(frontmatter 를 찾지 않는다).
const BUILTIN: &[&str] = &[
    "general-purpose",
    "fork",
    "Explore",
    "Plan",
    "claude",
    "statusline-setup",
    "claude-code-guide",
];
/// frontmatter 를 찾는 파일 머리의 글자 수.
const HEAD_CHARS: usize = 2000;

static FRONT: LazyLock<Regex> = LazyLock::new(|| {
    let dotall = Flags {
        dotall: true,
        ..Flags::NONE
    };
    Regex::with_flags(r"---\n(.*?)\n---", dotall)
});
static NAME: LazyLock<Regex> = LazyLock::new(|| multiline(r#"^name:\s*['"]?([^'"\n]+)"#));
static MODEL: LazyLock<Regex> = LazyLock::new(|| multiline(r#"^model:\s*['"]?([^'"\n]+)"#));

fn multiline(pattern: &str) -> Regex {
    let flags = Flags {
        multiline: true,
        ..Flags::NONE
    };
    Regex::with_flags(pattern, flags)
}

/// python `spawn_family(L, ti, st, cwd)`: 이 호출이 띄울 에이전트의 계열.
///
/// `home` 은 사용자 설정 폴더(python 의 `HOME`, `$CLAUDE_CONFIG_DIR` 또는 `~/.claude`)다.
pub fn spawn_family(
    tool_input: &Dict,
    st: &Dict,
    cwd: Option<&Value>,
    home: &str,
) -> Result<&'static str> {
    // The call's own model
    let mut model = match tool_input.get("model").filter(|v| v.truthy()) {
        None => String::new(),
        Some(Value::Str(m)) => strip(m).to_owned(),
        Some(_) => return Err(Stop::Raises("strip() of a model that is not text")),
    };

    // A user-defined agent's frontmatter
    if model.is_empty() || model == "inherit" {
        match tool_input.get("subagent_type").filter(|v| v.truthy()) {
            None => {}
            Some(Value::Str(kind)) if !BUILTIN.contains(&kind.as_str()) && !kind.contains(':') => {
                model = agent_model(kind, cwd, home)?.unwrap_or_default();
            }
            Some(Value::Str(_)) => {}
            Some(_) => return Err(Stop::Raises("subagent_type that is not text")),
        }
    }

    // Main's model
    if model.is_empty() || model == "inherit" {
        let main_model = match st.get("main").filter(|v| v.truthy()) {
            None => None,
            Some(Value::Dict(main)) => main.get("model").filter(|v| v.truthy()),
            Some(_) => return Err(Stop::Raises("main.get on a value that is not a dict")),
        };
        return Ok(family(main_model));
    }
    Ok(family(Some(&Value::Str(model))))
}

/// python `agent_model(name, cwd)`: 저장소와 사용자의 `agents/*.md` 가운데 이름이 `name` 인 것의 frontmatter model.
///
/// 파일은 폴더를 읽은 차례로 본다(python pathlib glob, 숨긴 파일 포함). UTF-8 이 아닌 파일은 python 이 예외로 끝난다.
fn agent_model(name: &str, cwd: Option<&Value>, home: &str) -> Result<Option<String>> {
    let base = match cwd.filter(|v| v.truthy()) {
        None => ".".to_owned(),
        Some(Value::Str(dir)) => dir.clone(),
        Some(_) => return Err(Stop::Raises("Path(cwd) of a value that is not text")),
    };
    let dirs = [
        pathlib_join(&pathlib_join(&base, ".claude"), "agents"),
        pathlib_join(home, "agents"),
    ];

    for dir in dirs {
        if !is_dir(&dir) {
            continue;
        }
        let names = listdir(&dir).unwrap_or_default();
        for file in names.iter().filter(|n| n.ends_with(".md")) {
            // The file head and its frontmatter
            let head: String = match read_text(&join(&dir, file)) {
                Ok(text) => text.chars().take(HEAD_CHARS).collect(),
                Err(FsError::Os(_)) => continue,
                Err(FsError::Value) => {
                    return Err(Stop::Raises("UnicodeDecodeError reading an agent file"));
                }
            };
            let Some(front) = FRONT
                .match_start(&head)
                .and_then(|m| m.text(&head, 1).map(str::to_owned))
            else {
                continue;
            };

            // The agent's name, or the file stem
            let declared = NAME
                .search(&front)
                .and_then(|m| m.text(&front, 1).map(|n| strip(n).to_owned()));
            let agent = declared.unwrap_or_else(|| splitext(file).0.to_owned());
            if agent == name {
                let model = MODEL
                    .search(&front)
                    .and_then(|m| m.text(&front, 1).map(|n| strip(n).to_owned()));
                return Ok(model);
            }
        }
    }
    Ok(None)
}

#[cfg(test)]
mod tests {
    use super::*;
    use harness_hook::testkit::assert_agree;

    /// frontmatter 패턴 셋이 python re 와 같은 일치를 낸다(regex crate 와 py::re 대조).
    #[test]
    fn patterns_agree_with_python() {
        assert_agree(
            &[("FRONT", &*FRONT), ("NAME", &*NAME), ("MODEL", &*MODEL)],
            &[
                "---\n", "\n---", "name:", "model:", " ", "\n", "'", "\"", "x", "opus", "\u{a0}",
                "\u{1c}", "\t", "-",
            ],
        );
    }

    /// 호출의 model 이 먼저이고, 없으면 메인의 모델이다.
    #[test]
    fn family_order() {
        let input = |json: &str| {
            harness_hook::py::json_load::loads(json)
                .unwrap()
                .into_dict()
                .unwrap()
        };
        let st = input(r#"{"main": {"model": "claude-opus-5-5"}}"#);
        let home = "/nonexistent";
        assert_eq!(
            spawn_family(&input(r#"{"model": " sonnet "}"#), &st, None, home).unwrap(),
            "sonnet"
        );
        assert_eq!(
            spawn_family(&input(r#"{"model": "inherit"}"#), &st, None, home).unwrap(),
            "opus"
        );
        assert!(spawn_family(&input(r#"{"model": 5}"#), &st, None, home).is_err());
    }
}
