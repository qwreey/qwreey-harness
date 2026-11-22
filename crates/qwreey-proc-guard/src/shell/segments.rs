//! Bash 명령을 구간으로 나눈다(`hooks/shell_segments.py`). heavy-proc-guard 와 self-match-guard 가 같이 쓴다.
//!
//! 셸 문법을 다 읽지는 않는다: heredoc 본문을 버리고 `&&`, `||`, `;`, `|`, 줄바꿈으로 나눈 뒤 각 구간의 머리 프로그램을 찾는다.
//! 따옴표 안의 구분자도 나누므로 훅은 오탐 쪽으로 기운다. 정규식은 python 판의 글 그대로 [`harness_hook::rx`] 로 돈다(HEREDOC 만 결과가 같은 꼴로 줄였다).

use std::sync::LazyLock;

use harness_hook::py::text::split_whitespace;
use harness_hook::rx::Regex;

const PREFIX_WORDS: &[&str] = &["(", "{", "time", "nice", "env", "command", "exec", "nohup"];
const TIMEOUT_VALUE_OPTIONS: &[&str] = &["-s", "-k", "--signal", "--kill-after"];

// python 판은 `<<(?!<)` 로 시작한다. `<<` 뒤의 나머지는 `-`, 공백, 따옴표, `\`, 이름 글자로만 시작해 `<` 에서는 맞지 않으므로
// 그 앞 보기는 결과를 바꾸지 않는다(시험 `heredoc_without_lookahead_is_the_same`)
static HEREDOC: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(r#"<<-?\s*(?:'([A-Za-z_]\w*)'|"([A-Za-z_]\w*)"|\\?([A-Za-z_]\w*))"#)
});
static SPLIT: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"&&|\|\||[;|\n]"));
static ASSIGN_WORD: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"[A-Za-z_][A-Za-z0-9_]*=\S*"));
static DURATION: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"[\d.]+[smhd]?"));

/// 구간 하나: 머리 프로그램과 구간 글.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Segment {
    /// `env`, `time`, `timeout 5`, `mise exec --` 같은 접두 뒤의 첫 낱말.
    pub head: String,
    pub text: String,
}

/// heredoc 본문을 뺀 명령. 버린 본문 줄은 `dropped` 에 차례로 더한다(python `strip_heredocs(cmd, dropped)`).
pub fn strip_heredocs(cmd: &str, mut dropped: Option<&mut Vec<String>>) -> String {
    let mut out: Vec<&str> = Vec::new();
    // 앞 줄에서 열린 heredoc: (끝 표시, 탭을 떼고 견주는가)
    let mut pending: Vec<(String, bool)> = Vec::new();
    for line in cmd.split('\n') {
        if let Some((term, dash)) = pending.first() {
            let body = if *dash {
                line.trim_start_matches('\t')
            } else {
                line
            };
            if body == term {
                pending.remove(0);
            } else if let Some(dropped) = dropped.as_deref_mut() {
                dropped.push(line.to_owned());
            }
            continue;
        }

        out.push(line);
        for m in HEREDOC.find_iter(line) {
            let term = (1..=3)
                .find_map(|g| m.text(line, g))
                .expect("one name group matches");
            let dash = line[m.start()..].starts_with("<<-");
            pending.push((term.to_owned(), dash));
        }
    }
    out.join("\n")
}

/// 구간마다 (머리, 글). 머리 낱말이 없는 구간(빈 구간, 접두만 있는 구간)은 뺀다(python `segments`).
pub fn segments(cmd: &str) -> Vec<Segment> {
    let stripped = strip_heredocs(cmd, None);
    SPLIT
        .split(&stripped)
        .into_iter()
        .filter_map(|seg| {
            let spaced = seg.replace('(', " ( ");
            let words: Vec<&str> = split_whitespace(&spaced).collect();
            let head = words.get(head_index(&words))?;
            Some(Segment {
                head: (*head).to_owned(),
                text: seg.to_owned(),
            })
        })
        .collect()
}

// 접두 낱말을 건너뛴 머리 자리. 낱말 수 이상이면 머리가 없다
fn head_index(words: &[&str]) -> usize {
    let mut i = 0;
    while i < words.len() {
        let w = words[i];
        if PREFIX_WORDS.contains(&w) || ASSIGN_WORD.fullmatch(w).is_some() {
            i += 1;
        } else if w == "timeout" {
            // timeout 의 옵션과 시간
            i += 1;
            while i < words.len()
                && (words[i].starts_with('-') || DURATION.fullmatch(words[i]).is_some())
            {
                i += if TIMEOUT_VALUE_OPTIONS.contains(&words[i]) {
                    2
                } else {
                    1
                };
            }
        } else if w == "mise" && words.get(i + 1) == Some(&"exec") {
            i += 2;
            if words.get(i) == Some(&"--") {
                i += 1;
            }
        } else {
            break;
        }
    }
    i
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 이 파일의 고정 정규식이 두 regex crate 엔진과 py::re 에서 모두 만들어진다.
    #[test]
    fn fixed_patterns_build() {
        for re in [&*HEREDOC, &*SPLIT, &*ASSIGN_WORD, &*DURATION] {
            re.check();
        }
    }

    fn heads(cmd: &str) -> Vec<String> {
        segments(cmd).into_iter().map(|s| s.head).collect()
    }

    /// `&&`, `|` 로 나눈 구간마다 변수 대입과 `nice` 를 건너뛴 명령 이름이 머리다.
    #[test]
    fn heads_skip_assignments_and_nice() {
        assert_eq!(
            heads("cd x && FOO=1 nice python3 a.py | tail"),
            ["cd", "python3", "tail"]
        );
    }

    /// `timeout`, `mise exec --` 같은 래퍼의 옵션과 값을 건너뛰고 그 뒤 명령이 머리다.
    #[test]
    fn heads_skip_wrapper_options() {
        assert_eq!(
            heads("timeout -s KILL 60 lune run p.luau; mise exec -- luau a"),
            ["lune", "luau"]
        );
    }

    /// 명령이 없는 래퍼 낱말(`env`, `timeout 5`)은 머리가 없고, 괄호와 `time` 은 건너뛴다.
    #[test]
    fn bare_wrappers_have_no_head() {
        assert_eq!(heads("env; ( time ls )"), ["ls"]);
        assert_eq!(heads("timeout 5"), Vec::<String>::new());
    }

    /// 히어독 본문은 지우고, 지운 본문을 따로 돌려준다.
    #[test]
    fn strips_heredoc_bodies() {
        let mut dropped = Vec::new();
        let cmd = "cat <<'EOF' > f\nbench\nEOF\npython3 - <<-X\n\tperf\n\tX\nls";
        assert_eq!(
            strip_heredocs(cmd, Some(&mut dropped)),
            "cat <<'EOF' > f\npython3 - <<-X\nls"
        );
        assert_eq!(dropped, ["bench", "\tperf"]);
    }

    /// 한 줄에 히어독이 둘이어도 두 본문을 모두 지우고 뒤 명령을 읽는다.
    #[test]
    fn two_heredocs_on_one_line_are_both_dropped() {
        assert_eq!(
            heads("python3 - <<\"E\" <<X\nbench\nE\nperf\nX\nls"),
            ["python3", "ls"]
        );
    }

    /// `<<(?!<)` 의 앞 보기를 뺀 HEREDOC 이 python 판 패턴(py::re)과 같은 일치를 낸다.
    #[test]
    fn heredoc_without_lookahead_is_the_same() {
        const PYTHON: &str =
            r#"<<(?!<)-?\s*(?:'([A-Za-z_]\w*)'|"([A-Za-z_]\w*)"|\\?([A-Za-z_]\w*))"#;
        let py = harness_hook::py::re::Regex::new(PYTHON).unwrap();
        let spans = |ms: Vec<harness_hook::py::re::Match>| -> Vec<Vec<Option<(usize, usize)>>> {
            ms.iter()
                .map(|m| (0..=3).map(|g| m.group(g)).collect())
                .collect()
        };

        for line in [
            "cat <<EOF",
            "cat <<-'EOF' x",
            "cat << \"E1\" <<\\E2",
            // Here-strings
            // python reads the word after the 2nd and 3rd `<` as a name
            "cat <<<word",
            "cat <<<<x <<- <<",
            "a<<b<<c",
            "<<\u{d55c} <<_x1",
        ] {
            assert_eq!(
                spans(HEREDOC.find_iter(line)),
                spans(py.find_iter(line)),
                "{line:?}"
            );
        }
    }
}
