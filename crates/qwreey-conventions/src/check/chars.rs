//! 키보드로 치지 않는 글자, 보이지 않는 글자, 주석 안의 유니코드 이스케이프(python `odd_chars`, `INVISIBLE`, `ESCAPE`).

use std::sync::LazyLock;

use harness_hook::py::value::Value;
use harness_hook::rx::Regex;

use super::char_tables::{LETTER_MARK_DIGIT, SYMBOL_HINTS, UPPER};
use crate::halt::{Halt, Result};

const EMOJI_RANGES: &[(u32, u32)] = &[
    (0x1F000, 0x1FAFF),
    (0x2600, 0x27BF),
    (0x2B00, 0x2BFF),
    (0xFE00, 0xFE0F),
    (0x20E3, 0x20E3),
];
const FULLWIDTH_RANGES: &[(u32, u32)] = &[(0x3000, 0x3000), (0xFF01, 0xFF5E), (0xFFE0, 0xFFE6)];

/// 흔한 기호의 대체(python `SYMBOL_FIX`). 키가 없으면 ASCII 나 평범한 단어로 풀어 쓴다.
const SYMBOL_FIX: &[(char, &str)] = &[
    ('\u{2014}', "-"),
    ('\u{2013}', "-"),
    ('\u{2015}', "-"),
    ('\u{2212}', "-"),
    ('\u{00b7}', ","),
    ('\u{2022}', "-"),
    ('\u{2026}', "..."),
    ('\u{2192}', "->"),
    ('\u{2190}', "<-"),
    ('\u{2194}', "<->"),
    ('\u{21d2}', "=>"),
    ('\u{00a7}', "(omit)"),
    ('\u{00d7}', "x"),
    ('\u{2265}', ">="),
    ('\u{2264}', "<="),
    ('\u{2260}', "!="),
    ('\u{201c}', "\""),
    ('\u{201d}', "\""),
    ('\u{2018}', "'"),
    ('\u{2019}', "'"),
    ('\u{2713}', "ok"),
    ('\u{2714}', "ok"),
    ('\u{2717}', "FAIL"),
    ('\u{2718}', "FAIL"),
    ('\u{26a0}', "NOTE:"),
];

/// 주석 안의 유니코드 이스케이프(python `ESCAPE`): 금지 글자를 이스케이프로 적어 검사를 피한 것.
pub static ESCAPE: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"\\u[0-9A-Fa-f]{4}|\\u\{[0-9A-Fa-f]+\}|\\U[0-9A-Fa-f]{8}"));

fn in_ranges(table: &[(u32, u32)], c: u32) -> bool {
    table
        .binary_search_by(|&(lo, hi)| {
            if hi < c {
                std::cmp::Ordering::Less
            } else if lo > c {
                std::cmp::Ordering::Greater
            } else {
                std::cmp::Ordering::Equal
            }
        })
        .is_ok()
}

/// 보이지 않는 글자, 방향 제어 글자인가(python `INVISIBLE`: 소프트 하이픈, NBSP, ZW*, 방향 표식, 임베딩, 고립, WORD JOINER, BOM).
pub fn is_invisible(c: char) -> bool {
    matches!(c,
        '\u{00ad}' | '\u{00a0}' | '\u{061c}' | '\u{180e}' | '\u{200b}'..='\u{200f}'
        | '\u{202a}'..='\u{202e}' | '\u{2060}'..='\u{2069}' | '\u{feff}')
}

/// python `ch.isupper()`(한 글자).
pub fn is_upper(c: char) -> bool {
    in_ranges(UPPER, u32::from(c))
}

// 범위 표는 정렬되지 않았다(python 과 같은 순서로 둔다): 차례로 본다
fn in_any(table: &[(u32, u32)], c: char) -> bool {
    table
        .iter()
        .any(|&(lo, hi)| (lo..=hi).contains(&u32::from(c)))
}

fn is_emoji(c: char) -> bool {
    in_any(EMOJI_RANGES, c)
}

/// 허용 글자 설정(python `cfg.get("allow_chars") or []`): `"emoji"` 는 이모지를 끄고, 나머지는 허용할 글자를 이은 글이다.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct Allow {
    pub emoji: bool,
    pub literal: String,
}

impl Allow {
    /// 설정 값을 python 처럼 읽는다: 목록은 원소, 글은 글자(그리고 `"emoji" in 글` 은 부분 글 찾기), dict 는 키.
    ///
    /// 목록에 글이 아닌 원소가 있거나 돌 수 없는 참 값이면 python 은 `in` 이나 `join` 에서 끝난다.
    pub fn from_value(value: Option<&Value>) -> Result<Allow> {
        let keys: Vec<String> = match value {
            None => return Ok(Allow::default()),
            Some(v) if !v.truthy() => return Ok(Allow::default()),
            Some(Value::Str(s)) => {
                return Ok(Allow {
                    emoji: s.contains("emoji"),
                    literal: s.clone(),
                });
            }
            Some(Value::List(items)) => {
                let emoji = items.iter().any(|v| v.as_str() == Some("emoji"));
                let mut literal = String::new();
                for v in items {
                    match v {
                        Value::Str(s) if s == "emoji" => {}
                        Value::Str(s) => literal.push_str(s),
                        _ => return Err(Halt::PyError("allow_chars has a non-string item")),
                    }
                }
                return Ok(Allow { emoji, literal });
            }
            Some(Value::Dict(d)) => d.iter().map(|(k, _)| k.to_owned()).collect(),
            Some(_) => return Err(Halt::PyError("allow_chars is not iterable")),
        };
        Ok(Allow {
            emoji: keys.iter().any(|k| k == "emoji"),
            literal: keys
                .iter()
                .filter(|k| *k != "emoji")
                .map(String::as_str)
                .collect(),
        })
    }
}

/// python `odd_chars(text, allow)`: 키보드로 치지 않는 글자(기호, 곡선 따옴표, 전각, 이모지)가 있는가.
///
/// ASCII, 허용 글자, 보이지 않는 글자(따로 알린다), 일반 범주 L*, M*, Nd 는 통과한다.
pub fn odd_chars(text: &str, allow: &Allow) -> bool {
    text.chars().any(|c| odd_char(c, allow))
}

fn odd_char(c: char, allow: &Allow) -> bool {
    if c.is_ascii() || allow.literal.contains(c) || is_invisible(c) {
        return false;
    }
    if is_emoji(c) {
        return !allow.emoji;
    }
    if in_any(FULLWIDTH_RANGES, c) {
        return true;
    }
    !in_ranges(LETTER_MARK_DIGIT, u32::from(c))
}

/// python `invisible_lines(text, added)`: 추가한 줄 가운데 보이지 않는 글자가 있는 줄(1 기반). 파일 맨 앞 BOM 은 통과.
pub fn invisible_lines(text: &str, added: &crate::edit::Added) -> Vec<usize> {
    let mut out = Vec::new();
    for (idx, line) in text.split('\n').enumerate() {
        if !added.contains(&idx) {
            continue;
        }
        let line = if idx == 0 {
            line.strip_prefix('\u{feff}').unwrap_or(line)
        } else {
            line
        };
        if line.chars().any(is_invisible) {
            out.push(idx + 1);
        }
    }
    out
}

// 줄 번호(1 기반) n 의 글. 범위 밖이면 빈 글(python `src[n - 1] if 0 < n <= len(src) else ""`)
fn line_of<'t>(src: &[&'t str], n: usize) -> &'t str {
    if n == 0 {
        ""
    } else {
        src.get(n - 1).copied().unwrap_or("")
    }
}

/// python `symbol_detail(text, lines, allow)`: 알림에 적을 글자와 대체(`글자들 (use "대체", ...)`). 없으면 빈 글.
pub fn symbol_detail(text: &str, lines: &[usize], allow: &Allow) -> String {
    let src: Vec<&str> = text.split('\n').collect();
    let probe = Allow {
        emoji: allow.emoji,
        literal: String::new(),
    };
    let mut odd: Vec<char> = Vec::new();
    let mut fixes: Vec<String> = Vec::new();
    for &n in lines {
        for c in line_of(&src, n).chars() {
            if c.is_ascii()
                || odd.contains(&c)
                || allow.literal.contains(c)
                || is_invisible(c)
                || !odd_char(c, &probe)
            {
                continue;
            }
            odd.push(c);
            let fix = symbol_fix(c);
            if !fixes.iter().any(|f| f == fix) {
                fixes.push(fix.to_owned());
            }
        }
    }
    if odd.is_empty() {
        return String::new();
    }

    let mut shown: String = odd
        .iter()
        .take(6)
        .map(char::to_string)
        .collect::<Vec<_>>()
        .join(" ");
    if odd.len() > 6 {
        shown.push_str(" ...");
    }
    let uses: Vec<String> = fixes.iter().take(6).map(|f| format!("\"{f}\"")).collect();
    format!("{shown} (use {})", uses.join(", "))
}

// 글자 하나의 대체: SYMBOL_FIX, 원 숫자와 호환 글자(생성한 표), 이모지, 그 밖
fn symbol_fix(c: char) -> &'static str {
    if let Some((_, fix)) = SYMBOL_FIX.iter().find(|(k, _)| *k == c) {
        return fix;
    }
    if let Ok(i) = SYMBOL_HINTS.binary_search_by_key(&u32::from(c), |&(cp, _)| cp) {
        return SYMBOL_HINTS[i].1;
    }
    if is_emoji(c) {
        "ok, FAIL, NOTE: or plain words"
    } else {
        "plain ASCII or words"
    }
}

/// python `invisible_detail(text, lines)`: 줄들의 보이지 않는 글자를 코드 포인트로(`U+200B (delete it)`).
pub fn invisible_detail(text: &str, lines: &[usize]) -> String {
    let src: Vec<&str> = text.split('\n').collect();
    let mut cps: Vec<String> = Vec::new();
    for &n in lines {
        for c in line_of(&src, n).chars().filter(|&c| is_invisible(c)) {
            let cp = format!("U+{:04X}", u32::from(c));
            if !cps.contains(&cp) {
                cps.push(cp);
            }
        }
    }
    if cps.is_empty() {
        return String::new();
    }
    format!("{} (delete it)", cps[..cps.len().min(6)].join(" "))
}

/// python `escape_detail(text, lines)`: 줄들의 이스케이프 글(앞 넷).
pub fn escape_detail(text: &str, lines: &[usize]) -> String {
    let src: Vec<&str> = text.split('\n').collect();
    let mut found: Vec<&str> = Vec::new();
    for &n in lines {
        let line = line_of(&src, n);
        for m in ESCAPE.find_iter(line) {
            let s = &line[m.start()..m.end()];
            if !found.contains(&s) {
                found.push(s);
            }
        }
    }
    if found.is_empty() {
        return String::new();
    }
    format!(
        "{} (write the character itself or reword)",
        found[..found.len().min(4)].join(" ")
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 키보드로 치지 않는 글자를 거르고, 알림에 대체 글과 코드 포인트를 적는다.
    #[test]
    fn odd_and_fixes() {
        // Symbols and full-width forms are odd, letters are not
        let none = Allow::default();
        assert!(odd_chars("a \u{2014} b", &none));
        assert!(!odd_chars("한글 caf\u{e9}", &none));
        assert!(odd_chars("\u{ff21}", &none));

        // Notices name each character with its fix
        assert_eq!(
            symbol_detail("x \u{2014}\u{2460}\u{ff01}", &[1], &none),
            "\u{2014} \u{2460} \u{ff01} (use \"-\", \"1)\", \"!\")"
        );
        assert_eq!(invisible_detail("a\u{200b}", &[1]), "U+200B (delete it)");
        assert_eq!(
            escape_detail("// \\u00e9 \\u{1F600}", &[1]),
            "\\u00e9 \\u{1F600} (write the character itself or reword)"
        );

        // Emoji are odd without the emoji setting
        assert!(
            odd_chars("\u{fe0f}", &none),
            "a variation selector is in the emoji ranges, which python checks before the category"
        );
        let emoji =
            Allow::from_value(Some(&Value::List(vec![Value::Str("emoji".into())]))).unwrap();
        assert!(!odd_chars("\u{1F600}", &emoji));
        assert!(is_upper('A') && !is_upper('a'));
    }

    /// 이 모듈의 고정 패턴이 모두 regex crate 로 옮겨지고 엔진이 만들어진다.
    #[test]
    fn fixed_patterns_build() {
        ESCAPE.check();
    }
}
