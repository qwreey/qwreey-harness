//! self-match-guard(PreToolUse Bash): `pgrep -f PAT`, `pkill -f PAT` 의 패턴이 그것을 부른 셸 자신에 걸린다(`hooks/self-match-guard.py`).
//!
//! 왜: Claude Code 는 Bash 명령을 `bash -c '... <명령> ...'` 로 돌려 셸의 argv 에 명령 전체가 든다. `pgrep -f` 는 전체 명령줄에서
//! 찾고 자기만 빼지 부모 셸은 빼지 않으므로, 명령에 든 패턴은 늘 그 셸을 찾는다. 배경의 `until ! pgrep -f X; do sleep 2; done` 이
//! 자기 셸을 몇 시간 기다렸고, `pkill -f X` 는 자기를 돌리는 셸을 죽일 수 있다.
//!
//! 판정: 명령 자리(구간 머리, 루프 낱말과 접두 뒤, `$(...)`, 백틱 안)의 pgrep/pkill 이 `-f` 와 패턴을 가지면, 패턴을 python 정규식으로
//! 명령 글(셸의 argv)에 맞춰 본다. while/until 루프 안이면 deny, 밖이면 pkill 은 warn, pgrep 은 info. heredoc 본문은 먼저 버리고
//! git/gh 명령은 통과한다.

pub mod args;

use std::collections::HashMap;
use std::sync::LazyLock;

use harness_hook::py::re::{self, Flags, Regex};
use harness_hook::py::text::split_whitespace;
use harness_hook::py::unicode::is_alnum;
use harness_hook::tag::{self, Level, Notices};
use harness_hook::{HookInput, HookOutput};

use crate::context::Context;
use crate::shell::segments;

const TAG: &str = "self-match-guard";
const EXEMPT_HEADS: &[&str] = &["git", "gh"];
// 명령 자리 앞에 올 수 있는 낱말: 셸 키워드와 다른 프로그램을 실행하는 접두
const LEAD_WORDS: &[&str] = &[
    "while", "until", "if", "elif", "then", "do", "else", "!", "{", "(", "time", "nice", "nohup",
    "exec", "command", "env", "sudo", "timeout",
];
const SHELL_NOTE: &str =
    "Claude Code runs each Bash command through a shell whose argv holds the whole command line";

fn regex(pattern: &str) -> Regex {
    Regex::new(pattern).expect("built-in pattern compiles")
}

static FINDER: LazyLock<Regex> =
    LazyLock::new(|| regex(r"(?:(?<=\$\()|(?<=`)|(?<![^\s({!]))(?:[\w./-]*/)?(pgrep|pkill)(?=\s)"));
// shell_segments 는 `&&` 까지만 나눈다. 배경 실행 `a & until ...` 의 `&` 도 나눠야 루프 머리를 본다(`2>&1`, `&>` 는 그대로)
static BACKGROUND: LazyLock<Regex> = LazyLock::new(|| regex(r"(?<![>&<])&(?![>&])"));
static ASSIGN: LazyLock<Regex> =
    LazyLock::new(|| regex(r#"(?:^|[;&|\s(])([A-Za-z_]\w*)=("[^"]*"|'[^']*'|[^\s;&|)]*)"#));
static VAR_USE: LazyLock<Regex> = LazyLock::new(|| regex(r"\$\{?([A-Za-z_]\w*)\}?"));
static LEAD_NUMBER: LazyLock<Regex> = LazyLock::new(|| regex(r"[\d.]+[smhd]?"));
static LEAD_ASSIGN: LazyLock<Regex> = LazyLock::new(|| regex(r"[A-Za-z_]\w*=\S*"));

/// 자기 셸에 걸리는 호출 하나.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Hit {
    /// `pgrep` 또는 `pkill`.
    pub tool: String,
    /// 명령에 쓰인 그대로의 패턴(변수를 펼치기 전).
    pub pattern: String,
    /// while/until 루프(조건이나 몸) 안인가.
    pub in_wait_loop: bool,
}

/// 패턴이 python 에서 re.error 가 아닌 예외(OverflowError, 깊은 중첩의 RecursionError)를 낸다. python 훅은 그때 아무것도 내지 않는다.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct PatternOverflow;

/// 훅 하나를 돌린다.
pub fn run(ctx: &Context, input: &HookInput) -> Option<HookOutput> {
    let cmd = input.command()?;
    if !cmd.contains("pgrep") && !cmd.contains("pkill") {
        return None;
    }
    if segments(cmd)
        .first()
        .is_some_and(|s| EXEMPT_HEADS.contains(&s.head.as_str()))
    {
        return None;
    }
    let hits = find(cmd).ok()?;
    if hits.is_empty() {
        return None;
    }

    // python 은 nonce 를 만들다 예외가 나면 아무것도 내지 않는다
    let nonce = ctx.nonce(input).ok()?;
    let notices = messages(&hits);
    Some(match deny_text(&hits) {
        Some(text) => {
            HookOutput::deny(tag::harness_hook(TAG, Level::Action, nonce.as_ref(), &text))
        }
        None => HookOutput::context("PreToolUse", notices.render(TAG, nonce.as_ref())),
    })
}

/// 자기 셸에 걸리는 pgrep/pkill -f 호출들, 처음 나온 순서로 겹침 없이.
pub fn find(cmd: &str) -> Result<Vec<Hit>, PatternOverflow> {
    let mut hits: Vec<Hit> = Vec::new();
    // 열린 루프: true 면 while/until, false 면 for/select
    let mut loops: Vec<bool> = Vec::new();
    // 명령의 대입은 한 번만 모은다(호출이 수천 개인 명령에서 매번 명령 전체를 훑지 않게)
    let mut values: Option<Assignments> = None;
    for seg in segments(cmd) {
        for part in BACKGROUND.split(&seg.text) {
            track_loops(part, &mut loops);
            let in_wait_loop = loops.contains(&true);
            for (tool, call) in calls(part) {
                let values = values.get_or_insert_with(|| assignments(cmd));
                let Some(pattern) = resolve_with(&call.pattern, values) else {
                    continue;
                };
                if !self_matches(&pattern, call.icase, call.exact, cmd)? {
                    continue;
                }
                let hit = Hit {
                    tool,
                    pattern: call.pattern,
                    in_wait_loop,
                };
                if !hits.contains(&hit) {
                    hits.push(hit);
                }
            }
        }
    }
    Ok(hits)
}

// 구간 머리의 루프 낱말로 열린 루프를 따라간다(`done` 이 닫는다). 다른 낱말을 만나면 그친다
fn track_loops(part: &str, loops: &mut Vec<bool>) {
    let spaced = part.replace('(', " ( ");
    for w in split_whitespace(&spaced) {
        let w = w.trim_end_matches(')');
        match w {
            "while" | "until" => loops.push(true),
            "for" | "select" => {
                loops.push(false);
                break;
            }
            "done" => {
                loops.pop();
            }
            w if LEAD_WORDS.contains(&w) => {}
            _ => break,
        }
    }
}

// 구간 조각 안의 명령 자리 pgrep/pkill 마다 (도구, 호출)
fn calls(part: &str) -> Vec<(String, args::Call)> {
    let mut out = Vec::new();
    for m in FINDER.find_iter(part) {
        let before = &part[..m.start()];
        let closer = if before.ends_with("$(") {
            Some(')')
        } else if before.ends_with('`') {
            Some('`')
        } else {
            None
        };
        if closer.is_none() && !lead_ok(before) {
            continue;
        }

        // 백틱 안의 패턴에는 백틱이 없다. 먼저 잘라야 바깥 따옴표가 낱말을 망치지 않는다
        let mut rest = &part[m.end()..];
        if closer == Some('`') {
            rest = rest.split('`').next().unwrap_or("");
        }
        let tool = m.text(part, 1).expect("tool group");
        if let Some(call) = args::parse(tool, &args::tokens(rest, closer)) {
            out.push((tool.to_owned(), call));
        }
    }
    out
}

// 프로그램 앞의 낱말이 모두 셸 키워드, 접두, 대입, 접두 옵션인가
fn lead_ok(before: &str) -> bool {
    let spaced = before.replace('(', " ( ");
    split_whitespace(&spaced).all(|w| {
        LEAD_WORDS.contains(&w)
            || w.starts_with('-')
            || LEAD_NUMBER.fullmatch(w).is_some()
            || LEAD_ASSIGN.fullmatch(w).is_some()
    })
}

/// 명령의 대입: 이름마다 마지막 값(따옴표를 뗀 것).
pub type Assignments = HashMap<String, String>;

/// 명령의 `NAME=value` 대입을 모은다(python 은 dict 에 차례로 넣어 뒤의 값이 이긴다).
pub fn assignments(cmd: &str) -> Assignments {
    ASSIGN
        .find_iter(cmd)
        .iter()
        .map(|m| {
            let name = m.text(cmd, 1).expect("name group");
            let value = m.text(cmd, 2).expect("value group");
            (name.to_owned(), unquote(value))
        })
        .collect()
}

/// 패턴의 `$VAR` 를 같은 명령의 대입 값으로 채운다. 모르는 변수가 남으면 `None`.
pub fn resolve(pattern: &str, cmd: &str) -> Option<String> {
    resolve_with(pattern, &assignments(cmd))
}

/// [`resolve`] 를 미리 모은 대입으로.
pub fn resolve_with(pattern: &str, values: &Assignments) -> Option<String> {
    let mut missing = false;
    let out = VAR_USE.replace_all(pattern, |m| {
        let name = m.text(pattern, 1).expect("name group");
        match values.get(name) {
            Some(v) => v.clone(),
            None => {
                missing = true;
                pattern[m.start()..m.end()].to_owned()
            }
        }
    });
    (!missing).then_some(out)
}

// python `v[1:-1] if v[:1] in "\"'" and len(v) > 1 else v`: 따옴표로 시작하면 앞뒤 한 글자씩 뗀다(끝이 따옴표가 아니어도)
fn unquote(v: &str) -> String {
    let mut chars = v.chars();
    match chars.next() {
        Some('"' | '\'') if v.chars().count() > 1 => {
            chars.next_back();
            chars.as_str().to_owned()
        }
        _ => v.to_owned(),
    }
}

/// 패턴이 셸의 argv(`/bin/bash -c <명령>`)에 맞는가. python 이 읽지 못하는 패턴은 글자 그대로 들어 있는지로 짐작한다.
///
/// py::re 가 옮기지 않은 문법(python 은 읽는다)은 맞지 않는다고 본다. 패턴은 명령 안에 있으므로 글자 비교는 늘 맞아서,
/// python 이 통과시키는 명령을 막게 된다. 훅은 실패로 막지 않는다: 모를 때는 통과다.
pub fn self_matches(
    pattern: &str,
    icase: bool,
    exact: bool,
    cmd: &str,
) -> Result<bool, PatternOverflow> {
    let argv = format!("/bin/bash -c {cmd}");
    let flags = if icase {
        Flags::IGNORECASE
    } else {
        Flags::NONE
    };
    match Regex::with_flags(pattern, flags) {
        Ok(rx) if exact => Ok(rx.fullmatch(&argv).is_some()),
        Ok(rx) => Ok(rx.is_match(&argv)),
        Err(re::Error::Overflow | re::Error::TooDeep) => Err(PatternOverflow),
        Err(re::Error::Unsupported(_)) => Ok(false),
        // POSIX 클래스처럼 python 이 못 읽는 ERE
        Err(re::Error::Syntax(_)) if icase => {
            Ok(argv.to_lowercase().contains(&pattern.to_lowercase()))
        }
        Err(re::Error::Syntax(_)) => Ok(argv.contains(pattern)),
    }
}

fn bracket(pattern: &str) -> String {
    let mut chars = pattern.chars();
    match chars.next() {
        Some(c) if is_alnum(c) => format!("[{c}]{}", chars.as_str()),
        _ => "[t]est-delegate".to_owned(),
    }
}

fn short(pattern: &str) -> String {
    if pattern.chars().count() <= 60 {
        return pattern.to_owned();
    }
    format!("{}...", pattern.chars().take(57).collect::<String>())
}

fn alternatives(tool: &str, pattern: &str) -> String {
    format!(
        "`{tool} -x <process name>` (matches the name, not the command line); the bracket trick `{tool} -f \"{}\"`, whose own text no \
         longer matches (only while the plain text appears nowhere else in the command); or `{tool} -A -f` (procps-ng 4.0.3+, skips \
         the calling shell)",
        bracket(pattern)
    )
}

/// 루프 안의 호출이 있으면 deny 사유 글(첫 호출).
pub fn deny_text(hits: &[Hit]) -> Option<String> {
    let hit = hits.iter().find(|h| h.in_wait_loop)?;
    let kills = if hit.tool == "pkill" {
        " and pkill kills the shell running it"
    } else {
        ""
    };
    Some(format!(
        "`{} -f \"{}\"` runs inside a while/until loop. {SHELL_NOTE}, so the pattern matches that shell itself: the loop never ends{kills}. \
         Re-run with {}. To wait for a job, run it with run_in_background and wait for its completion notification instead of polling.",
        hit.tool,
        short(&hit.pattern),
        alternatives(&hit.tool, &hit.pattern)
    ))
}

/// 루프 밖 호출의 알림: pkill 은 warn, pgrep 은 info.
pub fn messages(hits: &[Hit]) -> Notices {
    let mut notices = Notices::new();
    for h in hits {
        let p = short(&h.pattern);
        let alt = alternatives(&h.tool, &h.pattern);
        if h.tool == "pkill" {
            notices.push(
                Level::Warn,
                format!(
                    "`pkill -f \"{p}\"` also matches the shell running this command ({SHELL_NOTE}), so it can kill that shell and cut the \
                     command short. If you mean another process, consider {alt}; if losing the rest of this command does not matter, \
                     nothing to do."
                ),
            );
        } else {
            notices.push(
                Level::Info,
                format!(
                    "`pgrep -f \"{p}\"` also matches the shell running this command ({SHELL_NOTE}), so it finds at least that shell and \
                     succeeds. If the result or exit status matters, consider {alt}; otherwise nothing to do."
                ),
            );
        }
    }
    notices
}

#[cfg(test)]
mod tests {
    use super::*;

    fn hits(cmd: &str) -> Vec<Hit> {
        find(cmd).unwrap()
    }

    fn denied(cmd: &str) -> bool {
        deny_text(&hits(cmd)).is_some()
    }

    #[test]
    fn loops_are_denied() {
        for cmd in [
            "until ! pgrep -f \"test-delegate-cli.py\" >/dev/null; do sleep 2; done",
            "while pgrep -f my-job; do sleep 1; done",
            "while [ -n \"$(pgrep -f foo.py)\" ]; do sleep 1; done",
            "until [ -z \"`pgrep -f foo.py`\" ]; do sleep 1; done",
            "while pgrep -fl worker >/dev/null\ndo\n  sleep 2\ndone",
            "P=test-delegate; until ! pgrep -f \"$P\"; do sleep 2; done",
            "python3 test-delegate.py & until ! pgrep -f \"[t]est-delegate\"; do sleep 2; done",
        ] {
            assert!(denied(cmd), "{cmd}");
        }
    }

    #[test]
    fn outside_loops_is_a_notice() {
        let h = hits("pkill -9 -f 'node server.js'");
        assert!(deny_text(&h).is_none() && h[0].tool == "pkill");
        assert!(!denied("for i in 1 2; do pgrep -f job; done"));
        assert!(!denied("while false; do :; done; pgrep -f job"));
        assert_eq!(hits("pgrep -fl worker | wc -l").len(), 1);
    }

    #[test]
    fn safe_forms_pass() {
        for cmd in [
            "until ! pgrep -f \"[t]est-delegate-cli.py\"; do sleep 2; done",
            "until ! pgrep -x luau; do sleep 2; done",
            "until ! pgrep -f \"$JOB\"; do sleep 2; done",
            "until ! pgrep -fx test-delegate; do sleep 2; done",
            "echo 'pgrep -f x in a while loop'",
            "grep -n 'pgrep -f' SKILL.md",
            "cat > notes.md <<'EOF'\nwhile pgrep -f job; do sleep 1; done\nEOF",
        ] {
            assert!(hits(cmd).is_empty(), "{cmd}");
        }
    }

    #[test]
    fn overflowing_pattern_stops_the_hook() {
        assert_eq!(find("pgrep -f 'a{99999999999}'"), Err(PatternOverflow));

        // python 은 깊은 중첩에서 RecursionError 로 아무것도 내지 않는다. 2만 겹도 스택을 넘지 않는다
        for depth in [600, 20_000] {
            let p = format!("{}x{}", "(?:".repeat(depth), ")".repeat(depth));
            let cmd = format!("while pgrep -f '{p}'; do sleep 1; done");
            assert_eq!(find(&cmd), Err(PatternOverflow), "{depth}");
        }
    }

    #[test]
    fn patterns_python_reads_but_we_do_not_never_deny() {
        // 범위 플래그, (?x), \N{...}: python 은 읽고 명령에 맞지 않아 통과. 글자 비교로 짐작하면 늘 맞아 막았었다
        for p in ["(?i:x)y", "(?x)a b", "\\N{EM DASH}", "(?-i:a)b"] {
            let cmd = format!("while pgrep -f '{p}'; do sleep 1; done");
            assert!(hits(&cmd).is_empty(), "{p}");
        }

        // 큰 되풀이 수는 이제 옮긴다: 명령에 맞지 않으니 통과
        for p in ["x{2000}", "(?:x{500}){500}"] {
            let cmd = format!("while pgrep -f '{p}'; do sleep 1; done");
            assert!(hits(&cmd).is_empty(), "{p}");
        }

        // python 3.14 의 \z
        assert!(denied("while pgrep -f 'done\\z'; do sleep 1; done"));
    }

    #[test]
    fn helpers_follow_python() {
        assert_eq!(bracket("test"), "[t]est");
        assert_eq!(bracket("-x"), "[t]est-delegate");
        assert_eq!(short(&"a".repeat(61)), format!("{}...", "a".repeat(57)));
        assert_eq!(unquote("\"abc"), "ab");
        assert_eq!(resolve("${A}x$B", "A=1 B='2'").as_deref(), Some("1x2"));
        assert_eq!(resolve("$C", "A=1"), None);
    }
}
