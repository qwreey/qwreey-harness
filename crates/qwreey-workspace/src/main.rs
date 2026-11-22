//! `qwreey-workspace hook <이름> [이벤트]`: 훅 입력(stdin JSON)을 읽어 그 훅을 돌리고 출력(stdout JSON)을 쓴다. 종료 코드는 0 이다.
//!
//! 이름은 python 스크립트 이름과 같다: `workspace-gate`(인자로 이벤트를 받는다: PreToolUse, PostToolUse,
//! UserPromptExpansion), `sibling-notice`. python 판처럼 workspace-gate 의 이벤트가 없거나 모르는 것이면 아무것도 하지 않고,
//! 뒤의 인자는 보지 않는다. 하위 명령이 틀리면 stderr 에 쓰고 1 로 끝난다(2 는 PreToolUse 에서 도구를 막으므로 쓰지 않는다).

use std::io::Read;
use std::process::ExitCode;

use harness_hook::HookInput;
use harness_hook::output::emit;
use qwreey_workspace::context::Context;
use qwreey_workspace::{gate, sibling};

const USAGE: &str = "usage: qwreey-workspace hook <workspace-gate <event>|sibling-notice>";

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let (name, event) = match args.as_slice() {
        [cmd, name, rest @ ..] if cmd == "hook" => {
            (name.as_str(), rest.first().map_or("", String::as_str))
        }
        _ => ("", ""),
    };
    if name != "workspace-gate" && name != "sibling-notice" {
        eprintln!("{USAGE}");
        return ExitCode::from(1);
    }

    // 읽지 못한 입력(JSON 이 아님, 객체가 아님)은 조용히 끝낸다
    let mut bytes = Vec::new();
    if std::io::stdin().lock().read_to_end(&mut bytes).is_err() {
        return ExitCode::SUCCESS;
    }
    let Ok(input) = HookInput::from_slice(&bytes) else {
        return ExitCode::SUCCESS;
    };

    // python 판은 본문 전체를 try 로 감싸 어떤 예외든 출력 없이 넘긴다
    let ctx = Context::from_process();
    let output = if name == "workspace-gate" {
        gate::run(&ctx, event, &input)
    } else {
        sibling::run(&ctx, &input)
    };
    if let Ok(Some(text)) = output {
        emit(&text);
    }
    ExitCode::SUCCESS
}
