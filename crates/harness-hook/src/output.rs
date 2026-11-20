//! 훅 stdout JSON 과 종료 코드.
//!
//! 필드 순서가 곧 출력 바이트 순서다. python 훅이 쓰는 dict 순서에 맞췄다:
//! 바깥은 `decision`, `reason`, `systemMessage`, `hookSpecificOutput`,
//! 안쪽은 `hookEventName`, `permissionDecision`, `permissionDecisionReason`, `additionalContext`.
//! 다른 순서가 필요한 훅은 자기 구조체를 만들어 [`crate::py::json::to_string`] 으로 쓴다.

use std::io::Write;
use std::process::ExitCode;

use serde::Serialize;

pub use crate::py::json::EnsureAscii;

/// 훅 출력 객체 하나.
#[derive(Clone, Debug, Default, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct HookOutput {
    /// Stop, SubagentStop 등에서 턴을 이어 가게 한다(`"block"`). 사유는 [`HookOutput::reason`].
    #[serde(skip_serializing_if = "Option::is_none")]
    pub decision: Option<BlockDecision>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub reason: Option<String>,
    /// 사용자에게만 보이는 줄. 턴을 늘리지 않는다.
    #[serde(skip_serializing_if = "Option::is_none")]
    pub system_message: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub hook_specific_output: Option<HookSpecificOutput>,
}

/// `decision` 값. 지금은 `"block"` 하나만 쓴다.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum BlockDecision {
    Block,
}

/// `hookSpecificOutput`.
#[derive(Clone, Debug, Default, PartialEq, Eq, Serialize)]
#[serde(rename_all = "camelCase")]
pub struct HookSpecificOutput {
    pub hook_event_name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub permission_decision: Option<PermissionDecision>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub permission_decision_reason: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub additional_context: Option<String>,
}

/// PreToolUse 의 `permissionDecision`.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum PermissionDecision {
    Allow,
    Deny,
    Ask,
}

impl HookOutput {
    /// PreToolUse 에서 도구를 막는다. `reason` 은 `action` 태그로 감싼 글이다(HOOK-MESSAGES.md 규칙 5).
    pub fn deny(reason: impl Into<String>) -> HookOutput {
        HookOutput::specific(HookSpecificOutput {
            hook_event_name: "PreToolUse".to_owned(),
            permission_decision: Some(PermissionDecision::Deny),
            permission_decision_reason: Some(reason.into()),
            ..HookSpecificOutput::default()
        })
    }

    /// 모델에게 보일 글(`additionalContext`). `event` 는 입력의 `hook_event_name` 이다.
    pub fn context(event: impl Into<String>, text: impl Into<String>) -> HookOutput {
        HookOutput::specific(HookSpecificOutput {
            hook_event_name: event.into(),
            additional_context: Some(text.into()),
            ..HookSpecificOutput::default()
        })
    }

    /// 사용자에게만 보일 줄(`systemMessage`).
    pub fn system_message(text: impl Into<String>) -> HookOutput {
        HookOutput {
            system_message: Some(text.into()),
            ..HookOutput::default()
        }
    }

    /// 턴을 이어 가게 한다(`{"decision": "block", "reason": ...}`).
    pub fn block(reason: impl Into<String>) -> HookOutput {
        HookOutput {
            decision: Some(BlockDecision::Block),
            reason: Some(reason.into()),
            ..HookOutput::default()
        }
    }

    /// `hookSpecificOutput` 만 있는 출력.
    pub fn specific(inner: HookSpecificOutput) -> HookOutput {
        HookOutput {
            hook_specific_output: Some(inner),
            ..HookOutput::default()
        }
    }

    /// python `json.dumps(out, ensure_ascii=...)` 와 같은 문자열. 끝 줄바꿈은 없다(`json.dump(out, sys.stdout)`).
    pub fn render(&self, ascii: EnsureAscii) -> String {
        crate::py::json::to_string(self, ascii)
            .expect("HookOutput has only string keys and plain fields")
    }
}

/// stdout 에 쓰고 flush 한다. 읽는 쪽이 먼저 닫았으면(EPIPE) 조용히 넘긴다(python 훅은 그때 예외로 끝난다).
pub fn emit(text: &str) {
    let mut out = std::io::stdout().lock();
    let _ = out.write_all(text.as_bytes()).and_then(|()| out.flush());
}

/// 종료 코드 2 로 도구를 막는다. `text` 와 줄바꿈을 stderr 에 쓴다(python `print(text, file=sys.stderr); sys.exit(2)`).
pub fn exit_block(text: &str) -> ExitCode {
    let mut err = std::io::stderr().lock();
    let _ = writeln!(err, "{text}");
    ExitCode::from(2)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn renders_python_dict_order() {
        assert_eq!(
            HookOutput::deny("r").render(EnsureAscii::Yes),
            r#"{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "r"}}"#
        );
        assert_eq!(
            HookOutput::context("PostToolUse", "\u{e9}").render(EnsureAscii::No),
            "{\"hookSpecificOutput\": {\"hookEventName\": \"PostToolUse\", \"additionalContext\": \"\u{e9}\"}}"
        );
        assert_eq!(
            HookOutput::block("x").render(EnsureAscii::Yes),
            r#"{"decision": "block", "reason": "x"}"#
        );
    }
}
