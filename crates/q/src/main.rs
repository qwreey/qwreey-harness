//! `q hook <subagent-slots|stale-work|mise-hint>`, `q hook ambient UserPromptSubmit`: 훅 입력(stdin JSON)을 읽어 그 훅을
//! 돌리고 python 판과 같은 종료 코드와 stdout 을 낸다.
//!
//! python 판처럼 뒤의 인자는 보지 않는다(ambient 는 이벤트를 받는다). 하위 명령이 틀리거나 옮기지 않은 ambient 이벤트면
//! stderr 에 쓰고 1 로 끝난다(2 는 도구를 막으므로 쓰지 않는다). 옮기지 않은 이벤트는 python 판이 맡는다.

use std::io::{Read, Write};
use std::process::ExitCode;

use harness_hook::HookEnv;
use harness_hook::ambient::prompt_supplement;
use harness_hook::py::json_load::{self, Decode};
use harness_hook::py::surrogate::encode_os;
use q::slots::{self, Exit};
use q::{mise_hint, stale};

const USAGE: &str =
    "usage: q hook <subagent-slots|stale-work|mise-hint>\n       q hook ambient UserPromptSubmit";

/// 하위 명령.
#[derive(Clone, Copy)]
enum Command {
    SubagentSlots,
    StaleWork,
    MiseHint,
    AmbientPrompt,
}

fn parse(args: &[String]) -> Option<Command> {
    let args: Vec<&str> = args.iter().map(String::as_str).collect();
    match args.as_slice() {
        ["hook", "subagent-slots", ..] => Some(Command::SubagentSlots),
        ["hook", "stale-work", ..] => Some(Command::StaleWork),
        ["hook", "mise-hint", ..] => Some(Command::MiseHint),
        ["hook", "ambient", "UserPromptSubmit", ..] => Some(Command::AmbientPrompt),
        _ => None,
    }
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let Some(command) = parse(&args) else {
        eprintln!("{USAGE}");
        return ExitCode::from(1);
    };

    let mut raw = Vec::new();
    if std::io::stdin().lock().read_to_end(&mut raw).is_err() {
        return ExitCode::SUCCESS;
    }

    // Any python exception inside the hook body ends with no output
    let hook = HookEnv::from_process();
    match command {
        Command::SubagentSlots => match slots::run(&hook, &raw) {
            Exit::Quiet => {}
            Exit::Print(text) => write(&text, false),
            Exit::Crash => return ExitCode::from(1),
        },
        Command::StaleWork => {
            if let Ok(Some(text)) = stale::run(&hook, &raw) {
                write(&text, false);
            }
        }
        Command::MiseHint => {
            let input = json_load::from_bytes(&raw, Decode::SurrogateEscape)
                .ok()
                .and_then(|v| v.into_dict().ok());
            if let Some(Ok(Some(text))) = input.map(|input| mise_hint::run(&hook, &input)) {
                write(&text, false);
            }
        }
        Command::AmbientPrompt => {
            if let Some(bytes) = prompt_supplement(&hook, &raw) {
                write_bytes(&bytes);
            }
        }
    }
    ExitCode::SUCCESS
}

// python sys.stdout.write(text) (UTF-8, surrogateescape). A lone surrogate that is not an escaped byte writes nothing
fn write(text: &str, newline: bool) {
    let Some(mut bytes) = encode_os(text) else {
        return;
    };
    if newline {
        bytes.push(b'\n');
    }
    write_bytes(&bytes);
}

// 읽는 쪽이 먼저 닫았으면(EPIPE) 조용히 넘긴다
fn write_bytes(bytes: &[u8]) {
    let mut out = std::io::stdout().lock();
    let _ = out.write_all(bytes).and_then(|()| out.flush());
}
