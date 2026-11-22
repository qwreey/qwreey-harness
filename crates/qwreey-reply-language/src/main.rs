//! `qwreey-reply-language hook reply-language`: 훅 입력(stdin JSON)을 읽어 python 판과 같은 stdout 을 쓴다. 종료 코드는 늘 0 이다.
//!
//! 하위 명령이 틀리면 stderr 에 쓰고 1 로 끝난다. `set <language>` 는 python 판(`hooks/reply_language.py set`)이 맡는다.

use std::io::{Read, Write};
use std::process::ExitCode;

use harness_hook::HookEnv;

const USAGE: &str = "usage: qwreey-reply-language hook reply-language";

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    if args != ["hook", "reply-language"] {
        eprintln!("{USAGE}");
        return ExitCode::from(1);
    }

    let mut raw = Vec::new();
    if std::io::stdin().lock().read_to_end(&mut raw).is_err() {
        return ExitCode::SUCCESS;
    }
    let out = qwreey_reply_language::run(&HookEnv::from_process(), &raw);
    if !out.is_empty() {
        let mut stdout = std::io::stdout().lock();
        let _ = stdout.write_all(&out).and_then(|()| stdout.flush());
    }
    ExitCode::SUCCESS
}
