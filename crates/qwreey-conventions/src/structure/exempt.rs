//! 줄 기준 예외(python `exemption`, `reason_ok`): 파일 머리 10줄의 `<주석>@structure-exempt: <사유>` 나 structure.json 의 `exempt`.
//!
//! 사유가 비었거나 사유가 아닌 말(나중에, 귀찮, TODO, `-`)이면 무효다. 머리 표식이 structure.json 보다 앞선다.

use std::sync::LazyLock;

use harness_hook::py::re::{Flags, Regex};
use harness_hook::py::text::strip;
use harness_hook::py::unicode::is_word;
use harness_hook::py::value::Value;
use harness_hook::rx;

use super::config::Config;
use super::toolkit::comment_marks;
use crate::halt::{Halt, Result};
use crate::pyops::{fnmatch, items_or_empty, re_halt};

// 사유가 아닌 말: 비었거나, 미루기, 귀찮음, 자리표시
static NOT_A_REASON: LazyLock<rx::Regex> = LazyLock::new(|| {
    rx::Regex::with_flags(
        r"^(?:[-.…~_?!\s]*|todo|tbd|fixme|later|wip|n/?a|none|x+|임시|나중에?|나중에 ?나눔|추후|일단|귀찮.*)$",
        Flags::IGNORECASE,
    )
});

/// 예외 하나: 사유, 유효한가, 어디서 왔나(`header mark` 또는 `structure.json`).
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Exemption {
    pub reason: String,
    pub valid: bool,
    pub source: &'static str,
}

/// python `reason_ok(reason)`: 사유로 볼 만한 글인가(단어 글자 둘 이상, 미루는 말이 아님).
pub fn reason_ok(reason: &str) -> bool {
    let r = strip(reason);
    !r.is_empty()
        && NOT_A_REASON.match_start(r).is_none()
        && !r.contains("귀찮")
        && r.chars().filter(|&c| is_word(u32::from(c))).count() >= 2
}

/// python `exemption(head10, rel, cfg, comments)`: 이 파일의 예외, 없으면 `None`.
///
/// `comments` 는 툴킷의 예외 표식 주석(python 값 그대로)이다. 글이 아닌 주석이나 사유는 python 처럼 예외로 끝난다.
pub fn exemption(
    head: &str,
    rel: &str,
    cfg: &Config,
    comments: &Value,
) -> Result<Option<Exemption>> {
    if let Some(found) = header_mark(head, comments)? {
        return Ok(Some(found));
    }
    config_exempt(rel, cfg)
}

// 머리 줄 가운데 처음 맞는 표식
fn header_mark(head: &str, comments: &Value) -> Result<Option<Exemption>> {
    let pattern = format!(
        r"^\s*(?:{})\s*@structure-exempt\b\s*:?\s*(.*?)\s*(?:\]\]|\*/)?\s*$",
        comment_marks(comments)?.join("|")
    );
    let mark = Regex::new(&pattern).map_err(|e| re_halt(&e))?;

    let Some((line, m)) = head
        .split('\n')
        .find_map(|l| mark.match_start(l).map(|m| (l, m)))
    else {
        return Ok(None);
    };
    let reason = m.text(line, 1).unwrap_or("").to_owned();
    Ok(Some(Exemption {
        valid: reason_ok(&reason),
        reason,
        source: "header mark",
    }))
}

// structure.json 의 exempt 가운데 처음 맞는 글롭
fn config_exempt(rel: &str, cfg: &Config) -> Result<Option<Exemption>> {
    for entry in items_or_empty(cfg.get("exempt"))? {
        let Some(e) = entry.as_dict() else { continue };
        // python 은 목록이나 dict 인 path 의 repr 글(`['src/*']`)을 글롭으로 쓴다. 그 글롭은 `[` 로 시작하는 한 글자 집합이라
        // 한 글자 이름에만 맞는다: 그 항목만 건너뛴다
        let glob = match e.get("path") {
            Some(v) if v.truthy() => match v.scalar_str() {
                Some(text) => text,
                None => continue,
            },
            _ => String::new(),
        };
        if !fnmatch(rel, &glob)? {
            continue;
        }

        // reason_ok 는 참인 글이 아닌 사유에서 `.strip` 으로 끝난다
        let reason = match e.get("reason") {
            Some(Value::Str(s)) => s.clone(),
            Some(v) if v.truthy() => {
                return Err(Halt::PyError("an exempt reason that is not a string"));
            }
            _ => String::new(),
        };
        return Ok(Some(Exemption {
            valid: reason_ok(&reason),
            reason,
            source: "structure.json",
        }));
    }
    Ok(None)
}

#[cfg(test)]
mod tests {
    use super::*;
    use harness_hook::py::json_load::loads;

    fn luau() -> Value {
        Value::List(vec![Value::Str("--".into())])
    }

    /// 미루는 말과 빈 사유는 사유가 아니다.
    #[test]
    fn reasons() {
        // Real reasons pass
        assert!(reason_ok("type limits, cannot split"));
        assert!(reason_ok("순수 데이터 표"));

        // Postponing words and placeholders do not
        for bad in ["", " - ", "나중에", "귀찮아서", "TODO", "xxx", "N/A", "a"] {
            assert!(!reason_ok(bad), "{bad:?} is not a reason");
        }
    }

    /// 머리 표식은 주석 꼴과 끝 닫는 표식을 python 정규식대로 읽는다.
    #[test]
    fn header_marks() {
        // The closing `]]` and spaces are not part of the reason
        let cfg = Config::defaults();
        let got = exemption(
            "--!strict\n-- @structure-exempt: pure data ]]",
            "a.luau",
            &cfg,
            &luau(),
        )
        .unwrap();
        assert_eq!(got.map(|e| e.reason).as_deref(), Some("pure data"));

        // A mark with the wrong comment is not a mark
        let other = exemption("// @structure-exempt: data", "a.luau", &cfg, &luau()).unwrap();
        assert_eq!(other, None);

        // An empty reason is an invalid exemption
        let empty = exemption("-- @structure-exempt:", "a.luau", &cfg, &luau())
            .unwrap()
            .unwrap();
        assert!(!empty.valid);
    }

    /// structure.json 의 exempt 는 글롭으로 맞추고 글이 아닌 사유에서 끝난다.
    #[test]
    fn config_globs() {
        // A matching glob gives its reason
        let cfg = Config::from_value(
            &loads(r#"{"exempt": [{"path": "src/data/*", "reason": "icon table"}]}"#).unwrap(),
        );
        let got = exemption("", "src/data/Icons.luau", &cfg, &luau())
            .unwrap()
            .unwrap();
        assert_eq!(
            (got.reason.as_str(), got.valid, got.source),
            ("icon table", true, "structure.json")
        );

        // A list reason makes python's reason_ok raise
        let bad =
            Config::from_value(&loads(r#"{"exempt": [{"path": "*", "reason": [1]}]}"#).unwrap());
        assert!(exemption("", "a.luau", &bad, &luau()).is_err());
    }

    /// 목록인 exempt path 는 그 항목만 건너뛰고 다음 항목을 본다.
    #[test]
    fn list_path_skips_that_entry() {
        // python globs the list's repr, which matches one-character names only
        let raw = r#"{"exempt": [{"path": ["src/*"], "reason": "a real reason"}, {"path": "src/*", "reason": "pure data table"}]}"#;
        let cfg = Config::from_value(&loads(raw).unwrap());
        let got = exemption("--!strict", "src/a.luau", &cfg, &luau()).unwrap();
        assert_eq!(got.map(|e| e.reason).as_deref(), Some("pure data table"));
    }

    /// 이 모듈의 고정 패턴이 모두 regex crate 로 옮겨지고 엔진이 만들어진다.
    #[test]
    fn fixed_patterns_build() {
        NOT_A_REASON.check();
    }
}
