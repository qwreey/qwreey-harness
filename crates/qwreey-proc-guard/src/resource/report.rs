//! resource-guard 가 모델에게 보내는 core dump 글과, 명령이 크래시했는지 읽기.

use std::sync::LazyLock;

use harness_hook::py::num::parse_decimal;
use harness_hook::py::re::{self, Regex};
use harness_hook::py::text::split_whitespace;
use serde_json::Value;

use super::core::{CoreInfo, Found, signal_name};
use super::disk::gib;

const OUTPUT_TAIL: usize = 65536;
const GIB: u64 = 1 << 30;
const MIB: u64 = 1 << 20;

static CRASH_TEXT: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(concat!(
        r"core dumped|Segmentation fault|Bus error|Illegal instruction|Floating point exception",
        r"|\bSIG(?:SEGV|ABRT|BUS|FPE|ILL|QUIT|TRAP|SYS)\b|signal: (?:3|4|5|6|7|8|11|31)\b",
    ))
    .expect("built-in pattern")
});
static EXIT_CODE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"\AExit code (\d+)").expect("built-in pattern"));

/// 명령이 크래시한 흔적(짧은 글), 없으면 빈 글. 종료 코드는 PostToolUseFailure 의 error 첫 줄에서 읽는다.
pub fn crash_evidence(raw: &serde_json::Map<String, Value>) -> String {
    let text = if raw.get("hook_event_name").and_then(Value::as_str) == Some("PostToolUseFailure") {
        raw.get("error")
            .and_then(Value::as_str)
            .unwrap_or("")
            .to_owned()
    } else {
        let resp = raw.get("tool_response").and_then(Value::as_object);
        ["stdout", "stderr"]
            .iter()
            .filter_map(|k| resp.and_then(|r| r.get(*k)).and_then(Value::as_str))
            .collect::<Vec<_>>()
            .join("\n")
    };

    // 종료 코드 128+신호
    if let Some(m) = EXIT_CODE.match_start(&text)
        && let Some(code) = m.text(&text, 1).and_then(parse_decimal)
        && let Some(name) = i64::try_from(code).ok().and_then(|c| signal_name(c - 128))
    {
        return format!("exit code {code}, {name}");
    }

    // 출력 끝의 크래시 글
    let tail_start = text
        .char_indices()
        .rev()
        .nth(OUTPUT_TAIL - 1)
        .map_or(0, |(i, _)| i);
    let tail = &text[tail_start..];
    match CRASH_TEXT.search(tail) {
        Some(m) => format!("output says `{}`", &tail[m.start()..m.end()]),
        None => String::new(),
    }
}

/// core 의 프로그램 이름(pr_fname 또는 인자 첫 낱말의 basename)이 명령 글에 있는가.
pub fn program_in_command(info: &CoreInfo, command: &str) -> bool {
    let mut names = vec![info.program.clone()];
    if let Some(first) = split_whitespace(&info.args).next() {
        names.push(first.rsplit('/').next().unwrap_or(first).to_owned());
    }
    // pr_fname 은 15자에서 잘리므로 오른쪽 경계는 보지 않는다. 왼쪽 경계는 sh 가 bash 에 걸리지 않게
    names.iter().filter(|n| !n.is_empty()).any(|n| {
        let pattern = format!(r"(?<![A-Za-z0-9_.-]){}", re::escape(n));
        Regex::new(&pattern).is_ok_and(|rx| rx.is_match(command))
    })
}

fn size_text(n: u64) -> String {
    if n >= GIB {
        format!("{} GiB", gib(n as f64))
    } else if n >= MIB {
        format!("{:.1} MiB", n as f64 / MIB as f64)
    } else {
        format!("{} KiB", (n / 1024).max(1))
    }
}

fn core_lines(found: &[&Found]) -> Vec<String> {
    found
        .iter()
        .map(|f| {
            let program = if !f.info.program.is_empty() || !f.info.args.is_empty() {
                let shown = if f.info.args.is_empty() {
                    &f.info.program
                } else {
                    &f.info.args
                };
                format!("program `{shown}`")
            } else {
                "program unknown".to_owned()
            };
            let mut what = vec![size_text(f.size), program];
            if !f.info.signal.is_empty() {
                what.push(f.info.signal.clone());
            }
            format!("- `{}` ({})", f.path, what.join(", "))
        })
        .collect()
}

/// 이 명령의 core: 필요 없으면 지우라는 글(action).
pub fn core_action(found: &[&Found]) -> String {
    let mut lines = vec![
        "Core dump file(s) appeared after this command started, and the crashed program appears in the command \
         (or the command crashed and the program is unknown):"
            .to_owned(),
    ];
    lines.extend(core_lines(found));
    lines.push(
        "If the crash was intended (a repro, a crash test) or the dump is not needed, delete these files now. \
         If it may be needed for debugging, keep it and tell the user the path and size."
            .to_owned(),
    );
    lines.join("\n")
}

/// 이 명령의 것인지 모르는 core: 남기고 알리라는 글(warn).
pub fn core_notice(found: &[&Found]) -> String {
    let mut lines = vec![
        "Core dump file(s) appeared after this command started, but the crashed program does not appear in the command \
         or is unknown, so it may not be from this command (another session, a language server, or a crash while a \
         permission prompt was open):"
            .to_owned(),
    ];
    lines.extend(core_lines(found));
    lines.push("Keep these files and tell the user each path and size; delete them only if the user agrees.".to_owned());
    lines.join("\n")
}

/// core_pattern 이 처리기(`|...`)로 보낼 때의 안내(info).
pub fn handler_message(pattern: &str, evidence: &str) -> String {
    let handler = split_whitespace(&pattern[1..]).next().unwrap_or("?");
    let base = handler.rsplit('/').next().unwrap_or(handler);
    format!(
        "This command seems to have crashed ({evidence}), and core_pattern sends core dumps to a handler (`{base}`), not to a file here. \
         If the dump may be needed for debugging, tell the user where to find it (`coredumpctl list` for systemd-coredump, \
         /var/crash for apport); there is no file here to clean up."
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn evidence(v: Value) -> String {
        crash_evidence(v.as_object().unwrap())
    }

    #[test]
    fn reads_crash_evidence() {
        let failure =
            json!({"hook_event_name": "PostToolUseFailure", "error": "Exit code 139\nboom"});
        assert_eq!(evidence(failure), "exit code 139, SIGSEGV");
        let out = json!({"hook_event_name": "PostToolUse", "tool_response": {"stdout": "x", "stderr": "(signal: 11, SIGSEGV)"}});
        assert_eq!(evidence(out), "output says `signal: 11`");
        let fine = json!({"hook_event_name": "PostToolUseFailure", "error": "Exit code 1\n"});
        assert_eq!(evidence(fine), "");
    }

    #[test]
    fn program_matching_uses_a_left_boundary() {
        let info = |program: &str, args: &str| CoreInfo {
            program: program.into(),
            args: args.into(),
            signal: String::new(),
        };
        assert!(program_in_command(
            &info("python3", "/usr/bin/python3 x.py"),
            "python3 x.py"
        ));
        assert!(!program_in_command(&info("sh", ""), "bash run.sh"));
    }

    #[test]
    fn sizes_and_handler() {
        assert_eq!(size_text(500), "1 KiB");
        assert_eq!(size_text(3 * MIB / 2), "1.5 MiB");
        assert_eq!(size_text(GIB), "1.0 GiB");
        assert!(
            handler_message("|/usr/lib/systemd/systemd-coredump %P", "x")
                .contains("(`systemd-coredump`)")
        );
    }
}
