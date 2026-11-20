//! 모델에게 가는 글(python 판의 f-string 그대로)과 Stop 에서 이어 가면 안 되는 턴의 판정.

use std::sync::LazyLock;

use harness_hook::py::re::{Flags, Regex};
use harness_hook::py::text::{splitlines, strip};

/// 질문 뒤에 선택지 목록이 붙는 답을 위해 끝에서 몇 줄까지 본다.
const QUESTION_TAIL: usize = 5;

// sync-copies 가 이 줄을 한 줄로 쓴다. rustfmt 가 접지 않게 한다
#[rustfmt::skip]
// @start-replace: lib/harness_texts.py#STOP_ERROR value=string template="const STOP_ERROR_PATTERN: &str = {value};"
const STOP_ERROR_PATTERN: &str = "^\\s*(API Error|Prompt is too long|Context limit|Request timed out|Credit balance)";
// @end-replace

static STOP_ERROR: LazyLock<Regex> = LazyLock::new(|| {
    Regex::with_flags(STOP_ERROR_PATTERN, Flags::IGNORECASE).expect("built-in pattern")
});

/// 등급별 권하는 검토 모델(python `MODEL.get(tier, "sonnet")`).
pub fn model_for(tier: &str) -> &'static str {
    if tier == "high" { "opus" } else { "sonnet" }
}

/// `<harness-hook name="qwreey-advisor" level=...>` 태그(python `wrap`). `nonce_attr` 는 ` nonce="N"` 또는 빈 글.
pub fn wrap(body: &str, level: &str, nonce_attr: &str) -> String {
    format!(
        "<harness-hook name=\"qwreey-advisor\" level=\"{level}\"{nonce_attr}>\n{body}\n</harness-hook>"
    )
}

/// done 검토 권고(python `done_advice`).
pub fn done_advice(repo: &str, tier: &str, lines: i128, place: &str) -> String {
    format!(
        "{place}: {lines} changed lines in `{repo}` (review tier: {tier}) and no qwreey-advisor review has finished in this session recently \
         (only qwreey-advisor reviewers and inherit-advisor forks are tracked; other reviews are not).\n\
         Before declaring this done, consider the `qwreey-advisor:fresh-advisor` skill with kind=done \
         (Agent subagent_type=qwreey-advisor:reviewer, model={}) and handle its findings as the skill says. \
         Skip it if the change is mechanical or docs only, was already reviewed, or the user said so, and say so in one line.",
        model_for(tier)
    )
}

/// 같은 실패가 두 번(python PostToolUseFailure 의 글). `sig` 는 앞 200 글자만 넘긴다.
pub fn stuck_advice(sig: &str, tier: &str) -> String {
    format!(
        "The same failure happened twice this session: `{sig}`.\n\
         Before a third attempt, consider the `qwreey-advisor:fresh-advisor` skill with kind=stuck \
         (model={}): give it the command, the error, and your current hypothesis. \
         If the next step is already dictated by the error (typo, missing file), fix it and say so in one line.",
        model_for(tier)
    )
}

/// high 등급의 계획 검토 요구(deny).
pub const PLAN_DENY: &str = "This plan is for a high-tier repo. Get a kind=plan review first (`qwreey-advisor:fresh-advisor` skill, model=opus), \
                             add the line `qwreey-advisor: reviewed` (or `qwreey-advisor: skip` with a reason) to the plan, then exit plan mode again.";

/// high 등급의 계획 검토 권고(warn).
pub const PLAN_WARN: &str = "This plan is for a high-tier repo. Consider a kind=plan review (`qwreey-advisor:fresh-advisor` skill, model=opus) \
                             and add `qwreey-advisor: reviewed` to the plan; if it is small or already reviewed, add `qwreey-advisor: skip <reason>`.";

/// python `stop_passes(msg)`: 이어 가게 하면 안 되는 턴(빈 답, 오류와 한도 알림, 묻는 질문으로 끝난 답).
///
/// `msg` 는 `str(msg or "")` 한 글이다(부르는 쪽이 python 의 str() 을 맞춘다).
pub fn stop_passes(msg: &str) -> bool {
    let msg = strip(msg);
    if msg.is_empty() || STOP_ERROR.match_start(msg).is_some() {
        return true;
    }

    // A question in the last few non-empty lines
    let lines: Vec<&str> = splitlines(msg)
        .into_iter()
        .filter(|l| !strip(l).is_empty())
        .map(|l| strip(l).trim_end_matches(['*', '_', '`', ')', ' ']))
        .collect();
    let tail = &lines[lines.len().saturating_sub(QUESTION_TAIL)..];
    tail.iter()
        .any(|l| l.ends_with('?') || l.ends_with('\u{ff1f}'))
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Stop 이 지나가는 턴: 빈 답, 오류 알림(대소문자 무시), 끝 5줄 안의 질문.
    #[test]
    fn stop_passes_like_python() {
        // Empty and error replies
        assert!(stop_passes("  "));
        assert!(
            stop_passes("api error: 500"),
            "STOP_ERROR is case-insensitive"
        );

        // Questions, also behind markdown and in full width
        assert!(stop_passes("Done.\nShall I commit?**"));
        assert!(stop_passes(
            "Done.\n\u{ac70}\u{d560}\u{ae4c}\u{c694}\u{ff1f}"
        ));
        assert!(!stop_passes("Done.\nAll tests pass."));

        // Only the last five non-empty lines count
        assert!(!stop_passes("Why?\n1\n2\n3\n4\n5"));
        assert!(stop_passes("Why?\n1\n\n2\n3\n4"));
    }
}
