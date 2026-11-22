//! qwreey-conventions 플러그인의 편집 훅과 Bash 훅을 한 바이너리로(`plugins/qwreey-conventions/hooks/*.py` 의 Rust 판).
//!
//! 출력(종료 코드와 stdout)은 python 판과 바이트로 같다. 하위 명령은 `hook <이름>` 이고 이름은 python 스크립트 이름이다:
//! - `conventions-check`: [`check`], `conventions-check.py`(PostToolUse 의 줄 검사와 Stop 의 남은 문제 보고)
//! - `reuse-check`: [`reuse`], `reuse-check.py`
//! - `structure-reminder`: [`structure`], `structure-reminder.py`(Write, Edit, Bash)
//! - `memory-placement`: [`memory`], `memory-placement.py`
//! - `rules-inject`: [`rules`], `rules_inject.py`(Read, Edit, Write 뒤의 rule 주입)
//! - `bash-bypass-reminder`: [`bypass`], `bash-bypass-reminder.py`(Bash 앞의 알림과 스냅숏)
//! - `bash-writes`: [`bash_writes`], `bash_writes.py`(Bash 뒤, 바뀐 파일의 줄 검사와 rule 주입)
//!
//! compact_epoch(PreCompact)와 `scripts/conventions-scan.py` 는 python 그대로다.
//! 두 판은 같은 상태 파일을 같은 꼴로 읽고 쓴다(번갈아 돌아도 알림이 겹치지 않고, 한쪽의 Bash 스냅숏을 다른 쪽이 읽는다).
//!
//! 소스에 적힌 고정 정규식은 regex crate([`harness_hook::rx`], 앞뒤 보기는 [`pat::Look`])로, 사람이 쓴 패턴
//! (conventions.json `patterns`, `public_ids`, structure.json `toolkits.*.test`, 글롭, 패키지 이름)은 py::re 로 돈다.
//!
//! python 과 다른 곳(드문 입력, 그 한 항목만 다르고 훅의 다른 알림은 그대로 낸다):
//! - 사람이 쓴 패턴 가운데 py::re 가 옮기지 않은 문법(`(?x)`, 조건 괄호): 그 패턴만 없는 것으로 본다(python 은 그 패턴으로 판정).
//!   `toolkits.*.test` 면 그 툴킷의 시험 파일 기준(두 배)만 다를 수 있다.
//! - python 정본 영역(`value=string`)이 읽는 꼴 밖(내포, lambda, t-string, 표에 없는 `\N{...}` 이름): 그 영역만 판정하지 않는다.
//! - 시간 한도(reuse-check 300, 400 ms, bash-writes 1.5, 2.5 초)는 두 판의 속도가 달라 느린 실행에서만 끊는 자리가 다르다.
//! - bash-writes 의 사본 검사: python 은 파일마다 reuse-check 를 하위 프로세스로 나란히 띄워 4 초에서 끊고, 이 판은 차례로 부른다.
//! - TOML(coderag.toml)과 JSON 의 아주 깊은 중첩: python 은 RecursionError, 이 판은 한도([`harness_hook::py::toml::MAX_NESTING`])에서
//!   거절하거나 더 깊이 읽는다.

pub mod bash_writes;
pub mod bypass;
pub mod check;
pub mod context;
pub mod edit;
pub mod git;
pub mod halt;
pub mod lex;
pub mod memory;
pub mod pat;
pub mod plugins;
pub mod pyops;
pub mod pyval;
pub mod reuse;
pub mod rules;
pub mod stdout;
pub mod structure;

pub use context::Context;
