//! qwreey-advisor 플러그인의 도구마다, 말마다 뜨는 훅을 한 바이너리로(`plugins/qwreey-advisor/hooks/*.py` 의 Rust 판).
//!
//! 종료 코드와 stdout 은 python 판과 바이트로 같다. 하위 명령(`qwreey-advisor hook <이름> [이벤트]`):
//! - `readonly-for-reviewers`: [`guard`], 리뷰어 읽기 전용 가드(`readonly-for-reviewers.py` + `auditor-readonly-guard.py`)
//! - `second-opinion-nudge`: [`nudge`], 검토 시점 알림(모든 이벤트)
//! - `expand-inherit-prompt`: [`expand_inherit`], inherit-advisor 표지 펼치기
//! - `track-reviewer`: [`track_reviewer`], 리뷰어 run 줄과 스크래치
//! - `ambient UserPromptSubmit`: [`ambient`], 상시 규약 보충 주입
//!
//! python 그대로인 것: `ambient.py` 의 SessionStart, PreCompact, `compact_epoch.py`(PreCompact). 두 판은 같은 상태 파일
//! (회차별 dedup, handback 상태, last-review, ambient 표지, ledger)을 같은 꼴로 읽고 쓴다.

pub mod abort;
pub mod ambient;
pub mod context;
pub mod epoch;
pub mod expand_inherit;
pub mod fixed_re;
pub mod git;
pub mod guard;
pub mod hookio;
pub mod nudge;
pub mod outcome;
pub mod pylib;
pub mod track_reviewer;

pub use context::Context;
pub use outcome::Outcome;
