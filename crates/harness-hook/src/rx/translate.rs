//! python re 패턴 글을 regex crate 글로 옮긴다. 뜻이 같은 글은 그대로 두고, python 만의 글자 규칙(`\Z`, 글자 `{`, 클래스 안의
//! `[` `&&` `~~` `--`, `{,n}`)을 고쳐 쓰고, 갈림 검사에 쓸 것([`Uses`])을 적는다.

use super::Uses;
use crate::py::re::Flags;

// regex crate 에서 `\` 를 붙여야 글자가 되는 것
const META: &str = r"\.+*?()|[]{}^$#&-~";

/// 옮긴 패턴: regex crate 글, 갈림 검사에 쓸 것, 잡는 괄호 수.
pub(super) struct Translated {
    pub body: String,
    pub uses: Uses,
    pub groups: usize,
}

/// python 패턴 글을 regex crate 글로. 옮기지 않는 문법이면 그 이름.
///
/// `ascii` 면 Unicode 를 끈 엔진에 줄 글이다: python `\s` 를 ASCII 공백 표로 쓴다(그 엔진의 `\w \d \b` 와 IGNORECASE 는
/// ASCII 글에서 python 과 같다).
pub(super) fn translate(pattern: &str, flags: Flags, ascii: bool) -> Result<Translated, String> {
    let chars: Vec<char> = pattern.chars().collect();
    let mut out = String::with_capacity(pattern.len() + 8);
    let mut uses = Uses {
        icase: flags.ignore_case,
        ..Uses::default()
    };
    let mut multiline = flags.multiline;
    let mut groups = 0;
    let mut i = 0;

    while i < chars.len() {
        let c = chars[i];
        match c {
            '\\' => i = escape(&chars, i, false, ascii, &mut out, &mut uses)?,
            '[' => i = class(&chars, i, ascii, &mut out, &mut uses)?,
            '(' => i = group(&chars, i, &mut out, &mut uses, &mut multiline, &mut groups)?,
            '$' => {
                uses.dollar |= !multiline;
                out.push('$');
                i += 1;
            }
            '{' => i = brace(&chars, i, &mut out)?,
            '}' => {
                out.push_str(r"\}");
                i += 1;
            }
            '*' | '+' | '?' => {
                out.push(c);
                i += 1;
                if chars.get(i) == Some(&'+') {
                    return Err("possessive quantifier".into());
                }
                if chars.get(i) == Some(&'?') {
                    out.push('?');
                    i += 1;
                }
            }
            _ => {
                push_literal(&mut out, c, ascii);
                i += 1;
            }
        }
    }

    // The case guard covers ASCII letters only
    if uses.icase
        && let Some(c) = chars.iter().find(|c| !c.is_ascii() && has_case(**c))
    {
        return Err(format!("IGNORECASE with the cased letter {c:?}"));
    }
    Ok(Translated {
        body: out,
        uses,
        groups,
    })
}

// Unicode 를 끈 엔진에서 ASCII 밖 글자 자리: ASCII 글에 없는 바이트 하나. 그 글자는 ASCII 글에서 맞을 일이 없어 결과가 같다
// (클래스 범위 `À-ɏ` 은 `\xFF-\xFF`, `a-ɏ` 는 `a-\xFF` 가 되어 ASCII 쪽 몫이 그대로다)
const NEVER_ASCII: &str = r"\xFF";

fn push_literal(out: &mut String, c: char, ascii: bool) {
    if ascii && !c.is_ascii() {
        out.push_str(NEVER_ASCII);
    } else {
        out.push(c);
    }
}

fn has_case(c: char) -> bool {
    c.to_lowercase().ne(std::iter::once(c)) || c.to_uppercase().ne(std::iter::once(c))
}

// `chars[at]` 의 `\` 에서 시작하는 escape 하나를 옮긴다. 다음 자리
fn escape(
    chars: &[char],
    at: usize,
    in_class: bool,
    ascii: bool,
    out: &mut String,
    uses: &mut Uses,
) -> Result<usize, String> {
    let e = *chars.get(at + 1).ok_or("a trailing backslash")?;
    let hex = |n: usize| -> Result<String, String> {
        let digits: String = chars.iter().skip(at + 2).take(n).collect();
        if digits.chars().count() == n && digits.chars().all(|d| d.is_ascii_hexdigit()) {
            Ok(digits)
        } else {
            Err(format!("a bad \\{e} escape"))
        }
    };

    // Escapes regex reads like python keep their text, the rest are rewritten here
    match e {
        'w' | 'W' => uses.word = true,
        // python 의 \s 는 U+001C..U+001F 도 받는다. 클래스 안에서도 겹친 클래스로 쓴다
        's' | 'S' => {
            let negate = if e == 'S' { "^" } else { "" };
            let set = if ascii {
                r"\t-\r\x1c-\x20"
            } else {
                r"\s\x1c-\x1f"
            };
            out.push_str(&format!("[{negate}{set}]"));
            return Ok(at + 2);
        }
        'd' | 'D' => uses.digit = true,
        'b' if in_class => {
            out.push_str(r"\x08");
            return Ok(at + 2);
        }
        'b' | 'B' => uses.word = true,
        'A' if !in_class => {}
        'Z' if !in_class => {
            out.push_str(r"\z");
            return Ok(at + 2);
        }
        'n' | 't' | 'r' | 'f' | 'v' | 'a' => {}
        'x' | 'u' | 'U' => {
            let width = match e {
                'x' => 2,
                'u' => 4,
                _ => 8,
            };
            let digits = hex(width)?;
            let code = u32::from_str_radix(&digits, 16).map_err(|e| e.to_string())?;
            if ascii && code >= 0x80 {
                out.push_str(NEVER_ASCII);
            } else {
                out.push_str(&format!(r"\x{{{digits}}}"));
            }
            return Ok(at + 2 + width);
        }
        '0'..='9' => return Err("a back reference or octal escape".into()),
        c if c.is_ascii_alphanumeric() => return Err(format!("the escape \\{c}")),
        c => {
            // An escaped literal: regex wants the backslash only on its meta characters
            if META.contains(c) {
                out.push('\\');
            }
            push_literal(out, c, ascii);
            return Ok(at + 2);
        }
    }

    out.push('\\');
    out.push(e);
    Ok(at + 2)
}

// `chars[at]` 의 `[` 부터 닫는 `]` 까지. python 은 안의 `[`, `&&`, `~~`, `--` 를 글자로 읽고 regex 는 연산으로 읽는다
fn class(
    chars: &[char],
    at: usize,
    ascii: bool,
    out: &mut String,
    uses: &mut Uses,
) -> Result<usize, String> {
    let mut i = at + 1;
    out.push('[');
    if chars.get(i) == Some(&'^') {
        out.push('^');
        i += 1;
    }

    // A `]` right after the opening is a literal in both engines
    let first = i;
    while i < chars.len() {
        let c = chars[i];
        match c {
            ']' if i > first => {
                out.push(']');
                return Ok(i + 1);
            }
            '\\' => {
                i = escape(chars, i, true, ascii, out, uses)?;
                continue;
            }
            '[' | ']' | '&' | '~' => {
                out.push('\\');
                out.push(c);
            }
            '-' if i > first && chars[i - 1] == '-' => out.push_str(r"\-"),
            _ => push_literal(out, c, ascii),
        }
        i += 1;
    }
    Err("an unclosed class".into())
}

// `chars[at]` 의 `(`. 잡기, 묶음, 이름 괄호와 플래그만 받는다
fn group(
    chars: &[char],
    at: usize,
    out: &mut String,
    uses: &mut Uses,
    multiline: &mut bool,
    groups: &mut usize,
) -> Result<usize, String> {
    if chars.get(at + 1) != Some(&'?') {
        *groups += 1;
        out.push('(');
        return Ok(at + 1);
    }

    // Groups regex reads the same way
    let rest: String = chars.iter().skip(at + 2).take(3).collect();
    if rest.starts_with(':') {
        out.push_str("(?:");
        return Ok(at + 3);
    }
    if rest.starts_with("P<")
        || (rest.starts_with('<') && !rest.starts_with("<=") && !rest.starts_with("<!"))
    {
        // A named group: copy the name
        let open = if rest.starts_with('P') {
            at + 4
        } else {
            at + 3
        };
        let close = (open..chars.len())
            .find(|&k| chars[k] == '>')
            .ok_or("an unclosed group name")?;
        *groups += 1;
        out.push_str("(?P<");
        out.extend(&chars[open..close]);
        out.push('>');
        return Ok(close + 1);
    }

    // Constructs the regex crate does not have
    for (head, what) in [
        ("=", "lookahead"),
        ("!", "lookahead"),
        ("<=", "lookbehind"),
        ("<!", "lookbehind"),
        ("P=", "a back reference"),
        (">", "an atomic group"),
        ("#", "a comment group"),
        ("(", "a conditional group"),
    ] {
        if rest.starts_with(head) {
            return Err(what.into());
        }
    }

    // Inline flags, global `(?im)` or scoped `(?i:...)`
    let mut k = at + 2;
    let mut on = String::new();
    while k < chars.len() && chars[k].is_ascii_alphabetic() {
        on.push(chars[k]);
        k += 1;
    }
    if chars.get(k) == Some(&'-') {
        k += 1;
        while k < chars.len() && chars[k].is_ascii_alphabetic() {
            k += 1;
        }
    }
    let end = *chars.get(k).ok_or("an unclosed flag group")?;
    if let Some(bad) = on.chars().find(|f| !"ims".contains(*f)) {
        return Err(format!("the inline flag {bad}"));
    }
    uses.icase |= on.contains('i');
    if end == ')' && on.contains('m') {
        *multiline = true;
    }
    out.extend(&chars[at..=k]);
    Ok(k + 1)
}

// `chars[at]` 의 `{`: python 이 되풀이로 읽으면 `{m,n}` 꼴로, 아니면 글자 `{`
fn brace(chars: &[char], at: usize, out: &mut String) -> Result<usize, String> {
    let digits = |from: usize| -> usize {
        (from..chars.len())
            .find(|&k| !chars[k].is_ascii_digit())
            .unwrap_or(chars.len())
    };
    let lo_end = digits(at + 1);
    let lo: String = chars[at + 1..lo_end].iter().collect();
    let (hi, close) = if chars.get(lo_end) == Some(&',') {
        let hi_end = digits(lo_end + 1);
        (
            Some(chars[lo_end + 1..hi_end].iter().collect::<String>()),
            hi_end,
        )
    } else {
        (None, lo_end)
    };
    if chars.get(at + 1) == Some(&'}') || chars.get(close) != Some(&'}') {
        out.push_str(r"\{");
        return Ok(at + 1);
    }

    // A repetition
    let lo = if lo.is_empty() { "0".to_owned() } else { lo };
    match hi {
        None => out.push_str(&format!("{{{lo}}}")),
        Some(h) => out.push_str(&format!("{{{lo},{h}}}")),
    }
    let mut next = close + 1;
    match chars.get(next) {
        Some('+') => return Err("possessive quantifier".into()),
        Some('?') => {
            out.push('?');
            next += 1;
        }
        _ => {}
    }
    Ok(next)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 옮기지 않는 문법은 이름과 함께 거절하고, python 만의 글자 규칙은 regex 글로 바꾼다.
    #[test]
    fn translates_python_syntax() {
        let t = |p: &str| translate(p, Flags::NONE, false).map(|x| x.body);

        // Rejected constructs
        for p in [
            "(?=a)",
            "(?!a)",
            "(?<=a)",
            "(?<!a)",
            r"(a)\1",
            "(?P=n)",
            "(?>a)",
            "a*+",
            "a++",
            "a?+",
            "a{2}+",
            "(?(1)a|b)",
            "(?x)a",
            "(?#c)",
            r"\0",
        ] {
            assert!(t(p).is_err(), "{p}");
        }
        assert!(translate("é", Flags::IGNORECASE, false).is_err());

        // Python-only literal rules
        assert_eq!(t(r"a\Z").unwrap(), r"a\z");
        assert_eq!(t("a{").unwrap(), r"a\{");
        assert_eq!(t("a{}").unwrap(), r"a\{\}");
        assert_eq!(t("x{,2}y").unwrap(), "x{0,2}y");
        assert_eq!(t("[[&~]").unwrap(), r"[\[\&\~]");
        assert_eq!(t(r"[\b]").unwrap(), r"[\x08]");
        assert_eq!(t(r"\/\<").unwrap(), "/<");
        assert_eq!(t("(?P<k>a)(?<j>b)").unwrap(), "(?P<k>a)(?P<j>b)");

        // Python's \s adds U+001C..U+001F, written for each engine
        assert_eq!(t(r"\s[^\S]").unwrap(), r"[\s\x1c-\x1f][^[^\s\x1c-\x1f]]");
        let ascii = translate(r"\s", Flags::NONE, true).unwrap();
        assert_eq!(ascii.body, r"[\t-\r\x1c-\x20]");

        // The ASCII engine gets a byte no ASCII text has in place of other characters
        let ascii = translate(r"[가-힣a-\u024f]\u2014é", Flags::NONE, true).unwrap();
        assert_eq!(ascii.body, r"[\xFF-\xFFa-\xFF]\xFF\xFF");

        // Feature use decides the guard
        let x = translate(r"(\b)x$(?P<n>.)(?:y)", Flags::NONE, false).unwrap();
        assert!(x.uses.word && x.uses.dollar && !x.uses.digit);
        assert_eq!(x.groups, 2, "plain and named groups count, (?:) does not");
        let x = translate(r"(?m)x$", Flags::NONE, false).unwrap();
        assert!(!x.uses.dollar, "a global (?m) makes $ a line end");
    }
}
