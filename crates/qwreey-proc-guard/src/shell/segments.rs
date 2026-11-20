//! Bash 명령을 구간으로 나눈다(`hooks/shell_segments.py`). heavy-proc-guard 와 self-match-guard 가 같이 쓴다.
//!
//! 셸 문법을 다 읽지는 않는다: heredoc 본문을 버리고 `&&`, `||`, `;`, `|`, 줄바꿈으로 나눈 뒤 각 구간의 머리 프로그램을 찾는다.
//! 따옴표 안의 구분자도 나누므로 훅은 오탐 쪽으로 기운다. 정규식은 python 판의 글 그대로다(py::re 가 같은 뜻으로 읽는다).

use std::sync::LazyLock;

use harness_hook::py::re::Regex;
use harness_hook::py::text::split_whitespace;

const PREFIX_WORDS: &[&str] = &["(", "{", "time", "nice", "env", "command", "exec", "nohup"];
const TIMEOUT_VALUE_OPTIONS: &[&str] = &["-s", "-k", "--signal", "--kill-after"];

fn regex(pattern: &str) -> Regex {
    Regex::new(pattern).expect("built-in pattern compiles")
}

static HEREDOC: LazyLock<Regex> = LazyLock::new(|| {
    regex(r#"<<(?!<)-?\s*(?:'([A-Za-z_]\w*)'|"([A-Za-z_]\w*)"|\\?([A-Za-z_]\w*))"#)
});
static SPLIT: LazyLock<Regex> = LazyLock::new(|| regex(r"&&|\|\||[;|\n]"));
static ASSIGN_WORD: LazyLock<Regex> = LazyLock::new(|| regex(r"[A-Za-z_][A-Za-z0-9_]*=\S*"));
static DURATION: LazyLock<Regex> = LazyLock::new(|| regex(r"[\d.]+[smhd]?"));

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

    fn heads(cmd: &str) -> Vec<String> {
        segments(cmd).into_iter().map(|s| s.head).collect()
    }

    #[test]
    fn splits_and_finds_heads() {
        assert_eq!(
            heads("cd x && FOO=1 nice python3 a.py | tail"),
            ["cd", "python3", "tail"]
        );
        assert_eq!(
            heads("timeout -s KILL 60 lune run p.luau; mise exec -- luau a"),
            ["lune", "luau"]
        );
        assert_eq!(heads("env; ( time ls )"), ["ls"]);
        assert_eq!(heads("timeout 5"), Vec::<String>::new());
    }

    #[test]
    fn drops_heredoc_bodies() {
        let mut dropped = Vec::new();
        let cmd = "cat <<'EOF' > f\nbench\nEOF\npython3 - <<-X\n\tperf\n\tX\nls";
        assert_eq!(
            strip_heredocs(cmd, Some(&mut dropped)),
            "cat <<'EOF' > f\npython3 - <<-X\nls"
        );
        assert_eq!(dropped, ["bench", "\tperf"]);
        assert_eq!(
            heads("python3 - <<\"E\" <<X\nbench\nE\nperf\nX\nls"),
            ["python3", "ls"]
        );
    }
}
