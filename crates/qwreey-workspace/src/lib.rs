//! qwreey-workspace 플러그인의 도구마다 뜨는 훅 둘을 한 바이너리로(`plugins/qwreey-workspace/scripts/*.py` 의 Rust 판).
//!
//! 출력(종료 코드와 stdout)은 python 판과 바이트로 같다. 훅마다 하위 명령 하나다(`qwreey-workspace hook <이름>`):
//! - [`gate`]: `workspace_gate.py`, 다른 저장소 쓰기를 workspace 스킬 전까지 deny, 읽기는 회차마다 한 번 info
//! - [`sibling`]: `sibling_notice.py`, 기록에 형제 저장소 안 경로를 쓰면 info
//!
//! 어떤 훅도 오류로 끝나지 않는다: 읽지 못한 입력과 python 이 예외로 끝나는 입력은 아무것도 내지 않고 종료 코드 0 이다
//! ([`stop::Stop`]). 세션 시작과 compact 의 훅(ambient, stale_worktrees, compact_epoch)은 python 이다.

pub mod context;
pub mod gate;
pub mod paths;
pub mod pyval;
pub mod scope;
pub mod sibling;
pub mod stop;
