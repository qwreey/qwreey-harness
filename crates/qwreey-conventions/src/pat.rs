//! 정규식 셋을 한 꼴로: 소스의 고정 패턴([`rx::Regex`]), 사람이 쓴 패턴([`py::re::Regex`]), 앞뒤 보기를 코드로 옮긴 패턴([`Look`]).
//!
//! 고정 패턴은 regex crate 로 돈다(Q48 a). regex crate 는 앞뒤 보기를 못 하므로 그런 python 패턴은 [`Look`] 이
//! 같은 일치를 낸다: 일치 앞 글자 검사(뒤보기), 일치 뒤를 먹는 괄호의 시작을 끝으로(앞보기), 거른 자리 다음부터 다시 찾기.
//! 사람이 쓴 패턴(conventions.json, structure.json)은 python 이 물러날 때까지 py::re 다.

use harness_hook::py::re::{self as py_re, Match};
use harness_hook::rx;

/// python 패턴 하나의 찾기들(python `search`, `finditer`, `sub`, `split`).
pub trait Pat: Sync + Send {
    /// python `pattern.search(text, pos)`.
    fn search_from(&self, text: &str, pos: usize) -> Option<Match>;

    /// 엔진을 지금 만들어 본다(시험에서 상수 패턴 확인용). 못 만들면 panic.
    fn check(&self) {}

    /// python `pattern.search(text)`.
    fn search(&self, text: &str) -> Option<Match> {
        self.search_from(text, 0)
    }

    /// python `bool(pattern.search(text))`.
    fn is_match(&self, text: &str) -> bool {
        self.search_from(text, 0).is_some()
    }

    /// python `list(pattern.finditer(text))`. 빈 일치를 내지 않는 패턴의 기본 꼴이다.
    fn find_iter(&self, text: &str) -> Vec<Match> {
        let mut out = Vec::new();
        let mut pos = 0;
        while pos <= text.len() {
            let Some(m) = self.search_from(text, pos) else {
                break;
            };
            pos = if m.end() > m.start() {
                m.end()
            } else {
                m.end() + text[m.end()..].chars().next().map_or(1, char::len_utf8)
            };
            out.push(m);
        }
        out
    }

    /// python `pattern.split(text)`(잡는 괄호가 없는 패턴).
    fn split<'t>(&self, text: &'t str) -> Vec<&'t str> {
        let mut out = Vec::new();
        let mut last = 0;
        for m in self.find_iter(text) {
            out.push(&text[last..m.start()]);
            last = m.end();
        }
        out.push(&text[last..]);
        out
    }

    /// python `pattern.sub(f, text)`.
    fn replace_all(&self, text: &str, f: &mut dyn FnMut(&Match) -> String) -> String {
        let mut out = String::with_capacity(text.len());
        let mut last = 0;
        for m in self.find_iter(text) {
            out.push_str(&text[last..m.start()]);
            out.push_str(&f(&m));
            last = m.end();
        }
        out.push_str(&text[last..]);
        out
    }
}

impl Pat for rx::Regex {
    fn check(&self) {
        rx::Regex::check(self);
    }

    fn search_from(&self, text: &str, pos: usize) -> Option<Match> {
        rx::Regex::search_from(self, text, pos)
    }

    fn is_match(&self, text: &str) -> bool {
        rx::Regex::is_match(self, text)
    }

    fn find_iter(&self, text: &str) -> Vec<Match> {
        rx::Regex::find_iter(self, text)
    }

    fn replace_all(&self, text: &str, f: &mut dyn FnMut(&Match) -> String) -> String {
        rx::Regex::replace_all(self, text, f)
    }
}

impl Pat for py_re::Regex {
    fn search_from(&self, text: &str, pos: usize) -> Option<Match> {
        py_re::Regex::search_from(self, text, pos)
    }

    fn is_match(&self, text: &str) -> bool {
        py_re::Regex::is_match(self, text)
    }

    fn find_iter(&self, text: &str) -> Vec<Match> {
        py_re::Regex::find_iter(self, text)
    }

    fn replace_all(&self, text: &str, f: &mut dyn FnMut(&Match) -> String) -> String {
        py_re::Regex::replace_all(self, text, f)
    }
}

/// 앞뒤 보기가 있던 python 패턴을 regex crate 패턴과 코드 검사로.
///
/// python 은 시작 자리마다 패턴을 해 보고, 뒤보기는 그 자리 앞 글자만 본다. 그래서 regex crate 가 찾은 가장 왼쪽 일치를
/// `keep` 이 거르면 그 자리에는 python 의 일치가 없고, 다음 자리부터 다시 찾는다. 이 꼴이 python 과 같으려면 한 자리에서
/// 갈래가 서로 다른 글자로 시작해야 한다(거른 갈래 대신 다른 갈래가 맞는 일이 없게). 쓰는 곳마다 그것을 확인했다.
pub struct Look {
    rx: rx::Regex,
    /// 일치를 받는가: python 의 뒤보기, 가운데 앞보기를 코드로(글, 일치).
    keep: fn(&str, &Match) -> bool,
    /// 이 괄호가 잡혔으면 그 시작이 일치의 끝이다: 끝의 앞보기를 먹는 괄호로 바꿔 쓴 것.
    tail: Option<usize>,
    /// 거른 뒤 다음 시작: 이 글자들이 이어진 동안은 뒤보기가 늘 거르므로 건너뛴다(없으면 한 글자 뒤).
    skip_run: Option<fn(char) -> bool>,
}

impl Look {
    /// `pattern` 은 python 문법(앞뒤 보기 없이), `keep` 은 받는 일치, `tail` 은 앞보기를 먹은 괄호 번호.
    pub fn new(pattern: &str, keep: fn(&str, &Match) -> bool, tail: Option<usize>) -> Look {
        Look::with_flags(pattern, py_re::Flags::NONE, keep, tail)
    }

    /// [`Look::new`] 에 python 플래그를 붙인 것.
    pub fn with_flags(
        pattern: &str,
        flags: py_re::Flags,
        keep: fn(&str, &Match) -> bool,
        tail: Option<usize>,
    ) -> Look {
        Look {
            rx: rx::Regex::with_flags(pattern, flags),
            keep,
            tail,
            skip_run: None,
        }
    }

    /// 거른 자리 다음, `run` 글자가 이어진 동안을 건너뛴다(긴 낱말 안에서 자리마다 다시 찾지 않게).
    pub fn skipping(mut self, run: fn(char) -> bool) -> Look {
        self.skip_run = Some(run);
        self
    }
}

impl Pat for Look {
    fn check(&self) {
        self.rx.check();
    }

    fn search_from(&self, text: &str, pos: usize) -> Option<Match> {
        let mut at = pos;
        loop {
            let m = self.rx.search_from(text, at)?;
            if (self.keep)(text, &m) {
                return Some(match self.tail.and_then(|g| m.group(g)) {
                    Some((tail, _)) => m.with_end(tail),
                    None => m,
                });
            }

            // The next start python tries; inside a run the char before is again in the run
            let mut next = m.start();
            for c in text[m.start()..].chars() {
                next += c.len_utf8();
                if !self.skip_run.is_some_and(|run| run(c)) {
                    break;
                }
            }
            if next == m.start() {
                return None;
            }
            at = next;
        }
    }
}

/// python 의 `\w`(`isalnum() or "_"`)인가.
pub fn is_word(c: char) -> bool {
    c == '_' || harness_hook::py::unicode::is_alnum(c)
}

/// `text[..at]` 의 마지막 글자.
pub fn before(text: &str, at: usize) -> Option<char> {
    text[..at].chars().next_back()
}

/// 시험용: 바꿔 쓴 패턴이 py::re 의 원래 python 패턴과 같은 일치 범위(와 괄호들)를 내는가.
///
/// `groups` 는 (원래 괄호, 바꾼 괄호) 짝이다. 글마다 python 이 섞어 쓰는 글자(한글, 결합 기호, 위 첨자, 끝 줄바꿈)를 더해 본다.
#[cfg(test)]
pub fn assert_same(
    original: &str,
    flags: py_re::Flags,
    new: &dyn Pat,
    groups: &[(usize, usize)],
    texts: &[&str],
) {
    let original = py_re::Regex::with_flags(original, flags).expect("the python pattern");
    let extras = ["", "\n", "\u{fe0f}", "\u{b2}", "한", " ", "\u{1c}"];
    for text in texts {
        for (pre, post) in extras
            .iter()
            .flat_map(|a| extras.iter().map(move |b| (a, b)))
        {
            let t = format!("{pre}{text}{post}");
            let span = |m: &Match, pairs: &[usize]| -> Vec<Option<(usize, usize)>> {
                std::iter::once(Some((m.start(), m.end())))
                    .chain(pairs.iter().map(|&g| m.group(g)))
                    .collect()
            };
            let want: Vec<_> = original
                .find_iter(&t)
                .iter()
                .map(|m| span(m, &groups.iter().map(|g| g.0).collect::<Vec<_>>()))
                .collect();
            let got: Vec<_> = new
                .find_iter(&t)
                .iter()
                .map(|m| span(m, &groups.iter().map(|g| g.1).collect::<Vec<_>>()))
                .collect();
            assert_eq!(got, want, "{t:?}");
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 뒤보기를 코드로 옮긴 꼴은 py::re 가 원래 패턴으로 낸 일치와 같다(긴 낱말을 건너뛰어도).
    #[test]
    fn look_matches_py_re_on_lookbehind() {
        // python: (?<![\w-])audit/
        let original = py_re::Regex::new(r"(?<![\w-])audit/").unwrap();
        let look = Look::new(
            "audit/",
            |t, m| before(t, m.start()).is_none_or(|c| !is_word(c) && c != '-'),
            None,
        )
        .skipping(|c| is_word(c) || c == '-');

        // Starts, word runs, hyphens and non-ASCII before the name
        for text in [
            "audit/x",
            "xaudit/ audit/",
            "a-audit/ (audit/1",
            "한audit/ 。audit/",
            "audit/audit/",
            "xx",
            "",
        ] {
            let want: Vec<(usize, usize)> = original
                .find_iter(text)
                .iter()
                .map(|m| (m.start(), m.end()))
                .collect();
            let got: Vec<(usize, usize)> = look
                .find_iter(text)
                .iter()
                .map(|m| (m.start(), m.end()))
                .collect();
            assert_eq!(got, want, "{text:?}");
        }
    }

    /// 끝 앞보기를 먹는 괄호로 바꾼 꼴은 python 의 일치 범위와 다음 시작을 지킨다.
    #[test]
    fn look_matches_py_re_on_tail_lookahead() {
        // python: \bP\d{2,3}\b(?=\s*(?:p|fps|hz))
        let original = py_re::Regex::new(r"\bP\d{2,3}\b(?=\s*(?:p|fps|hz))").unwrap();
        let look = Look::new(r"\bP\d{2,3}\b(\s*(?:p|fps|hz))", |_, _| true, Some(1));
        for text in ["P60 fps P120hz", "P1080p", "P60 x", "P60P60 hz", "P601 fps"] {
            let want: Vec<(usize, usize)> = original
                .find_iter(text)
                .iter()
                .map(|m| (m.start(), m.end()))
                .collect();
            let got: Vec<(usize, usize)> = look
                .find_iter(text)
                .iter()
                .map(|m| (m.start(), m.end()))
                .collect();
            assert_eq!(got, want, "{text:?}");
        }
    }
}
