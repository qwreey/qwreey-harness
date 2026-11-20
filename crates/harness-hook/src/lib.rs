//! 플러그인 훅 바이너리가 같이 쓰는 것: 훅 입출력 JSON, 태그와 nonce, harness.env 설정 층.
//!
//! python 훅(`plugins/*/hooks/*.py`)과 바이트가 같은 출력을 내는 것이 목표다. 정본은 아직 python 쪽이다:
//! - nonce: `lib/harness_nonce.py`, 태그 형식: `home/.claude/HOOK-MESSAGES.md`
//! - 설정 층: `home/.claude/lib/harness_env.py`
//!
//! python 표준 라이브러리의 동작(공백 판정, 줄 나누기, float 표기, `json.dumps`, `expanduser`, pathlib 정규화)을
//! 맞춘 조각은 [`py`] 에 모았다. 바이트 대조는 `tests/parity.rs` 가 python 모듈을 직접 불러 본다.
//!
//! 환경 변수는 [`Env`] 로 받는다. 프로세스 환경을 직접 읽지 않으므로 시험이 환경을 바꾸지 않고 경우마다 다른 환경을 준다.

pub mod env;
pub mod epoch;
pub mod input;
pub mod known_repos;
pub mod nonce;
pub mod output;
pub mod py;
pub mod rx;
pub mod settings;
pub mod tag;

pub use env::Env;
pub use input::HookInput;
pub use nonce::Nonce;
pub use output::{EnsureAscii, HookOutput, HookSpecificOutput, PermissionDecision};
pub use settings::{Layers, LoadRequest, Project};
pub use tag::{Level, Notices};
