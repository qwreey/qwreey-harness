//! `qwreey-conventions hook <훅>`: 훅 입력(stdin JSON)을 읽어 그 훅을 돌리고 출력(stdout)을 쓴다.
//!
//! 종료 코드는 python 판과 같다: 보통 0, python 이 잡지 않는 예외로 끝나는 입력이면 1(stderr 에 한 줄).
//! 하위 명령이 틀리면 stderr 에 쓰고 1 로 끝난다(2 는 막는 코드라 쓰지 않는다).

use std::io::{Read, Write};
use std::process::ExitCode;

use harness_hook::HookInput;
use harness_hook::input::InputError;
use qwreey_conventions::context::Context;
use qwreey_conventions::halt::{Halt, Result};
use qwreey_conventions::{check, memory, reuse, rules, stdout, structure};

const USAGE: &str = "usage: qwreey-conventions hook <conventions-check|reuse-check|structure-reminder|memory-placement|\
                     rules-inject|bash-bypass-reminder|bash-writes>";

/// 하위 명령 하나: python 스크립트 하나.
struct Hook {
    name: &'static str,
    /// 끄기 스위치(python `conv_env.is_off`). stdin 을 읽기 전에 본다. 없으면 훅이 스스로 본다.
    switch: Option<&'static str>,
    /// stdin 이 JSON 이지만 객체가 아닐 때 python 이 예외로 끝나는가(`data.get` 의 AttributeError).
    crash_on_non_object: bool,
    /// 출력을 쓰다 실패해도(짝 없는 서로게이트) python 판이 예외를 잡아 0 으로 끝나는가. 쓴 데까지는 나간다.
    catches_output_error: bool,
    run: fn(&Context, &HookInput) -> Result<Option<String>>,
}

const HOOKS: &[Hook] = &[
    Hook {
        name: "conventions-check",
        switch: Some("CONVENTIONS_CHECK"),
        crash_on_non_object: true,
        catches_output_error: false,
        run: check::run,
    },
    Hook {
        name: "reuse-check",
        switch: Some("CONVENTIONS_CHECK"),
        crash_on_non_object: true,
        catches_output_error: false,
        run: reuse::run,
    },
    Hook {
        name: "structure-reminder",
        switch: Some("STRUCTURE_REMINDER"),
        crash_on_non_object: true,
        catches_output_error: false,
        run: structure::run,
    },
    // python 판은 본문 전체를 try 로 감싸 무엇이든 조용히 넘긴다
    Hook {
        name: "memory-placement",
        switch: Some("MEMORY_PLACEMENT"),
        crash_on_non_object: false,
        catches_output_error: false,
        run: memory::run,
    },
    // 아래 셋은 python 판이 본문 전체를 try 로 감싼다(rules-inject 의 끄기 스위치는 plugin.json 을 읽은 뒤에 본다)
    Hook {
        name: "rules-inject",
        switch: None,
        crash_on_non_object: false,
        catches_output_error: true,
        run: rules::run,
    },
];

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let hook = match args.as_slice() {
        [cmd, name] if cmd == "hook" => HOOKS.iter().find(|h| h.name == name),
        _ => None,
    };
    let Some(hook) = hook else {
        eprintln!("{USAGE}");
        return ExitCode::from(1);
    };

    let ctx = Context::from_process();
    if hook.switch.is_some_and(|sw| ctx.is_off(sw)) {
        return ExitCode::SUCCESS;
    }

    // 읽지 못한 입력(JSON 이 아님)은 조용히 끝낸다
    let mut bytes = Vec::new();
    if std::io::stdin().lock().read_to_end(&mut bytes).is_err() {
        return ExitCode::SUCCESS;
    }
    let input = match HookInput::from_slice(&bytes) {
        Ok(input) => input,
        Err(InputError::NotObject) if hook.crash_on_non_object => {
            return crash("hook input is not a JSON object");
        }
        Err(_) => return ExitCode::SUCCESS,
    };

    match (hook.run)(&ctx, &input) {
        Ok(Some(out)) => {
            let (bytes, whole) = stdout::python_bytes(&out);
            let mut stdout = std::io::stdout().lock();
            let _ = stdout.write_all(&bytes).and_then(|()| stdout.flush());
            if whole || hook.catches_output_error {
                ExitCode::SUCCESS
            } else {
                crash("a lone surrogate in the output")
            }
        }
        Ok(None) | Err(Halt::Unported(_)) => ExitCode::SUCCESS,
        Err(Halt::PyError(what)) => crash(what),
    }
}

// python 의 잡지 않은 예외 자리: stdout 없이 1
fn crash(what: &str) -> ExitCode {
    eprintln!("qwreey-conventions: {what} (the python hook raises here)");
    ExitCode::from(1)
}
