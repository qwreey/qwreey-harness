//! qwreey-proc-guard 플러그인의 훅 셋을 한 바이너리로(`plugins/qwreey-proc-guard/hooks/*.py` 의 Rust 판).
//!
//! 출력(종료 코드와 stdout)은 python 판과 바이트로 같다. 훅마다 하위 명령 하나다(`qwreey-proc-guard hook <이름>`):
//! - [`heavy`]: `heavy-proc-guard.py`, 벤치·퍼저 실행을 choom 없이 하면 deny
//! - [`self_match`]: `self-match-guard.py`, pgrep/pkill -f 패턴이 자기 셸에 걸리면 deny 또는 알림
//! - [`resource`]: `resource-guard.py`, 디스크 여유 공간과 core dump 알림. 상태 파일은 python 판과 같은 자리, 같은 꼴이다
//!
//! 어떤 훅도 오류로 끝나지 않는다: 읽지 못한 입력과 예기치 못한 실패는 아무것도 내지 않고 종료 코드 0 이다(python 판과 같다).

pub mod context;
pub mod heavy;
pub mod resource;
pub mod self_match;
pub mod shell;

pub use context::Context;
