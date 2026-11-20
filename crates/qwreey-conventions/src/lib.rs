//! qwreey-conventions 플러그인의 편집 훅을 한 바이너리로(`plugins/qwreey-conventions/hooks/*.py` 의 Rust 판).
//!
//! 출력(종료 코드와 stdout)은 python 판과 바이트로 같다. 하위 명령은 `hook <이름>` 이고 이름은 python 스크립트 이름이다:
//! - `conventions-check`: [`check`], `conventions-check.py`(PostToolUse 의 줄 검사와 Stop 의 남은 문제 보고)
//! - `reuse-check`: [`reuse`], `reuse-check.py`
//! - `structure-reminder`: [`structure`], `structure-reminder.py`(Write, Edit, Bash)
//! - `memory-placement`: [`memory`], `memory-placement.py`
//!
//! rules_inject, bash-bypass-reminder, bash_writes, compact_epoch 와 `scripts/conventions-scan.py` 는 python 그대로다.
//! 두 판은 같은 상태 파일을 같은 꼴로 읽고 쓴다(번갈아 돌아도 알림이 겹치지 않는다).

pub mod check;
pub mod context;
pub mod edit;
pub mod halt;
pub mod lex;
pub mod memory;
pub mod pyval;
pub mod reuse;
pub mod structure;

pub use context::Context;
