//! `qwreey-operator hook <delegate-nudge|subagent-bg-tasks>`: 훅 입력(stdin JSON)을 읽어 그 훅을 돌리고 출력을 쓴다.
//!
//! python 판처럼 뒤의 인자는 보지 않고, 종료 코드는 늘 0 이다. 하위 명령이 틀리면 stderr 에 쓰고 1 로 끝난다
//! (2 는 도구를 막으므로 쓰지 않는다).

use std::io::{Read, Write};
use std::process::ExitCode;

use harness_hook::HookEnv;
use harness_hook::py::json_load::{self, Decode};
use harness_hook::py::surrogate::encode_os;
use qwreey_operator::{bg_tasks, nudge};

const USAGE: &str = "usage: qwreey-operator hook <delegate-nudge|subagent-bg-tasks>";

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let name = match args.as_slice() {
        [cmd, name, ..] if cmd == "hook" => name.as_str(),
        _ => "",
    };
    if name != "delegate-nudge" && name != "subagent-bg-tasks" {
        eprintln!("{USAGE}");
        return ExitCode::from(1);
    }

    // python json.load(sys.stdin): input that is not a JSON object ends quietly
    let mut raw = Vec::new();
    if std::io::stdin().lock().read_to_end(&mut raw).is_err() {
        return ExitCode::SUCCESS;
    }
    let Some(input) = json_load::from_bytes(&raw, Decode::SurrogateEscape)
        .ok()
        .and_then(|v| v.into_dict().ok())
    else {
        return ExitCode::SUCCESS;
    };

    // Any python exception ends with no output
    let hook = HookEnv::from_process();
    let output = if name == "delegate-nudge" {
        nudge::run(&hook, &input)
    } else {
        bg_tasks::run(&hook, &input)
    };
    if let Ok(Some(text)) = output {
        print(&text);
    }
    ExitCode::SUCCESS
}

// python print(text): UTF-8 with surrogateescape. A lone surrogate that is not an escaped byte writes nothing
fn print(text: &str) {
    let Some(mut bytes) = encode_os(text) else {
        return;
    };
    bytes.push(b'\n');
    let mut out = std::io::stdout().lock();
    let _ = out.write_all(&bytes).and_then(|()| out.flush());
}
