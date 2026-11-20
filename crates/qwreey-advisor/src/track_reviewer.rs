//! `hook track-reviewer`: 리뷰어 호출마다 run id 와 스크래치 폴더를 주고 호출자(main, subagent)를 prompt 끝에 적는다
//! (python `hooks/track-reviewer.py`).
//!
//! PreToolUse(Agent|Task) 에서 `subagent_type` 이 리뷰어이고 prompt 에 run 줄이 아직 없을 때만 낸다.
//! run id 는 python `uuid.uuid4()` 와 같은 꼴의 무작위 값이라 출력은 실행마다 다르다. 늘 0 으로 끝난다.

use std::sync::LazyLock;

use harness_hook::py::path::join;
use harness_hook::py::re::Regex;
use harness_hook::py::surrogate::from_os;
use harness_hook::py::value::{Dict, Value};

use crate::context::Context;
use crate::hookio::{allow_with_input, load_dict, text, truthy};
use crate::outcome::Outcome;
use crate::pylib::fs::makedirs;

const REVIEWER: &str = "qwreey-advisor:reviewer";
const REASON: &str = "qwreey-advisor: 리뷰어 실행 id 와 스크래치를 prompt 끝에 붙임";

/// track-reviewer 가 붙이는 run 줄(python `RUN_LINE`). 잡는 괄호: run id, 호출자.
pub static RUN_LINE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r"\[qwreey-advisor run: ([0-9a-f-]{36}) caller=(main|subagent) scratch=[^\]\n]*\]")
        .expect("built-in pattern")
});

/// python `parse_run_line(text)`: 마지막 run 줄의 (run id, 호출자).
pub fn parse_run_line(text: &str) -> Option<(String, String)> {
    let found = RUN_LINE.find_iter(text);
    let last = found.last()?;
    Some((
        last.text(text, 1).unwrap_or("").to_owned(),
        last.text(text, 2).unwrap_or("").to_owned(),
    ))
}

/// 훅 한 번. python 의 예외는 모두 잡혀 0 으로 끝나므로 어느 경우든 stdout 만 다르다.
pub fn run(ctx: &Context, raw: &[u8]) -> Outcome {
    let Some(data) = load_dict(raw) else {
        return Outcome::quiet();
    };
    updated_prompt(ctx, &data)
        .and_then(|out| Outcome::printed(&out))
        .unwrap_or_default()
}

fn updated_prompt(ctx: &Context, data: &Dict) -> Option<String> {
    // Reviewer calls without a run line
    let ti = match truthy(data, "tool_input") {
        None => return None,
        Some(Value::Dict(d)) => d,
        Some(_) => return None,
    };
    if ti.get("subagent_type").and_then(Value::as_str) != Some(REVIEWER) {
        return None;
    }
    let prompt = ti.get("prompt")?.as_str()?;
    if parse_run_line(prompt).is_some() {
        return None;
    }

    // New run id and its scratch folder
    let run = uuid4()?;
    let caller = if truthy(data, "agent_id").is_some() {
        "subagent"
    } else {
        "main"
    };
    let base = ctx
        .env
        .get_os("CLAUDE_AUDIT_SCRATCH")
        .map_or_else(|| "/tmp/claude-audit".to_owned(), from_os);
    let scratch = join(&base, &run);
    makedirs(&scratch).ok()?;

    // Same input with the run line appended
    let mut updated = ti.clone();
    let line = format!(
        "{}\n\n[qwreey-advisor run: {run} caller={caller} scratch={scratch}/]",
        prompt.trim_end_matches('\n')
    );
    updated.insert("prompt", text(line));
    Some(allow_with_input(REASON, updated))
}

/// python `str(uuid.uuid4())`: 무작위 128비트에 판 4, RFC 4122 변형 비트. 난수를 못 읽으면 `None`.
fn uuid4() -> Option<String> {
    let mut b = [0u8; 16];
    getrandom::fill(&mut b).ok()?;
    b[6] = (b[6] & 0x0f) | 0x40;
    b[8] = (b[8] & 0x3f) | 0x80;
    let hex: String = b.iter().map(|x| format!("{x:02x}")).collect();
    Some(format!(
        "{}-{}-{}-{}-{}",
        &hex[..8],
        &hex[8..12],
        &hex[12..16],
        &hex[16..20],
        &hex[20..]
    ))
}

#[cfg(test)]
mod tests {
    use super::*;

    /// uuid4 꼴: 36자, 판 4, 변형 비트가 8..b, run 줄 정규식이 받는다.
    #[test]
    fn uuid4_shape() {
        let id = uuid4().expect("os random");
        assert_eq!(id.len(), 36);
        assert_eq!(&id[14..15], "4", "version nibble");
        assert!("89ab".contains(&id[19..20]), "RFC 4122 variant");
        let line = format!("[qwreey-advisor run: {id} caller=main scratch=/s/]");
        assert_eq!(parse_run_line(&line), Some((id, "main".to_owned())));
    }

    /// 여러 run 줄이 있으면 마지막 것이다.
    #[test]
    fn last_run_line_wins() {
        let a = "a".repeat(36);
        let b = "b".repeat(36);
        let text = format!(
            "[qwreey-advisor run: {a} caller=main scratch=x]\n[qwreey-advisor run: {b} caller=subagent scratch=y]"
        );
        assert_eq!(parse_run_line(&text), Some((b, "subagent".to_owned())));
    }
}
