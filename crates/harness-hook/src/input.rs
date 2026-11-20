//! 훅 stdin JSON. Claude Code 가 이벤트마다 객체 하나를 준다.

use std::io::Read;

use serde_json::{Map, Value};

/// 훅 입력 객체. python 훅의 `data = json.load(sys.stdin)` 자리.
///
/// 필드는 이벤트마다 달라서 원본 객체를 들고, 자주 읽는 것만 접근자로 낸다.
/// 접근자는 python 의 `data.get(key)` 가 문자열일 때만 값을 준다(다른 타입은 `None`).
#[derive(Clone, Debug, PartialEq)]
pub struct HookInput {
    raw: Map<String, Value>,
}

/// stdin 을 훅 입력으로 읽지 못한 이유. python 훅은 이때 아무것도 내지 않고 0 으로 끝난다.
#[derive(Debug)]
pub enum InputError {
    /// 읽기 실패.
    Io(std::io::Error),
    /// JSON 이 아니다(UTF-8 이 아닌 바이트 포함).
    Json(serde_json::Error),
    /// JSON 이지만 객체가 아니다.
    NotObject,
}

impl std::fmt::Display for InputError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            InputError::Io(e) => write!(f, "reading hook input: {e}"),
            InputError::Json(e) => write!(f, "hook input is not JSON: {e}"),
            InputError::NotObject => f.write_str("hook input is not a JSON object"),
        }
    }
}

impl std::error::Error for InputError {}

impl HookInput {
    /// `reader` 를 끝까지 읽어 훅 입력으로. 바이너리는 `HookInput::read(std::io::stdin())`.
    pub fn read<R: Read>(mut reader: R) -> Result<HookInput, InputError> {
        let mut bytes = Vec::new();
        reader.read_to_end(&mut bytes).map_err(InputError::Io)?;
        HookInput::from_slice(&bytes)
    }

    /// JSON 바이트를 훅 입력으로.
    ///
    /// 짝 없는 서로게이트 escape(`"\ud800"`)는 python 처럼 받는다: 글에는 자리표 글자로 든다([`crate::py::surrogate`]).
    /// python `json.load` 와 다른 점: 128 단계보다 깊은 중첩, `1e400` 처럼 f64 를 넘는 수, `NaN`, `Infinity` 글자를
    /// 받지 않는다. python 훅은 그런 입력을 읽고 Rust 훅은 [`InputError::Json`] 이 되어 아무것도 내지 않는다(막지 않는
    /// 쪽으로 실패한다. 훅은 도구를 멈추지 않는다는 원칙). Claude Code 가 주는 입력은 표준 JSON 이라 실제로는 거의 없다.
    pub fn from_slice(bytes: &[u8]) -> Result<HookInput, InputError> {
        match crate::py::surrogate::json_from_slice(bytes).map_err(InputError::Json)? {
            Value::Object(raw) => Ok(HookInput { raw }),
            _ => Err(InputError::NotObject),
        }
    }

    /// 원본 객체.
    pub fn raw(&self) -> &Map<String, Value> {
        &self.raw
    }

    /// 문자열 필드(python `data.get(key)` 가 `str` 일 때).
    pub fn str_field(&self, key: &str) -> Option<&str> {
        self.raw.get(key).and_then(Value::as_str)
    }

    /// `session_id`.
    pub fn session_id(&self) -> Option<&str> {
        self.str_field("session_id")
    }

    /// `agent_id`. 서브에이전트 안의 훅에만 있다.
    pub fn agent_id(&self) -> Option<&str> {
        self.str_field("agent_id")
    }

    /// `hook_event_name`(`PreToolUse`, `SessionStart` 등).
    pub fn hook_event_name(&self) -> Option<&str> {
        self.str_field("hook_event_name")
    }

    /// `cwd`.
    pub fn cwd(&self) -> Option<&str> {
        self.str_field("cwd")
    }

    /// `tool_name`.
    pub fn tool_name(&self) -> Option<&str> {
        self.str_field("tool_name")
    }

    /// `tool_input` 객체.
    pub fn tool_input(&self) -> Option<&Map<String, Value>> {
        self.raw.get("tool_input").and_then(Value::as_object)
    }

    /// Bash 의 `tool_input.command`(python `(data.get("tool_input") or {}).get("command")` 가 `str` 일 때).
    pub fn command(&self) -> Option<&str> {
        self.tool_input()?.get("command").and_then(Value::as_str)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn reads_fields_and_rejects_non_objects() {
        let input =
            HookInput::from_slice(br#"{"session_id":"s","tool_input":{"command":"ls"},"cwd":3}"#)
                .unwrap();
        assert_eq!(input.session_id(), Some("s"));
        assert_eq!(input.command(), Some("ls"));
        assert_eq!(input.cwd(), None);
        assert!(matches!(
            HookInput::from_slice(b"[]"),
            Err(InputError::NotObject)
        ));
        assert!(matches!(
            HookInput::from_slice(b"{"),
            Err(InputError::Json(_))
        ));
    }
}
