//! SubagentStop 에서 끝난 서브에이전트가 메인이 부른 검토인지 가리고, 그렇다면 최근 검토 시각과 ledger 자동 행을 남긴다
//! (python `hooks/review_record.py`).
//!
//! 검토로 치는 것: `qwreey-advisor:reviewer`(예전 이름 `qwreey-advisor-reviewer`), 그리고 agent_type 이 fork 이고 transcript
//! 앞부분에 inherit-advisor 표지가 있는 것. 호출자는 meta 의 parentAgentId(또는 spawnDepth > 1), 리뷰어는 run 줄도 본다.

use std::sync::LazyLock;

use harness_hook::py::fs::{read_text, write_text};
use harness_hook::py::num::{float_repr, parse_float, parse_int};
use harness_hook::py::path::join;
use harness_hook::py::value::{Dict, Value};
use harness_hook::rx::Regex;

use crate::abort::{Abort, Result};
use crate::epoch::sanitize;
use crate::pylib::fs::makedirs;

use super::NS;
use super::transcript::{head_text, run_caller};

const REVIEWERS: &[&str] = &["qwreey-advisor:reviewer", "qwreey-advisor-reviewer"];
const FORK_MARKERS: &[&str] = &["[qwreey-advisor:inherit]", "[second opinion: inherit]"];

static LEDGER_KIND: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"second opinion:\s*(\w+)"));

/// 검토의 종류.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Kind {
    Reviewer,
    Fork,
}

/// python `last_review_path(sid)`: 검토 완료 시각 파일(compact 를 넘어 유지한다). 폴더를 만든다.
pub fn last_review_path(tempdir: &str, sid: &str) -> Result<String> {
    let dir = join(tempdir, NS);
    makedirs(&dir).map_err(|_| Abort("cannot create the state folder"))?;
    Ok(join(&dir, &format!("{}.last-review", sanitize(sid))))
}

/// python `last_review_time(sid)`: 마지막으로 메인이 부른 검토가 끝난 시각, 없으면 0.
pub fn last_review_time(tempdir: &str, sid: &str) -> Result<f64> {
    let path = last_review_path(tempdir, sid)?;
    Ok(read_text(&path)
        .ok()
        .and_then(|text| parse_float(&text))
        .unwrap_or(0.0))
}

/// python `nested(meta)`: 서브에이전트가 띄운 것이면 `Some(true)`, 메인이면 `Some(false)`, meta 가 없으면 `None`.
pub fn nested(meta: &Dict) -> Result<Option<bool>> {
    if meta.is_empty() {
        return Ok(None);
    }
    let parent = meta.get("parentAgentId").is_some_and(Value::truthy);
    Ok(Some(
        parent || spawn_depth_over_one(meta.get("spawnDepth"))?,
    ))
}

// python: int(meta.get("spawnDepth") or 1) > 1, TypeError, ValueError 는 1. 무한대 float 는 OverflowError(잡지 않는다)
fn spawn_depth_over_one(depth: Option<&Value>) -> Result<bool> {
    let over = match depth.filter(|v| v.truthy()) {
        None => false,
        Some(Value::Int(n)) => *n > 1,
        Some(Value::Bool(_)) => false,
        Some(Value::BigInt(digits)) => !digits.starts_with('-'),
        Some(Value::Float(f)) if f.is_infinite() => return Err(Abort("spawnDepth is infinite")),
        Some(Value::Float(f)) => f.trunc() > 1.0,
        Some(Value::Str(s)) => parse_int(s).is_some_and(|n| n > 1),
        Some(Value::Null | Value::List(_) | Value::Dict(_)) => false,
    };
    Ok(over)
}

/// python `review_kind(data, meta)`: 검토면 그 종류.
pub fn review_kind(agent_type: Option<&Value>, tpath: &str, meta: &Dict) -> Result<Option<Kind>> {
    let at = match agent_type.filter(|v| v.truthy()) {
        None => return Ok(None),
        Some(Value::Str(s)) => s.as_str(),
        Some(Value::List(_) | Value::Dict(_)) => return Err(Abort("agent_type is unhashable")),
        Some(_) => return Ok(None),
    };
    if REVIEWERS.contains(&at) {
        return Ok(Some(Kind::Reviewer));
    }
    if at != "fork" {
        return Ok(None);
    }

    // A fork is a review when its transcript head or description carries the marker
    let head = head_text(tpath)?;
    if FORK_MARKERS.iter().any(|m| head.contains(m)) {
        return Ok(Some(Kind::Fork));
    }
    let described = match meta.get("description").filter(|v| v.truthy()) {
        None => false,
        Some(Value::Str(d)) => d.starts_with("second opinion: inherit"),
        Some(_) => return Err(Abort("description has no startswith")),
    };
    Ok(described.then_some(Kind::Fork))
}

/// python `caller_of`: `main` 또는 `subagent`.
pub fn caller_of(meta: &Dict, kind: Kind, tpath: &str) -> Result<&'static str> {
    if nested(meta)? == Some(true) {
        return Ok("subagent");
    }
    if kind == Kind::Reviewer && run_caller(tpath)?.as_deref() == Some("subagent") {
        return Ok("subagent");
    }
    Ok("main")
}

/// 메인이 부른 검토가 지금 끝났다고 적는다(python `open(last_review_path(sid), "w").write(str(time.time()))`).
pub fn record_main_review(tempdir: &str, sid: &str, now: f64) -> Result<()> {
    let path = last_review_path(tempdir, sid)?;
    write_text(&path, &float_repr(now)).map_err(|_| Abort("cannot write the last-review file"))
}

/// python `ledger_fields(kind, meta)`: (ledger kind, reviewer). python 이 예외를 내면(ledger 행을 건너뜀) `None`.
pub fn ledger_fields(kind: Kind, meta: &Dict) -> Option<(String, String)> {
    if kind == Kind::Fork {
        return Some(("inherit".to_owned(), "fork".to_owned()));
    }

    // Kind from the skill's description `second opinion: <kind>`
    let description = match meta.get("description").filter(|v| v.truthy()) {
        None => "",
        Some(Value::Str(d)) => d.as_str(),
        Some(_) => return None,
    };
    let word = LEDGER_KIND
        .match_start(description)
        .and_then(|m| m.text(description, 1).map(str::to_owned));
    let ledger_kind = match word.as_deref() {
        Some(k @ ("plan" | "stuck" | "done")) => k.to_owned(),
        _ => "adhoc".to_owned(),
    };

    // Reviewer family from the model
    let model = match meta.get("model").filter(|v| v.truthy()) {
        None => String::new(),
        Some(v) => v.scalar_str()?,
    };
    let reviewer = if model.contains("opus") {
        "opus-sub".to_owned()
    } else if model.contains("sonnet") {
        "sonnet-sub".to_owned()
    } else if !model.is_empty() && model != "inherit" {
        format!("{model}-sub")
    } else {
        "sub".to_owned()
    };
    Some((ledger_kind, reviewer))
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 이 모듈의 고정 정규식이 regex 판과 python 판(py::re)에서 같은 자리에 맞는다(만든 글 3000개).
    #[test]
    fn fixed_patterns_agree_with_python() {
        harness_hook::testkit::assert_agree(
            &[("LEDGER_KIND", &*LEDGER_KIND)],
            &[
                "second opinion:",
                " ",
                "done",
                "plan",
                "_x",
                "1",
                "\t",
                "é",
                "\u{2460}",
            ],
        );
    }

    fn meta(json: &str) -> Dict {
        crate::hookio::loads_object(json).expect("test meta is an object")
    }

    /// nested: meta 가 없으면 모름, parentAgentId 나 spawnDepth > 1 이면 서브에이전트.
    #[test]
    fn nested_like_python() {
        // No meta, main, nested
        assert_eq!(nested(&Dict::new()), Ok(None));
        assert_eq!(nested(&meta(r#"{"spawnDepth": 1}"#)), Ok(Some(false)));
        assert_eq!(nested(&meta(r#"{"parentAgentId": "a"}"#)), Ok(Some(true)));

        // python int() quirks
        assert_eq!(
            nested(&meta(r#"{"spawnDepth": "2"}"#)),
            Ok(Some(true)),
            "int(\"2\")"
        );
        assert_eq!(
            nested(&meta(r#"{"spawnDepth": 1.9}"#)),
            Ok(Some(false)),
            "int(1.9) is 1"
        );
        assert_eq!(
            nested(&meta(r#"{"spawnDepth": "x"}"#)),
            Ok(Some(false)),
            "ValueError reads as 1"
        );
        assert!(
            nested(&meta(r#"{"spawnDepth": Infinity}"#)).is_err(),
            "OverflowError is not caught"
        );
    }

    /// ledger 의 kind 와 reviewer: description 의 kind, model 의 계열.
    #[test]
    fn ledger_fields_like_python() {
        let fields = |json: &str| ledger_fields(Kind::Reviewer, &meta(json));
        assert_eq!(
            fields(r#"{"description": "second opinion: done", "model": "claude-opus-5"}"#),
            Some(("done".to_owned(), "opus-sub".to_owned()))
        );
        assert_eq!(
            fields(r#"{"description": "x"}"#),
            Some(("adhoc".to_owned(), "sub".to_owned()))
        );
        assert_eq!(
            fields(r#"{"model": "inherit"}"#),
            Some(("adhoc".to_owned(), "sub".to_owned()))
        );
        assert_eq!(
            fields(r#"{"model": "haiku"}"#),
            Some(("adhoc".to_owned(), "haiku-sub".to_owned()))
        );
        assert_eq!(
            ledger_fields(Kind::Fork, &Dict::new()),
            Some(("inherit".to_owned(), "fork".to_owned()))
        );
    }
}
