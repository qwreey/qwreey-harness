//! q 플러그인의 자주 뜨는 훅을 한 바이너리로(`plugins/q/scripts/*.py` 의 Rust 판).
//!
//! 출력(종료 코드와 stdout)은 python 판과 바이트로 같다. 훅마다 하위 명령 하나다(`q hook <이름>`):
//! - [`slots`]: `subagent-slots.py`, 서브에이전트 고지와 away 슬롯(PreToolUse Agent|Workflow, PostToolUse, SubagentStart,
//!   SubagentStop, Stop). away 의 슬롯과 2단계에서 막는다.
//! - [`stale`]: `stale_work.py`, 방치된 백그라운드 작업 알림(UserPromptSubmit, SubagentStop, Stop)
//! - [`mise_hint`]: `mise-hint.py`, mise shim 실패 안내(PostToolUseFailure Bash)
//! - `ambient UserPromptSubmit`: `ambient.py` 의 보충 주입([`harness_hook::ambient`], qwreey-advisor 와 같은 판)
//!
//! python 그대로인 것: ambient 의 SessionStart, SubagentStart, PreCompact, `compact_epoch.py`, `drift.py`, 원장 CLI
//! (`/q:away`, `/q:back`). 두 판은 같은 상태 파일(원장, 방치 작업, ambient 표지)을 같은 꼴로 읽고 쓴다.

pub mod mise_hint;
pub mod num;
pub mod pyval;
pub mod slots;
pub mod stale;
pub mod stop;
