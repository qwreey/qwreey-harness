//! qwreey-sessions 플러그인의 자주 뜨는 훅을 한 바이너리로(`plugins/qwreey-sessions/scripts/*.py` 의 Rust 판).
//!
//! 출력(종료 코드와 stdout)은 python 판과 바이트로 같다. 하위 명령:
//! - `hook session-log <PostToolUse|UserPromptSubmit|PreToolUse>`: [`session_log`], `scripts/hook.py` 의 같은 이벤트
//! - `hook records-read [PreToolUse|PostToolUse]`: [`records_read`], `scripts/records_read.py`
//!
//! SessionStart, PreCompact, PostCompact, SessionEnd 와 요약 워커(`scripts/cli.py flush`)는 python 그대로다.
//! 두 판은 같은 상태 파일([`store`], [`epoch`])을 같은 꼴로 읽고 쓴다.

pub mod abort;
pub mod brief;
pub mod config;
pub mod context;
pub mod date;
pub mod epoch;
pub mod fsx;
pub mod messages;
pub mod paths;
pub mod pyval;
pub mod records_home;
pub mod records_read;
pub mod session_log;
pub mod store;

pub use context::Context;
