//! 훅 stdin JSON. Claude Code 가 이벤트마다 객체 하나를 준다.

use std::io::Read;

use crate::py::json_load::{self, Decode, JsonError};
use crate::py::value::{Dict, Value};

/// 훅 입력 객체. python 훅의 `data = json.load(sys.stdin)` 자리(`python3 -X utf8` 의 stdin 이라 surrogateescape).
///
/// 필드는 이벤트마다 달라서 원본 객체를 들고, 자주 읽는 것만 접근자로 낸다.
/// 접근자는 python 의 `data.get(key)` 가 문자열일 때만 값을 준다(다른 타입은 `None`).
#[derive(Clone, Debug, PartialEq)]
pub struct HookInput {
    raw: Dict,
}

/// stdin 을 훅 입력으로 읽지 못한 이유. python 훅은 이때 아무것도 내지 않고 0 으로 끝난다.
#[derive(Debug)]
pub enum InputError {
    /// 읽기 실패.
    Io(std::io::Error),
    /// python `json.loads` 가 받지 않는 글([`json_load`]).
    Json(JsonError),
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

    /// JSON 바이트를 훅 입력으로. python 과 같이 읽는다([`json_load`]): UTF-8 이 아닌 바이트와 짝 없는 서로게이트
    /// escape 는 자리표 글자, `NaN`, 큰 정수, 깊은 중첩도 받는다.
    pub fn from_slice(bytes: &[u8]) -> Result<HookInput, InputError> {
        let value =
            json_load::from_bytes(bytes, Decode::SurrogateEscape).map_err(InputError::Json)?;
        match value.into_dict() {
            Ok(raw) => Ok(HookInput { raw }),
            Err(_) => Err(InputError::NotObject),
        }
    }

    /// 원본 객체.
    pub fn raw(&self) -> &Dict {
        &self.raw
    }

    /// 필드 하나(python `data.get(key)`).
    pub fn get(&self, key: &str) -> Option<&Value> {
        self.raw.get(key)
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
    pub fn tool_input(&self) -> Option<&Dict> {
        self.raw.get("tool_input").and_then(Value::as_dict)
    }

    /// Bash 의 `tool_input.command`(python `(data.get("tool_input") or {}).get("command")` 가 `str` 일 때).
    pub fn command(&self) -> Option<&str> {
        self.tool_input()?.get("command").and_then(Value::as_str)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 세션 id 와 명령을 읽고, 글이 아닌 값은 없음으로 본다.
    #[test]
    fn reads_fields() {
        let input =
            HookInput::from_slice(br#"{"session_id":"s","tool_input":{"command":"ls"},"cwd":3}"#)
                .unwrap();

        assert_eq!(input.session_id(), Some("s"));
        assert_eq!(input.command(), Some("ls"));
        assert_eq!(input.cwd(), None, "3 is not a string");
    }

    /// 최상위가 객체가 아닌 JSON 은 거절한다.
    #[test]
    fn rejects_non_objects() {
        assert!(matches!(
            HookInput::from_slice(b"[]"),
            Err(InputError::NotObject)
        ));
    }

    /// 깨진 JSON 은 JSON 오류로 거절한다.
    #[test]
    fn rejects_broken_json() {
        assert!(matches!(
            HookInput::from_slice(b"{"),
            Err(InputError::Json(_))
        ));
    }

    /// 2만 겹 중첩도 python 처럼 읽고, 버릴 때 스택이 넘치지 않는다.
    #[test]
    fn reads_deep_nesting() {
        let deep = format!(
            "{{\"session_id\": \"s\", \"tool_response\": {}1{}}}",
            "[".repeat(20_000),
            "]".repeat(20_000)
        );
        let input = HookInput::from_slice(deep.as_bytes()).unwrap();
        assert_eq!(input.session_id(), Some("s"));
        drop(input);
    }

    /// python 만 받는 값(NaN, 넘치는 float, UTF-8 이 아닌 바이트)도 읽는다.
    #[test]
    fn reads_python_only_values() {
        let odd = HookInput::from_slice(b"{\"a\": NaN, \"b\": 1e400, \"c\": \"\xff\"}").unwrap();
        assert!(matches!(odd.get("a"), Some(Value::Float(f)) if f.is_nan()));
        assert_eq!(odd.get("b"), Some(&Value::Float(f64::INFINITY)));
        assert!(odd.str_field("c").is_some());
    }
}
