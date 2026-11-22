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
//!
//! 소스에 적힌 고정 정규식은 regex crate([`harness_hook::rx`], 앞뒤 보기는 [`pat::Look`])로, 사람이 쓴 패턴
//! (conventions.json `patterns`, `public_ids`, structure.json `toolkits.*.test`, 글롭, 패키지 이름)은 py::re 로 돈다.
//!
//! python 과 다른 곳(드문 입력, 그 한 항목만 다르고 훅의 다른 알림은 그대로 낸다):
//! - 사람이 쓴 패턴 가운데 py::re 가 옮기지 않은 문법(`(?x)`, 조건 괄호): 그 패턴만 없는 것으로 본다(python 은 그 패턴으로 판정).
//!   `toolkits.*.test` 면 그 툴킷의 시험 파일 기준(두 배)만 다를 수 있다.
//! - structure.json `exempt` 의 `path` 가 목록이나 dict: 그 항목만 건너뛴다(python 은 repr 글을 글롭으로 써서 한 글자 이름에만 맞는다).
//! - python 정본 영역(`value=string`)이 읽는 꼴 밖(내포, lambda, t-string, 표에 없는 `\N{...}` 이름): 그 영역만 판정하지 않는다.
//! - 시간 한도(reuse-check 300, 400 ms)는 두 판의 속도가 달라 느린 실행에서만 끊는 자리가 다르다.

pub mod check;
pub mod context;
pub mod edit;
pub mod halt;
pub mod lex;
pub mod memory;
pub mod pat;
pub mod plugins;
pub mod pyops;
pub mod pyval;
pub mod reuse;
pub mod stdout;
pub mod structure;

pub use context::Context;
