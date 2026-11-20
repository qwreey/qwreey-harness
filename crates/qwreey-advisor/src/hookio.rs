//! 훅 입력을 python `json.load(sys.stdin)` 처럼 읽기, python dict 순서 그대로 출력 JSON 만들기.

use harness_hook::py::json::{EnsureAscii, dumps_dict};
use harness_hook::py::json_load::{self, Decode};
use harness_hook::py::value::{Dict, Value};

/// python `json.load(sys.stdin)`(UTF-8 모드, surrogateescape). JSON 이 아니면 `None`.
pub fn load(raw: &[u8]) -> Option<Value> {
    json_load::from_bytes(raw, Decode::SurrogateEscape).ok()
}

/// [`load`] 한 값이 객체면 그 dict.
pub fn load_dict(raw: &[u8]) -> Option<Dict> {
    load(raw)?.into_dict().ok()
}

/// JSON 바이트(`open(path)` 의 엄격한 UTF-8)가 객체면 그 dict, 아니면 `Err` 에 읽은 값(읽지 못하면 `None`).
pub fn parse_object(bytes: &[u8]) -> Result<Dict, Option<Value>> {
    match json_load::from_bytes(bytes, Decode::Strict) {
        Ok(value) => value.into_dict().map_err(Some),
        Err(_) => Err(None),
    }
}

/// 글 하나를 JSON 으로 읽어 객체면 그 dict, 아니면 `Err` 에 읽은 값(읽지 못하면 `None`).
pub fn loads_object(text: &str) -> Result<Dict, Option<Value>> {
    match json_load::loads(text) {
        Ok(value) => value.into_dict().map_err(Some),
        Err(_) => Err(None),
    }
}

/// python `data.get(key) or default` 의 참인 값.
pub fn truthy<'a>(dict: &'a Dict, key: &str) -> Option<&'a Value> {
    dict.get(key).filter(|v| v.truthy())
}

/// 글 값 하나로 된 dict 칸.
pub fn text(s: impl Into<String>) -> Value {
    Value::Str(s.into())
}

/// `{"hookSpecificOutput": {"hookEventName": event, "additionalContext": body}}`(python `json.dumps`).
pub fn context_output(event: &str, body: &str, ascii: EnsureAscii) -> String {
    let inner = Dict::from_pairs(vec![
        ("hookEventName".to_owned(), text(event)),
        ("additionalContext".to_owned(), text(body)),
    ]);
    specific(inner, ascii)
}

/// `{"hookSpecificOutput": inner}`.
pub fn specific(inner: Dict, ascii: EnsureAscii) -> String {
    let outer = Dict::from_pairs(vec![("hookSpecificOutput".to_owned(), Value::Dict(inner))]);
    dumps_dict(&outer, ascii, None)
}

/// PreToolUse 에서 입력을 바꿔 허락하는 출력(python 의 dict 순서, `ensure_ascii=False`).
///
/// `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow",
/// "permissionDecisionReason": reason, "updatedInput": updated}}`
pub fn allow_with_input(reason: &str, updated: Dict) -> String {
    let inner = Dict::from_pairs(vec![
        ("hookEventName".to_owned(), text("PreToolUse")),
        ("permissionDecision".to_owned(), text("allow")),
        ("permissionDecisionReason".to_owned(), text(reason)),
        ("updatedInput".to_owned(), Value::Dict(updated)),
    ]);
    specific(inner, EnsureAscii::No)
}
