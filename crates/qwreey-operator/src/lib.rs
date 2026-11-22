//! qwreey-operator 플러그인의 자주 뜨는 훅 둘을 한 바이너리로(`plugins/qwreey-operator/hooks/*.py` 의 Rust 판).
//!
//! 출력(종료 코드와 stdout)은 python 판과 바이트로 같다. 훅마다 하위 명령 하나다(`qwreey-operator hook <이름>`):
//! - [`nudge`]: `delegate-nudge.py`, 메인이 한 턴에 코드를 많이 쓰면 위임을 권한다(PostToolUse, UserPromptSubmit)
//! - [`bg_tasks`]: `subagent-bg-tasks.py`, 서브에이전트가 자기 백그라운드 작업을 남긴 채 끝내려 하면 알린다(SubagentStop)
//!
//! 어떤 훅도 오류로 끝나지 않는다: 읽지 못한 입력과 python 이 예외로 끝나는 입력은 아무것도 내지 않고 종료 코드 0 이다
//! ([`stop::Stop`]). 세션 시작과 compact 의 훅(ambient, compact_epoch)은 python 이다. 두 판은 같은 상태 파일을 같은 꼴로 쓴다.

pub mod bg_tasks;
pub mod nudge;
pub mod stop;
pub mod switch;
