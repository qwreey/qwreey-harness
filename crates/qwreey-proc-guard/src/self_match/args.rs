//! pgrep, pkill 호출 한 번의 인자 읽기(python 판의 `tokens`, `parse`).

use std::sync::LazyLock;

use harness_hook::rx::Regex;

use crate::shell::shlex::Lexer;

// procps-ng pgrep/pkill 에서 값을 받는 옵션
const ARG_SHORT: &str = "dgGOpPstuUFrq";
const ARG_LONG: &[&str] = &[
    "--delimiter",
    "--pgroup",
    "--group",
    "--older",
    "--pid",
    "--parent",
    "--session",
    "--terminal",
    "--euid",
    "--uid",
    "--pidfile",
    "--runstates",
    "--cgroup",
    "--ns",
    "--nslist",
    "--env",
    "--signal",
    "--queue",
];
const STOP_CHARS: &str = "();<>|&";

static SIGNAL_OPT: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"-(?:\d+|(?:SIG)?[A-Z][A-Z0-9]+(?:[+-]\d+)?)"));

/// 명령줄 전체를 패턴으로 찾는 호출(`-f`)의 패턴과 플래그.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Call {
    pub pattern: String,
    /// `-i`, `--ignore-case`
    pub icase: bool,
    /// `-x`, `--exact`
    pub exact: bool,
}

/// pgrep/pkill 뒤의 인자, 그 단순 명령 끝(따옴표 밖의 `)`, `;`, `|`, `>` 등)까지.
///
/// `closer` 는 `$(...)` 안이면 `)`, 백틱 안이면 `` ` `` 다. 그것으로 끝나는 낱말은 그 글자를 떼고 마지막 낱말이 된다.
pub fn tokens(rest: &str, closer: Option<char>) -> Vec<String> {
    let mut lex = Lexer::new(rest);
    let mut out = Vec::new();
    // 잘린 따옴표("$(pgrep -f x)" 의 닫는 따옴표만 남은 경우)는 거기서 멈춘다
    while let Ok(Some(t)) = lex.next_token() {
        if t.chars().all(|c| STOP_CHARS.contains(c)) {
            break;
        }
        if let Some(stripped) = closer.and_then(|c| t.strip_suffix(c)) {
            out.push(stripped.to_owned());
            break;
        }
        out.push(t);
    }
    out
}

/// 명령줄 전체를 패턴으로 찾으면 그 호출, 자기 셸에 걸릴 수 없는 꼴(`-f` 없음, `-v`, `-A`, 패턴 없음)이면 `None`.
pub fn parse(tool: &str, args: &[String]) -> Option<Call> {
    let mut full = false;
    let mut icase = false;
    let mut exact = false;
    let mut pattern: Option<&str> = None;
    let mut i = 0;
    while i < args.len() {
        let a = args[i].as_str();
        if a == "--" {
            pattern = args.get(i + 1).map(String::as_str);
            break;
        }

        if a.starts_with("--") {
            // 긴 옵션. 값 옵션이 `=` 없이 오면 다음 인자가 값이다
            let name = a.split('=').next().unwrap_or("");
            match name {
                "--full" => full = true,
                "--inverse" | "--ignore-ancestors" => return None,
                "--ignore-case" => icase = true,
                "--exact" => exact = true,
                _ if ARG_LONG.contains(&name) && !a.contains('=') => i += 1,
                _ => {}
            }
        } else if a.starts_with('-') && a.chars().count() > 1 {
            // 짧은 옵션 묶음. pkill 의 신호(-9, -KILL)는 옵션 하나
            let chars: Vec<char> = a.chars().collect();
            if tool == "pkill" && chars.len() > 2 && SIGNAL_OPT.fullmatch(a).is_some() {
                i += 1;
                continue;
            }
            for (j, c) in chars[1..].iter().enumerate() {
                match c {
                    'f' => full = true,
                    'v' | 'A' => return None,
                    'i' => icase = true,
                    'x' => exact = true,
                    c if ARG_SHORT.contains(*c) => {
                        // 묶음 끝의 값 옵션은 다음 인자가 값이다
                        if j == chars.len() - 2 {
                            i += 1;
                        }
                        break;
                    }
                    _ => {}
                }
            }
        } else {
            pattern = Some(a);
            break;
        }
        i += 1;
    }

    let pattern = pattern.filter(|p| full && !p.is_empty())?;
    Some(Call {
        pattern: pattern.to_owned(),
        icase,
        exact,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 이 파일의 고정 정규식이 두 regex crate 엔진과 py::re 에서 모두 만들어진다.
    #[test]
    fn fixed_patterns_build() {
        SIGNAL_OPT.check();
    }

    fn call(tool: &str, line: &str) -> Option<Call> {
        parse(tool, &tokens(line, None))
    }

    /// 플래그 뒤의 패턴을 따옴표를 풀어 읽고, `--` 뒤의 `-x` 는 패턴이다.
    #[test]
    fn reads_flags_and_pattern() {
        let c = call("pgrep", " -af 'python3 run.py'; do").unwrap();

        assert_eq!(c.pattern, "python3 run.py");
        assert_eq!(call("pkill", " -9 -f 'node x'").unwrap().pattern, "node x");
        assert_eq!(call("pgrep", " -f -- -x").unwrap().pattern, "-x");
    }

    /// 값을 받는 옵션, 신호 번호, 긴 옵션 이름이 앞에 와도 호출로 읽는다.
    #[test]
    fn other_option_forms_are_accepted() {
        assert!(call("pgrep", " -u root -f my-job").is_some());
        assert!(call("pkill", " -0 -f my-job").is_some());
        assert!(call("pgrep", " --full my-job").is_some());
    }

    /// 묶음 플래그에 `i` 가 있으면 대소문자를 가리지 않는 호출이다.
    #[test]
    fn i_flag_ignores_case() {
        assert!(call("pgrep", " -fix job").unwrap().icase);
    }

    /// 자기 자신과 맞을 수 없는 호출(`-x`, `-A`, `-v`, `-f` 없음, 패턴 없음)은 건너뛴다.
    #[test]
    fn skips_calls_that_cannot_self_match() {
        assert!(call("pgrep", " -x luau").is_none());
        assert!(call("pgrep", " -A -f job").is_none());
        assert!(call("pgrep", " -vf job").is_none());
        assert!(call("pgrep", " python3").is_none());
        assert!(call("pgrep", " -f").is_none());
    }

    /// 낱말은 `$(` 를 닫는 `)` 에서 끝난다.
    #[test]
    fn stops_at_the_closing_paren() {
        assert_eq!(tokens(" -f foo.py)\" ]", Some(')')), ["-f", "foo.py"]);
    }

    /// 낱말은 파이프에서 끝난다.
    #[test]
    fn stops_at_a_pipe() {
        assert_eq!(tokens(" -f job | wc -l", None), ["-f", "job"]);
    }
}
