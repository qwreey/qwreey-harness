//! Bash 명령 글에서 쓰는 대상 경로 후보를 찾는다(python `bash_paths` 의 정규식들). 거친 판정이다.
//!
//! python 판의 패턴(아래 `PY_*`)과 같은 자리에서 맞는다. regex crate 에 없는 괄호 참조(`\1`)와 뒤보기(`(?<!...)`)는
//! 코드로 옮겼고, 나머지는 [`rx::Regex`] 로 돈다. 시험이 `harness_hook::py::re` 로 돌린 python 판과 만든 입력 위에서 대조한다.

use std::sync::LazyLock;

use harness_hook::py::text::is_space;
use harness_hook::py::unicode::{is_decimal, is_word};
use harness_hook::rx::Regex;

/// python `HEREDOC`(re.S). 괄호 참조와 끝 보기는 [`heredoc_end`] 가 맡는다.
#[cfg(test)]
pub const PY_HEREDOC: &str = r#"<<-?\s*(['"]?)(\w+)\1[^\n]*\n.*?\n[ \t]*\2[ \t]*(?=\n|$)"#;
/// python `REDIRECT`. 뒤보기는 [`redirect_targets`] 가 맡는다.
#[cfg(test)]
pub const PY_REDIRECT: &str = r#"(?<![\d&>])>>?[ \t]*["']?([^\s"'|;&<>()]+)"#;
const TEE: &str = r"\btee\b((?:[ \t]+[^\s|;&<>]+)+)";
const SED_I: &str = r"\bsed\b[^\n|;&]*?[ \t]-[a-zA-Z]*i\S*([^\n|;&]*)";
const QUOTED: &str = r#""[^"\n]*"|'[^'\n]*'"#;
const REDIRECT_BODY: &str = r#">>?[ \t]*["']?([^\s"'|;&<>()]+)"#;

static TEE_RX: LazyLock<Regex> = LazyLock::new(|| Regex::new(TEE));
static SED_I_RX: LazyLock<Regex> = LazyLock::new(|| Regex::new(SED_I));
static QUOTED_RX: LazyLock<Regex> = LazyLock::new(|| Regex::new(QUOTED));
static REDIRECT_RX: LazyLock<Regex> = LazyLock::new(|| Regex::new(REDIRECT_BODY));

/// python `bash_paths` 의 앞 단계: 거르기 전의 후보 글(리다이렉션, tee 인자, `sed -i` 인자 순서).
pub fn candidates(cmd: &str) -> Vec<String> {
    let cmd = strip_heredocs(cmd);

    // A > inside a quoted string is not a redirect
    let blanked = QUOTED_RX.replace_all(&cmd, |_| "\"\"".to_owned());
    let mut found: Vec<String> = redirect_targets(&blanked)
        .into_iter()
        .map(str::to_owned)
        .collect();

    // Operands of tee and sed -i, options dropped
    for re in [&*TEE_RX, &*SED_I_RX] {
        for m in re.find_iter(&cmd) {
            let operands = m.text(&cmd, 1).unwrap_or("");
            found.extend(
                harness_hook::py::text::split_whitespace(operands)
                    .filter(|t| !t.starts_with('-'))
                    .map(str::to_owned),
            );
        }
    }
    found
}

/// python `HEREDOC.sub(lambda m: m.group(0).split("\n", 1)[0], cmd)`: heredoc 을 첫 줄만 남긴다.
pub fn strip_heredocs(cmd: &str) -> String {
    let mut out = String::with_capacity(cmd.len());
    let mut last = 0;
    let mut pos = 0;
    while let Some(off) = cmd[pos..].find("<<") {
        // python tries every start; only a << can begin a match
        let start = pos + off;
        let Some(end) = heredoc_end(cmd, start) else {
            pos = start + 1;
            continue;
        };

        // Keep the first line of the match
        out.push_str(&cmd[last..start]);
        out.push_str(cmd[start..end].split('\n').next().unwrap_or(""));
        last = end;
        pos = end;
    }

    out.push_str(&cmd[last..]);
    out
}

fn skip_space(text: &str, from: usize) -> usize {
    text[from..]
        .char_indices()
        .find(|&(_, c)| !is_space(c))
        .map_or(text.len(), |(i, _)| from + i)
}

fn skip_blanks(text: &str, from: usize) -> usize {
    from + text[from..].len() - text[from..].trim_start_matches([' ', '\t']).len()
}

// python \w+ 의 바이트 길이
fn word_len(text: &str, from: usize) -> usize {
    text[from..]
        .char_indices()
        .find(|&(_, c)| !is_word(u32::from(c)))
        .map_or(text.len() - from, |(i, _)| i)
}

// `start` 의 `<<` 에서 python HEREDOC 이 맞으면 일치의 끝
fn heredoc_end(cmd: &str, start: usize) -> Option<usize> {
    // Opener: <<, optional -, spaces
    let mut p = start + 2;
    if cmd[p..].starts_with('-') {
        p += 1;
    }
    p = skip_space(cmd, p);

    // Quoted name: only the whole word followed by the same quote
    if let Some(q) = cmd[p..].chars().next().filter(|c| *c == '\'' || *c == '"') {
        let name_at = p + 1;
        let len = word_len(cmd, name_at);
        if len == 0 || !cmd[name_at + len..].starts_with(q) {
            return None;
        }
        return terminator(cmd, &cmd[name_at..name_at + len], name_at + len + 1);
    }

    // Bare name: longest first, like python's backtracking
    let len = word_len(cmd, p);
    let ends = cmd[p..p + len]
        .char_indices()
        .map(|(i, c)| i + c.len_utf8());
    let lens: Vec<usize> = ends.collect();
    lens.into_iter()
        .rev()
        .find_map(|n| terminator(cmd, &cmd[p..p + n], p + n))
}

// 이름 뒤 `after` 부터: 그 줄 끝, 가장 짧은 본문, 줄바꿈과 공백 뒤 이름, 끝 공백, 그 뒤가 줄바꿈이나 글 끝. 맞으면 일치의 끝
fn terminator(cmd: &str, name: &str, after: usize) -> Option<usize> {
    let body = after + cmd[after..].find('\n')? + 1;

    // Lazy body: every \n from the body start is a candidate
    let mut from = body;
    while let Some(off) = cmd[from..].find('\n') {
        let name_at = skip_blanks(cmd, from + off + 1);
        if cmd[name_at..].starts_with(name) {
            let end = skip_blanks(cmd, name_at + name.len());
            if end == cmd.len() || cmd[end..].starts_with('\n') {
                return Some(end);
            }
        }
        from += off + 1;
    }
    None
}

/// python `REDIRECT.finditer(cmd)` 의 대상(괄호 1). 앞 글자가 숫자, `&`, `>` 인 자리에서는 시작하지 않는다.
pub fn redirect_targets(cmd: &str) -> Vec<&str> {
    let mut out = Vec::new();
    let mut pos = 0;
    while let Some(m) = REDIRECT_RX.search_from(cmd, pos) {
        let before = cmd[..m.start()].chars().next_back();
        if before.is_some_and(|c| c == '&' || c == '>' || is_decimal(u32::from(c))) {
            // python tries the next position; this start is behind a digit, & or >
            pos = m.start() + 1;
            continue;
        }
        out.push(m.text(cmd, 1).unwrap_or(""));
        pos = m.end();
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use harness_hook::py::re::{Flags, Regex as PyRegex};
    use harness_hook::testkit::{assert_agree, corpus};

    const PIECES: &[&str] = &[
        "cat ",
        "x",
        "tee ",
        " -a ",
        "sed",
        " -i ",
        " -ni.bak ",
        "-e",
        " s/a/b/ ",
        "f.py",
        " >",
        ">>",
        "2>",
        "&>",
        "<<",
        "<<-",
        "'EOF'",
        "\"EOF\"",
        "EOF",
        " EOF",
        "EO",
        "\n",
        "\t",
        " ",
        "|",
        ";",
        "&",
        "(",
        ")",
        "\"a > b\"",
        "'c'",
        "\u{e9}",
        "\u{663}",
        "\u{1c}",
        "\u{a0}",
        "out.rs",
        "/tmp/a",
        "\u{d55c}",
        "_",
    ];

    /// heredoc 꼴로 짠 명령 글: 여는 꼴, 따옴표와 이름, 본문, 끝 줄의 공백과 꼬리를 섞는다(결정적 의사 난수).
    fn heredoc_corpus() -> Vec<String> {
        let slots: [&[&str]; 8] = [
            &["cat ", "x", "", "a<"],
            &["<<", "<<-", "<< ", "<<\t", "<<-\n", "<<<", "<"],
            &[
                "EOF", "'EOF'", "\"EOF\"", "'EOF", "E\u{e9}", "_1", "", "\u{663}x",
            ],
            &["", " > a.py", "x", " ; y"],
            &["\n", "\n\n", ""],
            &["body > b.rs\n", "", "EO\n", "EOFX\n", "\u{d55c}\n"],
            &[
                "EOF",
                " EOF",
                "\tEOF \t",
                "E\u{e9}",
                "_1",
                "EO",
                "\u{663}x",
                "EOF\u{a0}",
            ],
            &["", "\n", "\nrest > c.go", " tail", "\n\n"],
        ];

        // One choice per slot
        let mut next = harness_hook::testkit::xorshift(0x9e37_79b9_7f4a_7c15);
        (0..20_000)
            .map(|_| {
                slots
                    .iter()
                    .map(|choices| choices[(next() % choices.len() as u64) as usize])
                    .collect()
            })
            .collect()
    }

    /// 고정 패턴 셋이 python re 와 같은 일치를 낸다(regex crate 와 py::re 대조).
    #[test]
    fn plain_patterns_agree_with_python() {
        assert_agree(
            &[
                ("TEE", &*TEE_RX),
                ("SED_I", &*SED_I_RX),
                ("QUOTED", &*QUOTED_RX),
            ],
            PIECES,
        );
    }

    /// heredoc 을 지운 글이 python `HEREDOC.sub` 와 같다.
    #[test]
    fn heredoc_strip_matches_python() {
        let dotall = Flags {
            dotall: true,
            ..Flags::NONE
        };
        let py = PyRegex::with_flags(PY_HEREDOC, dotall).expect("python pattern");
        let mut matched = 0;
        for cmd in corpus(PIECES, 5_000).into_iter().chain(heredoc_corpus()) {
            let want = py.replace_all(&cmd, |m| {
                let whole = m.text(&cmd, 0).unwrap_or("");
                whole.split('\n').next().unwrap_or("").to_owned()
            });
            matched += usize::from(want != cmd);
            assert_eq!(strip_heredocs(&cmd), want, "{cmd:?}");
        }

        // The corpus must exercise the pattern, not only its misses
        assert!(matched > 100, "only {matched} inputs had a heredoc");
    }

    /// 리다이렉션 대상이 python `REDIRECT`(py::re, 뒤보기 포함)와 같다.
    #[test]
    fn redirects_match_python() {
        let py = PyRegex::new(PY_REDIRECT).expect("python pattern");
        let mut matched = 0;
        for cmd in corpus(PIECES, 20_000) {
            let want: Vec<&str> = py
                .find_iter(&cmd)
                .iter()
                .filter_map(|m| m.text(&cmd, 1))
                .collect();
            matched += usize::from(!want.is_empty());
            assert_eq!(redirect_targets(&cmd), want, "{cmd:?}");
        }

        // The corpus must exercise the pattern, not only its misses
        assert!(matched > 500, "only {matched} inputs had a redirect");
    }

    /// 몇 가지 꼴: heredoc 본문 안의 `>` 는 보지 않고, 따옴표 안의 `>` 는 리다이렉션이 아니다.
    #[test]
    fn candidates_of_common_commands() {
        let heredoc = "cat > a.py <<'EOF'\nx > b.py\nEOF\necho \"1 > 2\" > c.rs";
        assert_eq!(candidates(heredoc), ["a.py", "c.rs"]);
        assert_eq!(
            candidates("ls | tee -a log.txt out.py"),
            ["log.txt", "out.py"]
        );
        assert_eq!(candidates("sed -i.bak 's/a/b/' x.go"), ["'s/a/b/'", "x.go"]);
        assert_eq!(candidates("echo 2>err.py"), Vec::<String>::new());
    }
}
