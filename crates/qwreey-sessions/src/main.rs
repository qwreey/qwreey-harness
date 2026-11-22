//! `qwreey-sessions hook <훅> [이벤트]`: 훅 입력(stdin JSON)을 읽어 그 훅을 돌리고 출력(stdout JSON)을 쓴다. 종료 코드는 늘 0 이다.
//!
//! 하위 명령이 틀리거나 옮기지 않은 이벤트면 stderr 에 쓰고 1 로 끝난다(2 는 PreToolUse 에서 도구를 막으므로 쓰지 않는다).
//! hooks.json 이 잘못 걸렸을 때 조용히 지나가지 않게 한다: 옮기지 않은 이벤트는 python 판(`scripts/hook.py`)이 맡는다.

use std::fmt::Write as _;
use std::io::{Read, Write};
use std::process::ExitCode;

use harness_hook::HookInput;
use harness_hook::output::emit;
use harness_hook::py::path::pathlib_join;
use qwreey_sessions::abort::Abort;
use qwreey_sessions::context::Context;
use qwreey_sessions::{records_read, session_log, store};

const USAGE: &str = "usage: qwreey-sessions hook session-log <PostToolUse|UserPromptSubmit|PreToolUse>\n       \
                     qwreey-sessions hook records-read [PreToolUse|PostToolUse]";

/// 하위 명령.
enum Command {
    SessionLog(session_log::Event),
    RecordsRead(records_read::Event),
}

fn parse(args: &[String]) -> Option<Command> {
    let args: Vec<&str> = args.iter().map(String::as_str).collect();
    match args.as_slice() {
        ["hook", "session-log", event] => session_log::Event::parse(event).map(Command::SessionLog),
        ["hook", "records-read"] => Some(Command::RecordsRead(records_read::Event::from_arg(None))),
        ["hook", "records-read", event] => Some(Command::RecordsRead(
            records_read::Event::from_arg(Some(event)),
        )),
        _ => None,
    }
}

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let Some(command) = parse(&args) else {
        eprintln!("{USAGE}");
        return ExitCode::from(1);
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
    match command {
        Command::SessionLog(event) => {
            let run = session_log::run(&ctx, event, &input);
            if let Some(out) = run.stdout {
                emit(&out);
            }
            if let Some(error) = run.error {
                log_error(&ctx, event, error);
            }
        }
        Command::RecordsRead(event) => {
            if let Some(out) = records_read::run(&ctx, event, &input) {
                emit(&out);
            }
        }
    }
    ExitCode::SUCCESS
}

/// python `log_error`: `<저장소 루트>/hook-errors.log` 에 한 줄. 쓰지 못하면 넘긴다.
fn log_error(ctx: &Context, event: session_log::Event, error: Abort) {
    let dir = ctx.config().home(&ctx.hook.env);
    if store::mkdir_all(&dir).is_err() {
        return;
    }
    let Some(path) = qwreey_sessions::fsx::os_path(&pathlib_join(&dir, "hook-errors.log")) else {
        return;
    };
    let mut line = String::new();
    let _ = write!(line, "{}", jiff::Zoned::now().strftime("%Y-%m-%dT%H:%M:%S"));
    let _ = writeln!(
        line,
        " ['{}'] Abort: {} (qwreey-sessions)",
        event.as_str(),
        error.0
    );
    if let Ok(mut file) = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)
    {
        let _ = file.write_all(line.as_bytes());
    }
}
