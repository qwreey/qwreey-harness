//! `qwreey-proc-guard hook <이름>`: 훅 입력(stdin JSON)을 읽어 그 훅을 돌리고 출력(stdout JSON)을 쓴다. 종료 코드는 늘 0 이다.
//!
//! 이름은 python 스크립트 이름과 같다: `heavy-proc-guard`, `self-match-guard`, `resource-guard`. 이벤트는 stdin 의
//! `hook_event_name` 에서 읽으므로 hooks.json 이 한 훅을 여러 이벤트에 걸어도 하위 명령은 하나다.
//! 하위 명령이 틀리면 stderr 에 쓰고 1 로 끝난다(2 는 PreToolUse 에서 도구를 막으므로 쓰지 않는다).

use std::io::Read;
use std::process::ExitCode;

use harness_hook::output::emit;
use harness_hook::{EnsureAscii, HookInput};
use qwreey_proc_guard::{Context, heavy, resource, self_match};

const HOOKS: &[&str] = &["heavy-proc-guard", "self-match-guard", "resource-guard"];

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let name = match args.as_slice() {
        [cmd, name] if cmd == "hook" && HOOKS.contains(&name.as_str()) => name.as_str(),
        _ => {
            eprintln!("usage: qwreey-proc-guard hook <{}>", HOOKS.join("|"));
            return ExitCode::from(1);
        }
    };

    // 읽지 못한 입력(JSON 이 아님, 객체가 아님)은 조용히 끝낸다
    let mut bytes = Vec::new();
    if std::io::stdin().lock().read_to_end(&mut bytes).is_err() {
        return ExitCode::SUCCESS;
    }
    let Ok(input) = HookInput::from_slice(&bytes) else {
        return ExitCode::SUCCESS;
    };

    let ctx = Context::from_process();
    let output = match name {
        "heavy-proc-guard" => heavy::run(&ctx, &input),
        "self-match-guard" => self_match::run(&ctx, &input),
        _ => resource::run(&ctx, &input),
    };
    if let Some(out) = output {
        emit(&out.render(EnsureAscii::Yes));
    }
    ExitCode::SUCCESS
}
