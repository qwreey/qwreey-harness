//! 코드에 적은 고정 정규식: 보통 글은 regex crate 로, 두 엔진이 다르게 읽는 글자가 든 글은 `harness_hook::py::re` 로 판정한다.
// @copy-of: crates/qwreey-advisor/src/fixed_re.rs
// crates/qwreey-reply-language 에 같은 바이트의 사본이 있다(플러그인 바이너리끼리 기대지 않는다). harness-hook 으로 옮길 후보다.
//!
//! regex crate 와 python `re` 는 대부분의 글에서 같은 자리에 맞는다. 갈리는 것은 글자 판정이다:
//! - `\w`(그래서 `\b`): python 은 문자(L), 숫자(N), `_`. regex 는 Alphabetic, 결합 표시(M), Nd, Pc, Join_Control.
//! - `\s`: python 은 U+001C..U+001F 도 공백으로 본다.
//! - `(?i)`: python 은 `i` 와 `İ`(U+0130), `ı`(U+0131)를 같게 본다. regex 의 단순 대소문자 접기는 아니다.
//!
//! 그래서 글에 그런 글자([`divergent`])가 있으면 python 판 패턴을 `py::re` 로 돌린다(처음 쓸 때 한 번 읽는다).
//! 그 밖의 문법 차이(`\Z`, 앞뒤 보기, 괄호 참조, `$` 가 끝 줄바꿈 앞에서도 맞는 것)는 regex 판 패턴을 따로 적어 맞춘다.
//! 빈 일치가 나는 패턴은 쓰지 않는다(빈 일치 뒤의 반복 규칙이 두 엔진에서 다르다).

use std::sync::OnceLock;

use harness_hook::py::re::{Flags, Regex as PyRegex};
use harness_hook::py::unicode::is_word;
use regex::{Regex, RegexBuilder};

/// 두 엔진의 판정이 갈리는 글자인가: 위 머리말의 세 갈래. 이런 글자가 없는 글에서는 두 엔진의 판정이 같다.
// 정규식으로 적으면 훅마다 큰 Unicode 집합을 새로 읽는다(훅 한 번에 0.3~0.4 ms 더 든다). regex 의 \w 표는 regex-syntax 가 그대로 준다
fn divergent_char(c: char) -> bool {
    match c {
        '\x1C'..='\x1F' | '\u{130}' | '\u{131}' => true,
        _ if c.is_ascii() => false,
        _ => is_word(u32::from(c)) != regex_syntax::is_word_character(c),
    }
}

/// 글에 두 엔진이 다르게 읽는 글자가 있나.
pub fn divergent(text: &str) -> bool {
    text.chars().any(divergent_char)
}

/// 일치 하나의 괄호별 바이트 범위(0 번이 전체).
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Caps {
    spans: Vec<Option<(usize, usize)>>,
}

impl Caps {
    fn from_rust(caps: &regex::Captures<'_>) -> Caps {
        Caps {
            spans: caps
                .iter()
                .map(|g| g.map(|m| (m.start(), m.end())))
                .collect(),
        }
    }

    fn from_py(m: &harness_hook::py::re::Match, groups: usize) -> Caps {
        Caps {
            spans: (0..=groups).map(|i| m.group(i)).collect(),
        }
    }

    /// 일치의 시작.
    pub fn start(&self) -> usize {
        self.spans[0].map_or(0, |(s, _)| s)
    }

    /// 일치의 끝.
    pub fn end(&self) -> usize {
        self.spans[0].map_or(0, |(_, e)| e)
    }

    /// 괄호 `i` 가 잡은 글(맞지 않은 괄호는 `None`).
    pub fn text<'t>(&self, text: &'t str, i: usize) -> Option<&'t str> {
        let (s, e) = (*self.spans.get(i)?)?;
        Some(&text[s..e])
    }
}

/// 고정 패턴 하나: regex 판과 python 판.
pub struct Fixed {
    rust: Regex,
    py_pattern: &'static str,
    flags: Flags,
    py: OnceLock<Option<PyRegex>>,
}

impl Fixed {
    /// 두 엔진이 같은 문법으로 읽는 패턴, 플래그 없음.
    pub fn new(pattern: &'static str) -> Fixed {
        Fixed::with_rust(pattern, pattern, Flags::NONE)
    }

    /// 두 엔진이 같은 문법으로 읽는 패턴과 python 플래그.
    pub fn with_flags(pattern: &'static str, flags: Flags) -> Fixed {
        Fixed::with_rust(pattern, pattern, flags)
    }

    /// python 판(`py_pattern`)과 regex 판(`rust_pattern`)을 따로 적은 패턴. 둘은 같은 글에 같은 자리에서 맞아야 한다.
    pub fn with_rust(py_pattern: &'static str, rust_pattern: &str, flags: Flags) -> Fixed {
        let rust = RegexBuilder::new(rust_pattern)
            .case_insensitive(flags.ignore_case)
            .multi_line(flags.multiline)
            .dot_matches_new_line(flags.dotall)
            .build()
            .expect("built-in pattern");
        Fixed {
            rust,
            py_pattern,
            flags,
            py: OnceLock::new(),
        }
    }

    // python 판은 갈리는 글자가 있을 때만 읽는다. 읽지 못하면(옮기지 않은 문법) regex 판을 쓴다
    fn py_for(&self, text: &str) -> Option<&PyRegex> {
        if !divergent(text) {
            return None;
        }
        self.py
            .get_or_init(|| PyRegex::with_flags(self.py_pattern, self.flags).ok())
            .as_ref()
    }

    /// python `pattern.search(text)` 가 맞는가.
    pub fn is_match(&self, text: &str) -> bool {
        match self.py_for(text) {
            Some(py) => py.is_match(text),
            None => self.rust.is_match(text),
        }
    }

    /// python `pattern.search(text)`.
    pub fn search(&self, text: &str) -> Option<Caps> {
        match self.py_for(text) {
            Some(py) => py.search(text).map(|m| Caps::from_py(&m, py.groups())),
            None => self.rust.captures(text).map(|c| Caps::from_rust(&c)),
        }
    }

    /// python `pattern.match(text)`: 맨 앞에서 맞는 일치. 맨 앞 일치가 있으면 그것이 가장 왼쪽 일치라 search 로 찾는다.
    pub fn match_start(&self, text: &str) -> Option<Caps> {
        self.search(text).filter(|c| c.start() == 0)
    }

    /// python `pattern.finditer(text)`: 겹치지 않는 일치들.
    pub fn find_iter(&self, text: &str) -> Vec<Caps> {
        match self.py_for(text) {
            Some(py) => py
                .find_iter(text)
                .iter()
                .map(|m| Caps::from_py(m, py.groups()))
                .collect(),
            None => self
                .rust
                .captures_iter(text)
                .map(|c| Caps::from_rust(&c))
                .collect(),
        }
    }

    /// python `pattern.sub(f, text)`.
    pub fn replace_all(&self, text: &str, mut f: impl FnMut(&Caps) -> String) -> String {
        let mut out = String::with_capacity(text.len());
        let mut last = 0;
        for caps in self.find_iter(text) {
            out.push_str(&text[last..caps.start()]);
            out.push_str(&f(&caps));
            last = caps.end();
        }
        out.push_str(&text[last..]);
        out
    }
}

/// 시험용: regex 판이 python 판(py::re)과 같은 일치를 내는가. 갈리는 글자가 든 글은 늘 python 판이 돌므로 참이다.
#[cfg(test)]
pub fn agrees_with_py(fixed: &Fixed, text: &str) -> bool {
    if divergent(text) {
        return true;
    }

    // Matches from both engines
    let py = PyRegex::with_flags(fixed.py_pattern, fixed.flags).expect("python pattern");
    let want: Vec<Caps> = py
        .find_iter(text)
        .iter()
        .map(|m| Caps::from_py(m, py.groups()))
        .collect();
    let got: Vec<Caps> = fixed
        .rust
        .captures_iter(text)
        .map(|c| Caps::from_rust(&c))
        .collect();

    // regex 판이 python 판의 괄호 없이 적힌 패턴(펼친 괄호 참조)은 일치 전체만 비교한다
    if fixed.rust.captures_len() != py.groups() + 1 {
        let whole = |caps: &[Caps]| {
            caps.iter()
                .map(|c| (c.start(), c.end()))
                .collect::<Vec<_>>()
        };
        return whole(&want) == whole(&got);
    }
    want == got
}

/// 시험용: 결정적 의사 난수(xorshift64). 같은 `seed` 면 같은 수열이다.
#[cfg(test)]
pub fn xorshift(mut seed: u64) -> impl FnMut() -> u64 {
    move || {
        seed ^= seed << 13;
        seed ^= seed >> 7;
        seed ^= seed << 17;
        seed
    }
}

/// 시험용: `pieces` 를 이어 붙인 글 `n` 개(결정적 의사 난수, 한 글에 1..12 조각).
#[cfg(test)]
pub fn corpus(pieces: &[&str], n: usize) -> Vec<String> {
    let mut next = xorshift(0x2545_f491_4f6c_dd1d);
    (0..n)
        .map(|_| {
            let count = (next() % 12) as usize + 1;
            (0..count)
                .map(|_| pieces[(next() % pieces.len() as u64) as usize])
                .collect()
        })
        .collect()
}

/// 시험용: 이름 붙인 패턴마다 [`corpus`] 의 모든 글에서 [`agrees_with_py`] 인지 본다. 어긋나면 패턴 이름과 글로 멈춘다.
#[cfg(test)]
pub fn assert_agree(patterns: &[(&str, &Fixed)], pieces: &[&str]) {
    for text in corpus(pieces, 3000) {
        for (name, fixed) in patterns {
            assert!(
                agrees_with_py(fixed, &text),
                "{name} differs from python on {text:?}"
            );
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use harness_hook::py::text::is_space;
    use harness_hook::py::unicode::{is_decimal, is_word};

    /// 손으로 적은 판정이 regex 의 집합 연산으로 적은 정의와 모든 글자에서 같다.
    #[test]
    fn divergent_char_matches_set_definition() {
        let defined =
            Regex::new(r"^(?:[\x1C-\x1F\u{130}\u{131}]|[\w--[\p{L}\p{N}_]]|[[\p{L}\p{N}_]--\w])$")
                .expect("definition");
        for c in (0..=0x10_FFFFu32).filter_map(char::from_u32) {
            assert_eq!(
                divergent_char(c),
                defined.is_match(c.encode_utf8(&mut [0; 4])),
                "U+{:04X}",
                u32::from(c)
            );
        }
    }

    /// 갈리는 글자가 아니면 regex 의 `\w`, `\s`, `\d` 가 python 과 같다(두 Unicode 표의 판이 맞는지도 여기서 본다).
    #[test]
    fn classes_agree_outside_divergent_chars() {
        // One-char probes for each class
        let word = Regex::new(r"^\w$").expect("class");
        let space = Regex::new(r"^\s$").expect("class");
        let digit = Regex::new(r"^\d$").expect("class");
        let mut mismatches = Vec::new();
        for c in (0..=0x10_FFFFu32).filter_map(char::from_u32) {
            let s = c.to_string();
            if divergent(&s) {
                continue;
            }
            let code = u32::from(c);
            if word.is_match(&s) != is_word(code)
                || space.is_match(&s) != is_space(c)
                || digit.is_match(&s) != is_decimal(code)
            {
                mismatches.push(code);
            }
        }

        // python's tables come from harness-hook (generated by python 3.14)
        assert!(
            mismatches.is_empty(),
            "{} chars differ, first {:x?}",
            mismatches.len(),
            &mismatches[..mismatches.len().min(8)]
        );
    }

    /// `(?i)` 는 갈리는 글자(İ, ı) 밖에서 python 과 같다: K 와 켈빈 기호, s 와 긴 s.
    #[test]
    fn ignore_case_agrees() {
        let k = Fixed::with_flags("k", Flags::IGNORECASE);
        assert!(
            k.is_match("\u{212a}"),
            "Kelvin sign folds to k in both engines"
        );
        let i = Fixed::with_flags("i", Flags::IGNORECASE);
        assert!(
            i.is_match("\u{130}"),
            "python matches dotted capital I; the py::re path answers"
        );
        assert!(!Fixed::with_flags("x", Flags::IGNORECASE).is_match("\u{131}"));
    }
}
