//! 리뷰어 가드가 Bash 명령 글에서 찾는 것: heredoc, 따옴표 글, 리다이렉션 대상, 명령 조각, 제자리 편집 옵션.
//!
//! python 판의 정규식(아래 `PY_*`)과 같은 자리에서 맞는다. regex crate 에 없는 앞 보기(`(?<!...)`)와 괄호 참조(`\1`)는
//! 몇 줄의 코드로 옮겼고, python 의 `\s`(U+001C..U+001F 포함)는 문자 집합으로 적었다. 그래서 글자에 따라 엔진을 바꾸지 않는다.
//! 시험이 `harness_hook::py::re` 로 돌린 python 판과 만든 입력 위에서 대조한다.

use std::sync::LazyLock;

use harness_hook::py::text::is_space;
use regex::Regex;

/// python `REDIR`(가드의 리다이렉션). 앞 보기는 [`redirect_targets`] 가 맡는다.
#[cfg(test)]
pub const PY_REDIR: &str = r"(?<![0-9&<])(?:[0-9]?)(>>?|&>>?)\s*([^\s;&|<>]+)";
/// python `HEREDOC`(re.S). 괄호 참조와 끝 보기는 [`heredoc_spans`] 가 맡는다.
#[cfg(test)]
pub const PY_HEREDOC: &str =
    "<<-?\\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\\1[^\\n]*\\n(.*?)\\n\\s*\\2\\s*(?=\\n|$)";

fn regex(pattern: &str) -> Regex {
    Regex::new(pattern).expect("built-in pattern")
}

// python \s 는 Unicode 공백에 U+001C..U+001F 를 더한다
static REDIR: LazyLock<Regex> =
    LazyLock::new(|| regex(r"([0-9]?)(>>?|&>>?)[\s\x1C-\x1F]*([^\s\x1C-\x1F;&|<>]+)"));
static INPLACE: LazyLock<Regex> =
    LazyLock::new(|| regex(r"(?:^|[\s\x1C-\x1F])-[a-zA-Z]*i(?:[\s\x1C-\x1F]|$|[.=])|--in-place"));
static SEGMENT_SPLIT: LazyLock<Regex> = LazyLock::new(|| regex(r"\|\||&&|[;|\n]"));
static QUOTED: LazyLock<Regex> = LazyLock::new(|| regex(r#"'[^']*'|"(?:[^"\\]|\\.)*""#));

/// python `INPLACE.search(text)`: `-i`, `-pi.bak`, `--in-place` 꼴이 있나.
///
/// python `$` 의 끝 줄바꿈 앞 자리는 `\s` 갈래가 이미 맡는다.
pub fn has_inplace(text: &str) -> bool {
    INPLACE.is_match(text)
}

/// python `re.split(r"\|\||&&|[;|\n]", cmd)`.
pub fn segments(cmd: &str) -> Vec<&str> {
    SEGMENT_SPLIT.split(cmd).collect()
}

/// python `QUOTED.sub("''", cmd)`.
pub fn blank_quotes(cmd: &str) -> String {
    QUOTED.replace_all(cmd, "''").into_owned()
}

/// python `REDIR.finditer(cmd)` 의 대상(괄호 2). 앞 글자가 숫자, `&`, `<` 인 자리에서는 시작하지 않는다.
pub fn redirect_targets(cmd: &str) -> Vec<&str> {
    let mut out = Vec::new();
    let mut pos = 0;
    while let Some(caps) = REDIR.captures_at(cmd, pos) {
        let whole = caps.get(0).expect("group 0");
        let before = cmd[..whole.start()].chars().next_back();
        if before.is_some_and(|c| c.is_ascii_digit() || c == '&' || c == '<') {
            // python tries the next position; this start is behind a digit, & or <
            pos = whole.start()
                + cmd[whole.start()..]
                    .chars()
                    .next()
                    .map_or(1, char::len_utf8);
            continue;
        }
        out.push(caps.get(3).expect("target group").as_str());
        pos = whole.end();
    }
    out
}

/// python `HEREDOC.finditer(cmd)` 의 일치 범위(바이트).
///
/// 패턴: `<<`, `-`, 공백, 따옴표(있으면 이름 뒤에 같은 따옴표), 이름, 그 줄 끝까지, 본문(가장 짧게), 줄바꿈과 공백 뒤의 같은
/// 이름, 그 뒤 공백 가운데 줄바꿈 앞이나 글 끝. 따옴표 없는 이름은 python 처럼 긴 것부터 짧은 것까지 해 본다.
pub fn heredoc_spans(cmd: &str) -> Vec<(usize, usize)> {
    let mut out = Vec::new();
    let mut pos = 0;
    while let Some(off) = cmd[pos..].find("<<") {
        let start = pos + off;
        match heredoc_at(cmd, start) {
            Some(end) => {
                out.push((start, end));
                pos = end;
            }
            None => pos = start + 1,
        }
    }
    out
}

fn skip_space(text: &str, from: usize) -> usize {
    text[from..]
        .char_indices()
        .find(|&(_, c)| !is_space(c))
        .map_or(text.len(), |(i, _)| from + i)
}

fn ident_len(text: &str, from: usize) -> usize {
    let bytes = text.as_bytes();
    let mut n = 0;
    while let Some(&b) = bytes.get(from + n) {
        let ok = b == b'_' || b.is_ascii_alphabetic() || (n > 0 && b.is_ascii_digit());
        if !ok {
            break;
        }
        n += 1;
    }
    n
}

// `start` 의 `<<` 에서 맞으면 일치의 끝
fn heredoc_at(cmd: &str, start: usize) -> Option<usize> {
    // Opener: <<, optional -, spaces
    let mut p = start + 2;
    if cmd[p..].starts_with('-') {
        p += 1;
    }
    p = skip_space(cmd, p);

    // Quoted name: only the full name followed by the same quote
    if let Some(q) = cmd[p..].chars().next().filter(|c| *c == '\'' || *c == '"') {
        let name_at = p + 1;
        let len = ident_len(cmd, name_at);
        if len == 0 || !cmd[name_at + len..].starts_with(q) {
            return None;
        }
        return terminate(cmd, &cmd[name_at..name_at + len], name_at + len + 1);
    }

    // Bare name: longest first, like python's backtracking
    let len = ident_len(cmd, p);
    (1..=len)
        .rev()
        .find_map(|n| terminate(cmd, &cmd[p..p + n], p + n))
}

// 이름 뒤 `after` 부터: 그 줄 끝의 줄바꿈, 가장 짧은 본문, 줄바꿈과 공백 뒤 이름, 끝 공백. 맞으면 일치의 끝
fn terminate(cmd: &str, name: &str, after: usize) -> Option<usize> {
    let body = after + cmd[after..].find('\n')? + 1;

    // Lazy body: every \n from the body start is a candidate end
    let mut from = body;
    while let Some(off) = cmd[from..].find('\n') {
        let nl = from + off;
        let name_at = skip_space(cmd, nl + 1);
        if cmd[name_at..].starts_with(name) {
            let tail = name_at + name.len();
            let space_end = skip_space(cmd, tail);
            if space_end == cmd.len() {
                return Some(cmd.len());
            }
            // \s* gives back to the last newline in the trailing spaces
            if let Some(last_nl) = cmd[tail..space_end].rfind('\n') {
                return Some(tail + last_nl);
            }
        }
        from = nl + 1;
    }
    None
}

/// python `HEREDOC.sub(lambda m: m.group(0).split("\n", 1)[0], cmd)`: heredoc 을 첫 줄만 남긴다.
pub fn strip_heredocs(cmd: &str) -> String {
    let mut out = String::with_capacity(cmd.len());
    let mut last = 0;
    for (start, end) in heredoc_spans(cmd) {
        out.push_str(&cmd[last..start]);
        let whole = &cmd[start..end];
        out.push_str(whole.split('\n').next().unwrap_or(""));
        last = end;
    }
    out.push_str(&cmd[last..]);
    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use harness_hook::py::re::{Flags, Regex as PyRegex};

    /// 만든 명령 글 묶음: heredoc, 리다이렉션, 따옴표, 공백 글자가 섞인다(결정적 의사 난수).
    fn corpus() -> Vec<String> {
        let parts = [
            "cat ",
            "<<",
            "<<-",
            "<<<",
            " ",
            "\t",
            "\n",
            "\x1c",
            "'",
            "\"",
            "EOF",
            "EOF2",
            "E",
            "x",
            "_a",
            "1",
            "2",
            ">",
            ">>",
            "&>",
            "&>>",
            "<",
            "&",
            "|",
            ";",
            "/tmp/a",
            "-",
            "\u{a0}",
            "\u{d55c}",
            " EOF\n",
            "\nEOF",
            "\n EOF  \n",
            "EOF x",
        ];
        harness_hook::testkit::corpus(&parts, 4000)
    }

    /// heredoc 꼴로 짠 명령 글: 따옴표, 이름, 본문, 끝 줄의 공백과 꼬리를 섞는다.
    fn heredoc_corpus() -> Vec<String> {
        let pieces: [&[&str]; 8] = [
            &["cat ", "x", ""],
            &["<<", "<<-", "<< ", "<<\t", "<<-\n", "<<<"],
            &["", "'", "\"", "'x"],
            &["EOF", "E", "EOF2", "_a1", "EO"],
            &["", "'", "\"", " > out", " | grep x"],
            &["\n", "\na > b\n", "\nEOF", "\n EOF\n", "\nEOFx\n", ""],
            &[
                "\nEOF",
                "\n  EOF  ",
                "\nEOF\n",
                "\nEOF x",
                "\n\nEOF\n tail",
                "\nEOF2\n",
                "\nE\n",
            ],
            &["", "\n", "\necho > f", " \x1c\n"],
        ];

        // One piece from each slot, in slot order
        let mut next = harness_hook::testkit::xorshift(0x9e37_79b9_7f4a_7c15);
        (0..3000)
            .map(|_| {
                pieces
                    .iter()
                    .map(|p| p[(next() % p.len() as u64) as usize])
                    .collect()
            })
            .collect()
    }

    /// heredoc 범위가 python `HEREDOC`(py::re)의 finditer 와 같다.
    #[test]
    fn heredoc_matches_python() {
        let dotall = Flags {
            dotall: true,
            ..Flags::NONE
        };
        let py = PyRegex::with_flags(PY_HEREDOC, dotall).expect("python pattern");
        let mut matched = 0;
        for cmd in corpus().into_iter().chain(heredoc_corpus()) {
            let want: Vec<(usize, usize)> = py
                .find_iter(&cmd)
                .iter()
                .map(|m| (m.start(), m.end()))
                .collect();
            matched += usize::from(!want.is_empty());
            assert_eq!(heredoc_spans(&cmd), want, "{cmd:?}");
        }

        // The corpus must exercise the pattern, not only its misses
        assert!(matched > 100, "only {matched} inputs had a heredoc");
    }

    /// 리다이렉션 대상이 python `REDIR`(py::re, 앞 보기 포함)와 같다.
    #[test]
    fn redirects_match_python() {
        let py = PyRegex::new(PY_REDIR).expect("python pattern");
        let mut matched = 0;
        for cmd in corpus() {
            let want: Vec<&str> = py
                .find_iter(&cmd)
                .iter()
                .filter_map(|m| m.text(&cmd, 2))
                .collect();
            matched += usize::from(!want.is_empty());
            assert_eq!(redirect_targets(&cmd), want, "{cmd:?}");
        }

        // The corpus must exercise the pattern, not only its misses
        assert!(matched > 500, "only {matched} inputs had a redirect");
    }

    /// 제자리 편집 옵션과 조각 나누기의 몇 꼴.
    #[test]
    fn inplace_and_segments() {
        // In-place flags
        assert!(has_inplace("-i s/a/b/ f"));
        assert!(has_inplace("-pi.bak -e x"));
        assert!(has_inplace("x --in-place"));
        assert!(!has_inplace("-n -e p"));

        // Segments split on || && ; | and newlines
        assert_eq!(
            segments("a || b && c; d | e\nf"),
            ["a ", " b ", " c", " d ", " e", "f"]
        );
        assert_eq!(blank_quotes(r#"echo 'a > b' "c \" d" e"#), "echo '' '' e");
    }
}
