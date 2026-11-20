//! `hook expand-inherit-prompt`: inherit-advisor 의 fork 표지를 후행 프롬프트 원문으로 펼친다
//! (python `hooks/expand-inherit-prompt.py`).
//!
//! `subagent_type == "fork"` 이고 prompt 가 표지로 시작할 때만 prompt 를 `templates/fork-prompt.md` 로 바꾼다.
//! 템플릿이 없거나 형식이 틀리면 그대로 통과한다(표지 자체가 안전한 최소 지시다).

use std::collections::BTreeSet;

use harness_hook::py::path::join;
use harness_hook::py::text::{split_whitespace, splitlines, strip};
use harness_hook::py::value::{Dict, Value};

use crate::context::Context;
use crate::hookio::{allow_with_input, load_dict, text, truthy};
use crate::outcome::Outcome;
use harness_hook::py::fs::{FsError, read_text};

const TAG: &str = "[qwreey-advisor:inherit]";
const NEXT_PLACEHOLDER: &str = "<next step in one line>";
const REQ_AFTER: &str = "Request:";
const REASON: &str = "qwreey-advisor: inherit-advisor 표지를 후행 프롬프트로 펼침";

/// 훅 한 번. python 은 입력 오류를 잡아 0 으로 끝나지만 출력을 쓰다 나는 오류(쓸 수 없는 서로게이트)는 1 이다.
pub fn run(ctx: &Context, raw: &[u8]) -> Outcome {
    let Some(data) = load_dict(raw) else {
        return Outcome::quiet();
    };
    let Some(templates) = ctx.plugin_root().map(|root| {
        join(
            &join(&join(&root, "skills"), "inherit-advisor"),
            "templates",
        )
    }) else {
        return Outcome::quiet();
    };
    let Some(out) = expanded_input(&data, &templates) else {
        return Outcome::quiet();
    };
    Outcome::printed(&out).unwrap_or_else(|| {
        Outcome::stderr_line(
            1,
            "expand-inherit-prompt: the prompt cannot be written to stdout",
        )
    })
}

fn expanded_input(data: &Dict, templates: &str) -> Option<String> {
    let ti = match truthy(data, "tool_input") {
        None => return None,
        Some(Value::Dict(d)) => d,
        Some(_) => return None,
    };
    if ti.get("subagent_type").and_then(Value::as_str) != Some("fork") {
        return None;
    }
    let prompt = ti.get("prompt")?.as_str()?;
    let new = expand(prompt, templates)?;

    let mut updated = ti.clone();
    updated.insert("prompt", text(new));
    Some(allow_with_input(REASON, updated))
}

/// python `expand(prompt)`: 표지를 펼친 prompt. 바꿀 수 없으면 `None`.
pub fn expand(prompt: &str, templates: &str) -> Option<String> {
    if !prompt.starts_with(TAG) {
        return None;
    }

    // Read `next:` and `options:` lines after the marker
    let mut next = String::new();
    let mut options: BTreeSet<String> = BTreeSet::new();
    for line in splitlines(prompt).into_iter().skip(1) {
        let (key, value) = line.split_once(':').unwrap_or((line, ""));
        let key = strip(key).to_lowercase();
        if key == "next" && next.is_empty() {
            next = strip(value).to_owned();
        } else if key == "options" {
            let value = value.replace(',', " ");
            options.extend(split_whitespace(&value).map(|o| strip(o).to_lowercase()));
        }
    }
    if next.is_empty() {
        return None;
    }

    // Templates, missing ones leave the marker as is
    let template = read_template(templates, "fork-prompt.md").ok()?;
    let template = template.trim_end_matches('\n');
    let reqs = if options.contains("reqs") {
        let text = read_template(templates, "fork-prompt-reqs.md").ok()?;
        strip(&text).to_owned()
    } else {
        String::new()
    };
    if !template.contains(NEXT_PLACEHOLDER) {
        return None;
    }

    // Fill the next step, put requirements after the Request: line
    let out = template.replace(NEXT_PLACEHOLDER, &next);
    if reqs.is_empty() {
        return Some(out);
    }
    let mut lines: Vec<&str> = out.split('\n').collect();
    let at = lines.iter().position(|l| l.starts_with(REQ_AFTER))?;
    lines.insert(at + 1, &reqs);
    Some(lines.join("\n"))
}

// python 은 OSError 만 잡는다: UTF-8 이 아닌 템플릿(ValueError)은 훅 전체의 except 가 잡아 통과한다
fn read_template(dir: &str, name: &str) -> Result<String, FsError> {
    read_text(&join(dir, name))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn templates() -> String {
        let root = env!("CARGO_MANIFEST_DIR");
        format!("{root}/../../plugins/qwreey-advisor/skills/inherit-advisor/templates")
    }

    /// 표지와 next 줄이 있으면 템플릿의 자리를 그 한 줄로 채운다.
    #[test]
    fn fills_the_next_step() {
        let prompt = format!("{TAG} Review only.\nnext: commit the parser");
        let out = expand(&prompt, &templates()).expect("templates exist in the repo");
        assert!(out.contains("commit the parser"));
        assert!(!out.contains(NEXT_PLACEHOLDER));
    }

    /// 표지가 없거나 next 가 비면 바꾸지 않는다.
    #[test]
    fn leaves_other_prompts() {
        assert_eq!(expand("Review this", &templates()), None);
        assert_eq!(
            expand(&format!("{TAG}\noptions: reqs"), &templates()),
            None,
            "next is required"
        );
        assert_eq!(
            expand(&format!("{TAG}\nnext: x"), "/nonexistent"),
            None,
            "missing templates pass"
        );
    }
}
