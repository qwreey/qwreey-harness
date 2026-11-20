//! `qwreey-advisor hook <훅> [이벤트]`: 훅 입력(stdin JSON)을 읽어 그 훅을 돌리고 python 판과 같은 종료 코드, stdout, stderr 를 낸다.
//!
//! 하위 명령이 틀리거나 옮기지 않은 이벤트면 stderr 에 쓰고 1 로 끝난다(2 는 PreToolUse 에서 도구를 막으므로 쓰지 않는다).
//! hooks.json 이 잘못 걸렸을 때 조용히 지나가지 않게 한다: 옮기지 않은 이벤트(ambient 의 SessionStart 등)는 python 판이 맡는다.

use std::io::{Read, Write};
use std::process::ExitCode;

use qwreey_advisor::{Context, Outcome, ambient, expand_inherit, guard, nudge, track_reviewer};

const USAGE: &str = "usage: qwreey-advisor hook <readonly-for-reviewers|second-opinion-nudge|expand-inherit-prompt|track-reviewer>\n       \
                     qwreey-advisor hook ambient UserPromptSubmit";

/// 하위 명령.
#[derive(Clone, Copy)]
enum Command {
    ReadonlyForReviewers,
    SecondOpinionNudge,
    ExpandInheritPrompt,
    TrackReviewer,
    AmbientPrompt,
}

fn parse(args: &[String]) -> Option<Command> {
    let args: Vec<&str> = args.iter().map(String::as_str).collect();
    match args.as_slice() {
        ["hook", "readonly-for-reviewers"] => Some(Command::ReadonlyForReviewers),
        ["hook", "second-opinion-nudge"] => Some(Command::SecondOpinionNudge),
        ["hook", "expand-inherit-prompt"] => Some(Command::ExpandInheritPrompt),
        ["hook", "track-reviewer"] => Some(Command::TrackReviewer),
        ["hook", "ambient", "UserPromptSubmit"] => Some(Command::AmbientPrompt),
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

    let ctx = Context::from_process();
    let outcome = match command {
        Command::ReadonlyForReviewers => guard::run(&ctx, &raw),
        Command::SecondOpinionNudge => nudge::run(&ctx, &raw),
        Command::ExpandInheritPrompt => expand_inherit::run(&ctx, &raw),
        Command::TrackReviewer => track_reviewer::run(&ctx, &raw),
        Command::AmbientPrompt => ambient::run(&ctx, &raw),
    };
    write(&outcome)
}

// 읽는 쪽이 먼저 닫았으면(EPIPE) 조용히 넘긴다
fn write(outcome: &Outcome) -> ExitCode {
    if !outcome.stdout.is_empty() {
        let mut out = std::io::stdout().lock();
        let _ = out.write_all(&outcome.stdout).and_then(|()| out.flush());
    }
    if !outcome.stderr.is_empty() {
        let _ = std::io::stderr().lock().write_all(&outcome.stderr);
    }
    ExitCode::from(outcome.code)
}
