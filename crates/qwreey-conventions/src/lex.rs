//! 간이 렉서(python `hooks/conv_lex.py`): 확장자별 계열, 줄마다 주석 조각과 코드 유무.
//!
//! 열 위치는 줄 안의 바이트 위치다(python 은 글자 위치). 위치끼리만 견주고 밖에 내보내지 않으므로 판정은 같다.

use std::sync::LazyLock;

use harness_hook::py::re::Regex;

/// 렉서 계열(python `FAMILY` 의 값).
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Family {
    Lua,
    C,
    Rust,
    Astro,
    Py,
    Html,
}

/// 확장자(소문자, 점 포함) -> 렉서 계열(python `FAMILY.get(ext)`).
pub fn family(ext: &str) -> Option<Family> {
    Some(match ext {
        ".luau" | ".lua" => Family::Lua,
        ".ts" | ".tsx" | ".js" | ".jsx" | ".mjs" | ".go" | ".kt" => Family::C,
        ".rs" => Family::Rust,
        ".astro" => Family::Astro,
        ".py" | ".sh" => Family::Py,
        ".html" | ".htm" => Family::Html,
        _ => return None,
    })
}

/// 한 줄의 렉싱 결과(python 의 줄 dict).
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct Row {
    /// 주석 조각들(여닫는 표식을 뺀 본문, python `"c"`).
    pub c: Vec<String>,
    /// 조각의 (시작, 끝) 바이트 위치(python `"s"`).
    pub s: Vec<(usize, usize)>,
    /// 코드나 문자열이 있는가(python `"code"`).
    pub code: bool,
    /// `keep_code` 일 때만: 주석을 지우고 문자열을 `""` 하나로 줄인 코드 글(python `"k"`).
    pub k: String,
    /// `keep_code` 일 때만: 여러 줄 주석이나 문자열 안에서 시작하는 줄인가(python `"in"`).
    pub inside: bool,
}

// 열린 여러 줄 주석이나 문자열과 그 닫는 표식
#[derive(Clone, Debug)]
enum Open {
    Block(String),
    Str(String),
}

// 이 자리에서 열린 것(python open_comment_or_string 의 kind)
enum Opened {
    Line(usize),
    Block(String, usize),
    Str(String, usize),
    StrLine(char, usize),
}

/// python `lex(text, fam, keep_code)`: 줄마다 [`Row`].
pub fn lex(text: &str, fam: Family, keep_code: bool) -> Vec<Row> {
    let mut out = Vec::new();
    let mut state: Option<Open> = None;
    for s in text.split('\n') {
        let mut row = Row {
            inside: keep_code && state.is_some(),
            ..Row::default()
        };
        let mut code = String::new();
        let n = s.len();
        let mut pos = 0;

        while pos < n {
            // Inside a block comment
            if let Some(Open::Block(close)) = &state {
                match s[pos..].find(close.as_str()) {
                    None => {
                        row.c.push(s[pos..].to_owned());
                        row.s.push((pos, n));
                        pos = n;
                    }
                    Some(rel) => {
                        let j = pos + rel;
                        row.c.push(s[pos..j].to_owned());
                        row.s.push((pos, j));
                        pos = j + close.len();
                        state = None;
                    }
                }
                continue;
            }

            // Inside a multi-line string
            if let Some(Open::Str(close)) = &state {
                row.code = true;
                match find_close(s, pos, close) {
                    None => pos = n,
                    Some(j) => {
                        pos = j + close.len();
                        state = None;
                    }
                }
                continue;
            }

            // Skip plain code to the next opener
            let k = s[pos..]
                .find(|c: char| is_opener(fam, c))
                .map_or(n, |rel| pos + rel);
            if k > pos {
                let span = &s[pos..k];
                row.code = row.code || !span.trim_matches([' ', '\t', '\r']).is_empty();
                if keep_code {
                    code.extend(
                        span.chars()
                            .map(|c| if c == '\t' || c == '\r' { ' ' } else { c }),
                    );
                }
                pos = k;
                continue;
            }

            // An opener that opens nothing is plain code
            let Some(opened) = open_comment_or_string(s, pos, fam) else {
                row.code = true;
                if keep_code {
                    code.push_str(&s[pos..pos + 1]);
                }
                pos += 1;
                continue;
            };

            // What it opened decides the rest of the line
            if keep_code && matches!(opened, Opened::Str(..) | Opened::StrLine(..)) {
                code.push_str("\"\"");
            }
            match opened {
                Opened::Line(b) => {
                    row.c.push(s[pos + b..].to_owned());
                    row.s.push((pos + b, n));
                    pos = n;
                }
                Opened::Block(close, b) => {
                    state = Some(Open::Block(close));
                    pos += b;
                }
                Opened::Str(close, b) => {
                    row.code = true;
                    state = Some(Open::Str(close));
                    pos += b;
                }
                Opened::StrLine(quote, b) => {
                    row.code = true;
                    pos = skip_string_line(s, pos + b, quote);
                }
            }
        }

        if keep_code {
            row.k = code;
        }
        out.push(row);
    }
    out
}

// 계열마다 주석이나 문자열이 열릴 수 있는 글자(python OPENERS). 그 사이의 코드는 한 번에 건너뛴다
fn is_opener(fam: Family, c: char) -> bool {
    match fam {
        Family::Lua => matches!(c, '-' | '[' | '"' | '\'' | '`'),
        Family::Py => matches!(c, '#' | '"' | '\''),
        Family::Html => c == '<',
        Family::Astro => matches!(c, '<' | '/' | '"' | '\'' | '`'),
        Family::C | Family::Rust => matches!(c, '/' | '"' | '\'' | '`'),
    }
}

// 한 줄 문자열의 끝 다음 자리: 같은 줄에서 닫히고, 안 닫히면 줄 끝. `\` 는 다음 글자 하나를 건너뛴다
fn skip_string_line(s: &str, from: usize, quote: char) -> usize {
    let n = s.len();
    let mut j = from;
    while j < n {
        let Some(c) = s[j..].chars().next() else {
            break;
        };
        if c == quote {
            break;
        }
        j += c.len_utf8();
        if c == '\\' {
            j += s[j..].chars().next().map_or(1, char::len_utf8);
        }
    }
    (j + 1).min(n)
}

/// python `find_close(s, pos, close)`: `` ` ``, `"""`, `'''` 는 바로 앞이 `\` 이면 닫는 표식이 아니다.
fn find_close(s: &str, pos: usize, close: &str) -> Option<usize> {
    let escapable = matches!(close, "`" | "\"\"\"" | "'''");
    let mut j = pos;
    loop {
        let k = j + s.get(j..)?.find(close)?;
        if escapable && k > 0 && s.as_bytes()[k - 1] == b'\\' {
            j = k + 1;
            continue;
        }
        return Some(k);
    }
}

// `[` 뒤의 `=` 들과 `[`(Lua 긴 괄호): (= 의 수, 여는 표식이 끝나는 자리)
fn long_bracket(s: &str, at: usize) -> Option<(usize, usize)> {
    let rest = s.get(at..)?.strip_prefix('[')?;
    let eq = rest.bytes().take_while(|&b| b == b'=').count();
    rest[eq..].starts_with('[').then_some((eq, at + 1 + eq + 1))
}

fn closer(eq: usize) -> String {
    format!("]{}]", "=".repeat(eq))
}

// python RUST_CHAR `'(?:\\.[^']{0,8}|[^'\\])'` 가 pos 에서 맞는가
fn rust_char_literal(s: &str, pos: usize) -> bool {
    let mut it = s[pos + 1..].chars();
    match it.next() {
        Some('\\') => {
            // `\` 다음 아무 글자 하나, `'` 아닌 글자 0~8개(가장 길게), 그리고 `'`
            if it.next().is_none() {
                return false;
            }
            let mut rest = it.clone();
            let mut taken = 0;
            while taken < 8 && rest.clone().next().is_some_and(|c| c != '\'') {
                rest.next();
                taken += 1;
            }
            rest.next() == Some('\'')
        }
        Some('\'') | None => false,
        Some(_) => it.next() == Some('\''),
    }
}

// python open_comment_or_string: pos 에서 주석이나 문자열이 열리면 그 종류
fn open_comment_or_string(s: &str, pos: usize, fam: Family) -> Option<Opened> {
    let rest = &s[pos..];
    let ch = rest.chars().next()?;
    match fam {
        Family::Lua => {
            if rest.starts_with("--") {
                if let Some((eq, end)) = long_bracket(s, pos + 2) {
                    return Some(Opened::Block(closer(eq), end - pos));
                }
                return Some(Opened::Line(2));
            }
            if let Some((eq, end)) = long_bracket(s, pos) {
                return Some(Opened::Str(closer(eq), end - pos));
            }
            match ch {
                '"' | '\'' => Some(Opened::StrLine(ch, 1)),
                '`' => Some(Opened::Str("`".to_owned(), 1)),
                _ => None,
            }
        }
        Family::Py => {
            if ch == '#' {
                return Some(Opened::Line(1));
            }
            for q in ["\"\"\"", "'''"] {
                if rest.starts_with(q) {
                    return Some(Opened::Str(q.to_owned(), 3));
                }
            }
            matches!(ch, '"' | '\'').then_some(Opened::StrLine(ch, 1))
        }
        // 마크업의 아포스트로피가 문자열 상태를 오염시키지 않게 문자열은 보지 않는다
        Family::Html => rest
            .starts_with("<!--")
            .then(|| Opened::Block("-->".to_owned(), 4)),
        Family::C | Family::Rust | Family::Astro => open_c_like(s, pos, fam, ch),
    }
}

fn open_c_like(s: &str, pos: usize, fam: Family, ch: char) -> Option<Opened> {
    let rest = &s[pos..];
    if fam == Family::Astro && rest.starts_with("<!--") {
        return Some(Opened::Block("-->".to_owned(), 4));
    }
    if rest.starts_with("//") {
        return Some(Opened::Line(2));
    }
    if rest.starts_with("/*") {
        return Some(Opened::Block("*/".to_owned(), 2));
    }
    match ch {
        '"' => Some(Opened::StrLine('"', 1)),
        // Rust 는 수명 'a 와 문자 리터럴 'x' 를 가른다. Astro 는 짝이 같은 줄에 있을 때만(마크업 속 "don't")
        '\'' if fam == Family::Rust => {
            rust_char_literal(s, pos).then_some(Opened::StrLine('\'', 1))
        }
        '\'' if fam == Family::Astro => s[pos + 1..]
            .contains('\'')
            .then_some(Opened::StrLine('\'', 1)),
        '\'' => Some(Opened::StrLine('\'', 1)),
        '`' if fam != Family::Rust => Some(Opened::Str("`".to_owned(), 1)),
        _ => None,
    }
}

static BODY_HEAD: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"^[\s\-/#*!]+").expect("constant pattern"));

/// python `comment_body(seg)`: 주석 조각에서 표식 장식을 걷어 낸 본문.
pub fn comment_body(seg: &str) -> &str {
    let from = BODY_HEAD.match_start(seg).map_or(0, |m| m.end());
    seg[from..].trim_end_matches([' ', '\t', '*', '/', '-'])
}

#[cfg(test)]
mod tests {
    use super::*;

    /// Lua 의 문자열 속 `--` 는 주석이 아니고, 긴 괄호 주석은 다음 줄로 이어진다.
    #[test]
    fn lua_comments_strings_and_blocks() {
        let rows = lex(
            "local s = \"-- no\" -- yes\n--[==[ a\nb ]==] x\n",
            Family::Lua,
            true,
        );

        // Only the dashes outside the string open a comment
        assert_eq!(rows[0].c, vec![" yes"]);
        assert!(rows[0].code);
        assert_eq!(
            rows[0].k, "local s = \"\" ",
            "keep_code shrinks a string to an empty literal"
        );

        // A long-bracket comment carries over to the next line
        assert_eq!(rows[1].c, vec![" a"]);
        assert!(!rows[1].code);
        assert!(rows[2].inside);
        assert_eq!(rows[2].c, vec!["b "]);
        assert!(rows[2].code);
    }

    /// Rust 의 수명 `'a` 는 문자 리터럴로 열지 않고 `'x'`, `'\''` 는 연다.
    #[test]
    fn rust_lifetimes_and_chars() {
        // Char literals open a string, a lifetime does not
        assert!(rust_char_literal("'a'", 0));
        assert!(rust_char_literal("'\\''", 0));
        assert!(rust_char_literal("'\\u{1F600}'", 0));
        assert!(!rust_char_literal("'a: &str", 0));

        // The `/` inside a char literal does not start a comment
        let rows = lex(
            "fn f<'a>(x: &'a str) -> char { '/' } // c",
            Family::Rust,
            false,
        );
        assert_eq!(rows[0].c, vec![" c"]);
    }

    /// 주석 본문에서 앞의 표식과 뒤의 닫는 표식을 걷어 낸다.
    #[test]
    fn body_strips_markers() {
        assert_eq!(comment_body("-- hello --"), "hello");
        assert_eq!(comment_body("/// doc */"), "doc");
    }
}
