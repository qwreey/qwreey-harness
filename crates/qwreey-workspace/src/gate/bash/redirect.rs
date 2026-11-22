//! 리다이렉트 대상(python `REDIR.finditer(seg)` 의 첫 괄호).
//!
//! python 패턴: `(?<![0-9&<>])\d?>>?(?!&)\s*([^\s;|&<>()]+)`. 앞뒤 보기가 있어 rx(regex crate)가 받지 못하고,
//! 조각 하나는 짧아 py::re 를 만드는 값이 찾는 값보다 크다. 그래서 같은 뜻을 손으로 훑는다:
//! - 시작 앞 글자가 ASCII 숫자, `&`, `<`, `>` 가 아니다.
//! - Unicode 십진 숫자 하나(python `\d`)가 올 수 있고, 그 뒤 `>` 또는 `>>`. 바로 뒤가 `&` 면 안 된다(`>&2`).
//!   `>>` 다음이 `&` 면 `>` 하나로 다시 본다(되돌아가기). 그때 다음 글자가 `>` 라 대상이 될 수 없다.
//! - 공백(python `\s`)을 건너 대상 글자(공백과 `;|&<>()` 밖)가 하나 이상.

use harness_hook::py::text::is_space;
use harness_hook::py::unicode::is_decimal;

/// 조각의 리다이렉트 대상들, 앞에서부터(겹치지 않게).
pub fn targets(seg: &str) -> Vec<String> {
    let chars: Vec<char> = seg.chars().collect();
    let mut out = Vec::new();
    let mut at = 0;
    while at < chars.len() {
        match match_at(&chars, at) {
            Some((start, end)) => {
                out.push(chars[start..end].iter().collect());
                at = end;
            }
            None => at += 1,
        }
    }
    out
}

// `at` 에서 시작하는 일치의 대상 자리(글자 단위)
fn match_at(chars: &[char], at: usize) -> Option<(usize, usize)> {
    if at > 0 && matches!(chars[at - 1], '0'..='9' | '&' | '<' | '>') {
        return None;
    }

    // An optional fd digit, then `>>` or `>`
    let arrow = if is_decimal(u32::from(chars[at])) {
        at + 1
    } else {
        at
    };
    if chars.get(arrow) != Some(&'>') {
        return None;
    }
    if chars.get(arrow + 1) == Some(&'>')
        && let Some(found) = target_after(chars, arrow + 2)
    {
        return Some(found);
    }
    target_after(chars, arrow + 1)
}

// `(?!&)\s*([^\s;|&<>()]+)` 를 `at` 에서
fn target_after(chars: &[char], at: usize) -> Option<(usize, usize)> {
    if chars.get(at) == Some(&'&') {
        return None;
    }
    let start = at + chars[at..].iter().take_while(|c| is_space(**c)).count();
    let len = chars[start..].iter().take_while(|c| is_target(**c)).count();
    (len > 0).then_some((start, start + len))
}

fn is_target(c: char) -> bool {
    !is_space(c) && !matches!(c, ';' | '|' | '&' | '<' | '>' | '(' | ')')
}

#[cfg(test)]
mod tests {
    use super::*;
    use harness_hook::py::re::Regex;
    use harness_hook::testkit::corpus;

    /// 손으로 훑은 대상이 python 패턴(py::re)의 finditer 첫 괄호와 같다.
    #[test]
    fn targets_match_the_python_pattern() {
        let pattern = Regex::new(r"(?<![0-9&<>])\d?>>?(?!&)\s*([^\s;|&<>()]+)").unwrap();
        let pieces = [
            ">", ">>", "&", "<", "2", "1", "\u{663}", " ", "\u{a0}", "a", "/x", ";", "(", "|",
            "\u{e9}",
        ];

        for text in corpus(&pieces, 5000) {
            let want: Vec<String> = pattern
                .find_iter(&text)
                .iter()
                .map(|m| m.text(&text, 1).unwrap_or("").to_owned())
                .collect();
            assert_eq!(targets(&text), want, "{text:?}");
        }
    }
}
