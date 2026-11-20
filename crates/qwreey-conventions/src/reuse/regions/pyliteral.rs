//! python 정본 영역의 문자열 상수를 좁은 꼴에서만 읽는다(python `ast.parse` 뒤 `ast.walk` 의 str Constant).
//!
//! why not 온전한 python 파서: 정본 영역은 거의 늘 `NAME = "..."` 한 줄이나 괄호 안에 이어 붙인 리터럴이다.
//! 그 꼴만 읽고, 확실하지 않은 글(다른 식, f-string, bytes, `\N{...}`, 줄 잇기 `\`, 문법 오류일 수 있는 글)은
//! [`Halt::Unported`] 로 넘긴다. python 의 SyntaxError 글을 옮기지 않으므로 틀린 알림을 내지 않는 쪽을 골랐다.
//!
//! 받는 문장: `대상 = 묶음`, `대상: 이름 = 묶음`, `묶음`. 대상은 `a.b.c` 꼴, 묶음은 리터럴 하나 이상(옆에 붙은 것은
//! 하나로 합친다)이거나 그것을 괄호 하나로 감싼 것. 문장 하나가 상수 하나다.

use harness_hook::py::surrogate::placeholder;
use harness_hook::py::text::{is_space, strip};

use crate::halt::{Halt, Result};

const UNSURE: Halt = Halt::Unported("a python canon region outside the literal subset");

// python 의 예약어(이름 자리에 오면 SyntaxError)
const KEYWORDS: &[&str] = &[
    "False", "None", "True", "and", "as", "assert", "async", "await", "break", "class", "continue",
    "def", "del", "elif", "else", "except", "finally", "for", "from", "global", "if", "import",
    "in", "is", "lambda", "nonlocal", "not", "or", "pass", "raise", "return", "try", "while",
    "with", "yield",
];

#[derive(Clone, Debug, PartialEq, Eq)]
enum Token {
    Name(String),
    Op(char),
    Str(String),
}

/// 정본 영역 줄들의 str 상수 값들. 받는 꼴이 아니면 [`Halt::Unported`].
pub fn constants(lines: &[&str]) -> Result<Vec<String>> {
    // Dedent by the smallest indent, counted in characters as python slices
    let indent = lines
        .iter()
        .filter(|x| !strip(x).is_empty())
        .map(|x| x.chars().take_while(|&c| is_space(c)).count())
        .min()
        .unwrap_or(0);
    let src: Vec<String> = lines
        .iter()
        .map(|x| x.chars().skip(indent).collect())
        .collect();
    let src: Vec<char> = src.join("\n").chars().collect();

    let mut out = Vec::new();
    for stmt in statements(&src)? {
        out.push(statement_value(&stmt)?);
    }
    Ok(out)
}

// 논리 줄마다 낱말들. 괄호 안의 줄바꿈은 줄을 끊지 않는다
fn statements(src: &[char]) -> Result<Vec<Vec<Token>>> {
    let mut out = Vec::new();
    let mut cur: Vec<Token> = Vec::new();
    let mut depth = 0usize;
    let mut i = 0;
    let mut line_start = true;

    while i < src.len() {
        let c = src[i];

        // An indented statement line is python's IndentationError
        if line_start && depth == 0 {
            line_start = false;
            if c == ' ' || c == '\t' {
                let rest = src[i..].iter().take_while(|&&c| c != '\n');
                let blank = rest.clone().all(|&c| c == ' ' || c == '\t');
                let comment = rest.clone().find(|&&c| c != ' ' && c != '\t') == Some(&'#');
                if !blank && !comment {
                    return Err(UNSURE);
                }
            }
        }

        match c {
            // Line ends, spaces and comments
            '\n' => {
                if depth == 0 && !cur.is_empty() {
                    out.push(std::mem::take(&mut cur));
                }
                line_start = true;
                i += 1;
            }
            ' ' | '\t' => i += 1,
            '#' => {
                while i < src.len() && src[i] != '\n' {
                    i += 1;
                }
            }

            // Brackets and operators
            '(' => {
                depth += 1;
                cur.push(Token::Op(c));
                i += 1;
            }
            ')' => {
                depth = depth.checked_sub(1).ok_or(UNSURE)?;
                cur.push(Token::Op(c));
                i += 1;
            }
            '=' | '.' | ':' => {
                cur.push(Token::Op(c));
                i += 1;
            }

            // Literals and names
            '"' | '\'' => {
                let (value, next) = read_string(src, i, false)?;
                cur.push(Token::Str(value));
                i = next;
            }
            c if c.is_ascii_alphabetic() || c == '_' => {
                let (token, next) = name_or_prefixed(src, i)?;
                cur.push(token);
                i = next;
            }
            _ => return Err(UNSURE),
        }
    }

    if depth != 0 {
        return Err(UNSURE);
    }
    if !cur.is_empty() {
        out.push(cur);
    }
    Ok(out)
}

// 이름 하나, 또는 `r"..."`, `u"..."` 리터럴. 다른 머리(b, f, t)가 붙은 리터럴은 옮기지 않는다
fn name_or_prefixed(src: &[char], at: usize) -> Result<(Token, usize)> {
    let mut j = at;
    while j < src.len() && (src[j].is_ascii_alphanumeric() || src[j] == '_') {
        j += 1;
    }
    let word: String = src[at..j].iter().collect();
    if j < src.len() && !src[j].is_ascii() {
        return Err(UNSURE);
    }

    // A quote right after the word makes it a string prefix
    if j < src.len() && (src[j] == '"' || src[j] == '\'') {
        let raw = match word.to_ascii_lowercase().as_str() {
            "r" => true,
            "u" => false,
            _ => return Err(UNSURE),
        };
        let (value, next) = read_string(src, j, raw)?;
        return Ok((Token::Str(value), next));
    }
    if KEYWORDS.contains(&word.as_str()) {
        return Err(UNSURE);
    }
    Ok((Token::Name(word), j))
}

// `at` 의 따옴표부터 닫는 따옴표 다음까지: (값, 다음 자리)
fn read_string(src: &[char], at: usize, raw: bool) -> Result<(String, usize)> {
    let q = src[at];
    let triple = src.get(at + 1) == Some(&q) && src.get(at + 2) == Some(&q);
    let mut i = at + if triple { 3 } else { 1 };
    let mut value = String::new();

    loop {
        let Some(&c) = src.get(i) else {
            return Err(UNSURE);
        };

        // Closing quote
        if c == q && (!triple || (src.get(i + 1) == Some(&q) && src.get(i + 2) == Some(&q))) {
            return Ok((value, i + if triple { 3 } else { 1 }));
        }
        if c == '\n' && !triple {
            return Err(UNSURE);
        }

        // Raw text keeps the backslash and protects the next character
        if c == '\\' && raw {
            let next = *src.get(i + 1).ok_or(UNSURE)?;
            value.push('\\');
            value.push(next);
            i += 2;
            continue;
        }
        if c != '\\' {
            value.push(c);
            i += 1;
            continue;
        }

        let (piece, next) = escape(src, i)?;
        value.push_str(&piece);
        i = next;
    }
}

// `src[at]` 의 `\` 에서 시작하는 escape 하나: (값, 다음 자리)
fn escape(src: &[char], at: usize) -> Result<(String, usize)> {
    let e = *src.get(at + 1).ok_or(UNSURE)?;
    // One-character escapes
    let simple = match e {
        '\n' => Some(""),
        '\\' => Some("\\"),
        '\'' => Some("'"),
        '"' => Some("\""),
        'a' => Some("\u{7}"),
        'b' => Some("\u{8}"),
        'f' => Some("\u{c}"),
        'n' => Some("\n"),
        'r' => Some("\r"),
        't' => Some("\t"),
        'v' => Some("\u{b}"),
        _ => None,
    };
    if let Some(s) = simple {
        return Ok((s.to_owned(), at + 2));
    }

    // Octal, hex and unicode escapes
    let digits = |from: usize, max: usize, radix: u32| -> String {
        src[from.min(src.len())..]
            .iter()
            .take(max)
            .take_while(|c| c.is_digit(radix))
            .collect()
    };
    let (code, next) = match e {
        '0'..='7' => {
            let d = digits(at + 1, 3, 8);
            (
                u32::from_str_radix(&d, 8).map_err(|_| UNSURE)?,
                at + 1 + d.len(),
            )
        }
        'x' | 'u' | 'U' => {
            let width = match e {
                'x' => 2,
                'u' => 4,
                _ => 8,
            };
            let d = digits(at + 2, width, 16);
            if d.len() != width {
                return Err(UNSURE);
            }
            (
                u32::from_str_radix(&d, 16).map_err(|_| UNSURE)?,
                at + 2 + width,
            )
        }
        'N' => return Err(UNSURE),
        // python 이 경고만 내고 그대로 두는 escape
        _ => return Ok((format!("\\{e}"), at + 2)),
    };
    let c = char::from_u32(code)
        .or_else(|| placeholder(code))
        .ok_or(UNSURE)?;
    Ok((c.to_string(), next))
}

// 문장 하나를 상수 하나로: `대상 =`, `대상: 이름 =` 를 건너뛴 뒤 리터럴 묶음
fn statement_value(stmt: &[Token]) -> Result<String> {
    let mut rest = stmt;

    // Assignment target, optionally annotated with a name
    if let Some(eq) = stmt.iter().position(|t| *t == Token::Op('=')) {
        let (target, value) = (&stmt[..eq], &stmt[eq + 1..]);
        let (name, annotation) = match target.iter().position(|t| *t == Token::Op(':')) {
            Some(colon) => (&target[..colon], Some(&target[colon + 1..])),
            None => (target, None),
        };
        if !dotted(name) || annotation.is_some_and(|a| !dotted(a)) {
            return Err(UNSURE);
        }
        rest = value;
    }

    // One group of adjacent literals, bare or in one pair of parentheses
    if let [Token::Op('('), inner @ .., Token::Op(')')] = rest {
        rest = inner;
    }
    if rest.is_empty() {
        return Err(UNSURE);
    }
    let mut value = String::new();
    for t in rest {
        let Token::Str(s) = t else { return Err(UNSURE) };
        value.push_str(s);
    }
    Ok(value)
}

// `a`, `a.b.c`
fn dotted(tokens: &[Token]) -> bool {
    !tokens.is_empty()
        && tokens.len() % 2 == 1
        && tokens.iter().enumerate().all(|(k, t)| match t {
            Token::Name(_) => k % 2 == 0,
            Token::Op('.') => k % 2 == 1,
            _ => false,
        })
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 대입, 괄호 안 이어 붙이기, escape 를 python ast 처럼 읽는다.
    #[test]
    fn reads_the_literal_subset() {
        // Implicit concatenation inside parentheses is one constant
        assert_eq!(
            constants(&[
                "    OMIT = (",
                "        \"a\\tb\"  # note",
                "        'c'",
                "    )"
            ])
            .unwrap(),
            ["a\tbc"]
        );

        // Raw, unicode-prefixed and triple-quoted strings
        assert_eq!(constants(&[r#"X = r"\d\"""#]).unwrap(), [r#"\d\""#]);
        assert_eq!(constants(&["X: str = u'''a", "b'''"]).unwrap(), ["a\nb"]);
        assert_eq!(constants(&["A = 'x'", "B = 'y'"]).unwrap().len(), 2);

        // Escapes python leaves alone keep the backslash
        assert_eq!(
            constants(&[r#"X = "\q\101\u00e9""#]).unwrap(),
            ["\\qA\u{e9}"]
        );
    }

    /// 받는 꼴 밖의 글은 옮기지 않는다(python 이 상수를 더 세거나 SyntaxError 를 낼 수 있다).
    #[test]
    fn leaves_other_code_unported() {
        for code in [
            "X = f\"{a}\"",
            "X = b'x'",
            "X = 1",
            "  X = 'a'\nY = 'b'",
            "X = 'a' + 'b'",
            "X = 'a",
            "class = 'a'",
            "X = '\\N{BULLET}'",
            "X = ('a'",
        ] {
            let lines: Vec<&str> = code.split('\n').collect();
            assert_eq!(constants(&lines), Err(UNSURE), "{code}");
        }
    }
}
