//! 소스에 글로 적힌 고정 정규식(Q48 a): python re 문법의 패턴을 regex crate 로 돌린다. 결과는 [`crate::py::re`] 와 같다.
//!
//! why not py::re 만: py::re 는 python 과 바이트까지 같게 하려고 sre 의 되돌아가며 찾기를 옮긴 것이라 큰 파일에서 느리다
//! (conventions 의 큰 파일에서 python re 의 절반 속도). regex crate 는 같은 패턴을 선형 시간에 돈다.
//! why not regex crate 만: 두 엔진은 몇 글자에서 뜻이 갈린다. 그 글자가 든 글은 py::re 로 넘겨 python 과 같은 답을 낸다.
//!
//! 엔진은 글마다 고른다. 모두 처음 쓸 때 만든다(훅은 한 번 뜨고 끝나서, 만드는 값이 찾는 값보다 크기 쉽다).
//! - ASCII 글: Unicode 를 끈 regex(`\w \d \b` 와 IGNORECASE 가 ASCII). ASCII 글에서는 python 과 뜻이 같고 만드는 값이 작다.
//! - ASCII 밖 글자가 든 글: Unicode regex. 아래 갈림 글자가 들었으면 py::re.
//!
//! 갈리는 곳과 검사([`tables`] 는 모든 코드 포인트에서 두 엔진을 견준 시험이 지킨다):
//! - `\w \W \b \B`: python 은 `isalnum() or "_"`, regex 는 Unicode Word(결합 기호, `²` 같은 No 숫자, `_` 밖의 Pc, ZWJ 등이 다르다).
//! - `\s \S`: python 은 U+001C..U+001F 도 공백으로 본다. 옮길 때 그 범위를 더한다.
//! - `\d \D`: 두 표가 같다(시험이 지킨다).
//! - MULTILINE 이 아닌 `$`: python 은 글 끝의 줄바꿈 앞에서도 맞는다. 그런 글은 py::re.
//! - IGNORECASE: python 은 U+0130, U+0131 을 `i` 와 같게 본다(regex 는 단순 접기만). 패턴의 대소문자 글자는 ASCII 만 받는다.
//! - 빈 일치 다음: python 3.7+ 은 빈 일치 바로 뒤 같은 자리에서 빈 것이 아닌 일치를 찾는다. regex crate 는 이것을 못 해서
//!   그런 자리를 만나면 py::re 로 다시 돈다.
//!
//! 앞뒤 보기, 괄호 참조, 원자 괄호, 소유 되풀이, 조건 괄호, `(?x)` 는 옮기지 않는다(패턴을 그것 없이 다시 쓴다). 그런 패턴을
//! 받으면 panic 이다: 패턴은 상수이고 [`Regex::with_flags`] 가 글을 옮길 때 알린다.

mod tables;
mod translate;

use std::sync::OnceLock;

use crate::py::re::{self as py_re, Flags, Match};
use crate::py::unicode::in_ranges;
use translate::translate;

/// 패턴이 쓰는, 두 엔진의 뜻이 갈릴 수 있는 것들.
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
struct Uses {
    word: bool,
    digit: bool,
    /// MULTILINE 이 아닌 `$`.
    dollar: bool,
    icase: bool,
}

// 찾는 꼴: 아무 데서나(search), 맨 앞에서(match), 글 전체(fullmatch)
#[derive(Clone, Copy)]
enum Kind {
    Search = 0,
    Anchored = 1,
    Full = 2,
}

impl Kind {
    fn wrap(self, body: &str) -> String {
        match self {
            Kind::Search => body.to_owned(),
            Kind::Anchored => format!(r"\A(?:{body})"),
            Kind::Full => format!(r"\A(?:{body})\z"),
        }
    }
}

// regex crate 엔진 하나(Unicode 를 켠 글 엔진, 끈 바이트 엔진)
trait Engine: Sized {
    fn build(body: &str, flags: Flags) -> Result<Self, regex::Error>;
    fn matches(&self, text: &str) -> bool;
    fn captures_at(&self, text: &str, pos: usize) -> Option<Match>;
}

impl Engine for regex::Regex {
    fn build(body: &str, flags: Flags) -> Result<Self, regex::Error> {
        regex::RegexBuilder::new(body)
            .case_insensitive(flags.ignore_case)
            .multi_line(flags.multiline)
            .dot_matches_new_line(flags.dotall)
            .build()
    }

    fn matches(&self, text: &str) -> bool {
        self.is_match(text)
    }

    fn captures_at(&self, text: &str, pos: usize) -> Option<Match> {
        let mut locs = self.capture_locations();
        self.captures_read_at(&mut locs, text, pos)?;
        Some(to_match((0..locs.len()).map(|i| locs.get(i))))
    }
}

impl Engine for regex::bytes::Regex {
    fn build(body: &str, flags: Flags) -> Result<Self, regex::Error> {
        regex::bytes::RegexBuilder::new(body)
            .unicode(false)
            .case_insensitive(flags.ignore_case)
            .multi_line(flags.multiline)
            .dot_matches_new_line(flags.dotall)
            .build()
    }

    fn matches(&self, text: &str) -> bool {
        self.is_match(text.as_bytes())
    }

    fn captures_at(&self, text: &str, pos: usize) -> Option<Match> {
        let mut locs = self.capture_locations();
        self.captures_read_at(&mut locs, text.as_bytes(), pos)?;
        Some(to_match((0..locs.len()).map(|i| locs.get(i))))
    }
}

fn to_match(spans: impl Iterator<Item = Option<(usize, usize)>>) -> Match {
    let mut slots = Vec::new();
    for span in spans {
        slots.push(span.map(|s| s.0));
        slots.push(span.map(|s| s.1));
    }
    Match::from_slots(slots)
}

// 한 엔진의 옮긴 글과, 찾는 꼴마다 처음 쓸 때 만든 regex. 만들지 못하면 `None`
#[derive(Debug)]
struct Tier<R> {
    body: String,
    built: [OnceLock<Option<R>>; 3],
}

impl<R: Engine> Tier<R> {
    fn new(body: String) -> Tier<R> {
        Tier {
            body,
            built: [OnceLock::new(), OnceLock::new(), OnceLock::new()],
        }
    }

    fn get(&self, kind: Kind, flags: Flags) -> Option<&R> {
        self.built[kind as usize]
            .get_or_init(|| R::build(&kind.wrap(&self.body), flags).ok())
            .as_ref()
    }
}

/// 이 글을 돌릴 엔진.
enum Pick<'a> {
    Fast(&'a dyn Dyn),
    Exact(&'a py_re::Regex),
}

// [`Engine`] 의 객체 꼴(만드는 함수 빼고)
trait Dyn {
    fn matches(&self, text: &str) -> bool;
    fn captures_at(&self, text: &str, pos: usize) -> Option<Match>;
}

impl<R: Engine> Dyn for R {
    fn matches(&self, text: &str) -> bool {
        Engine::matches(self, text)
    }

    fn captures_at(&self, text: &str, pos: usize) -> Option<Match> {
        Engine::captures_at(self, text, pos)
    }
}

/// python 문법으로 적은 고정 패턴. 메서드와 결과는 [`py_re::Regex`] 와 같다.
#[derive(Debug)]
pub struct Regex {
    source: Box<str>,
    flags: Flags,
    groups: usize,
    uses: Uses,
    ascii: Tier<regex::bytes::Regex>,
    unicode: Tier<regex::Regex>,
    exact: OnceLock<py_re::Regex>,
}

impl Regex {
    /// python `re.compile(pattern)`. 옮기지 못하는 패턴이면 panic.
    pub fn new(pattern: &str) -> Regex {
        Regex::with_flags(pattern, Flags::NONE)
    }

    /// python `re.compile(pattern, flags)`. 옮기지 못하는 패턴이면 panic. regex 는 처음 쓸 때 만든다.
    pub fn with_flags(pattern: &str, flags: Flags) -> Regex {
        let (unicode, ascii) = match (
            translate(pattern, flags, false),
            translate(pattern, flags, true),
        ) {
            (Ok(u), Ok(a)) => (u, a),
            (Err(why), _) | (_, Err(why)) => {
                panic!("rx cannot take the pattern {pattern:?}: {why}")
            }
        };
        Regex {
            source: pattern.into(),
            flags,
            groups: unicode.groups,
            uses: unicode.uses,
            ascii: Tier::new(ascii.body),
            unicode: Tier::new(unicode.body),
            exact: OnceLock::new(),
        }
    }

    /// 두 regex crate 엔진과 py::re 를 지금 만들어 본다(시험에서 상수 패턴 확인용). 못 만들면 panic.
    pub fn check(&self) {
        for kind in [Kind::Search, Kind::Anchored, Kind::Full] {
            if let Err(e) = regex::bytes::Regex::build(&kind.wrap(&self.ascii.body), self.flags) {
                panic!("the ASCII engine cannot take {:?}: {e}", self.source);
            }
            if let Err(e) = regex::Regex::build(&kind.wrap(&self.unicode.body), self.flags) {
                panic!("regex crate cannot take {:?}: {e}", self.source);
            }
        }
        self.exact();
    }

    /// python `pattern.groups`: 잡는 괄호 수(0 번 빼고).
    pub fn groups(&self) -> usize {
        self.groups
    }

    /// python `pattern.search(text, pos)`. `pos` 는 바이트 위치(글자 경계)다. 앞 글은 `\b` 가 본다.
    pub fn search_from(&self, text: &str, pos: usize) -> Option<Match> {
        match self.pick(text, Kind::Search) {
            Pick::Fast(re) => re.captures_at(text, pos),
            Pick::Exact(py) => py.search_from(text, pos),
        }
    }

    /// python `pattern.search(text)`.
    pub fn search(&self, text: &str) -> Option<Match> {
        self.search_from(text, 0)
    }

    /// `search` 가 맞는가.
    pub fn is_match(&self, text: &str) -> bool {
        match self.pick(text, Kind::Search) {
            Pick::Fast(re) => re.matches(text),
            Pick::Exact(py) => py.is_match(text),
        }
    }

    /// python `pattern.fullmatch(text)`.
    pub fn fullmatch(&self, text: &str) -> Option<Match> {
        match self.pick(text, Kind::Full) {
            Pick::Fast(re) => re.captures_at(text, 0),
            Pick::Exact(py) => py.fullmatch(text),
        }
    }

    /// python `pattern.match(text)`: 맨 앞에서만, 끝은 어디든.
    pub fn match_start(&self, text: &str) -> Option<Match> {
        match self.pick(text, Kind::Anchored) {
            Pick::Fast(re) => re.captures_at(text, 0),
            Pick::Exact(py) => py.match_start(text),
        }
    }

    /// python `pattern.finditer(text)`: 겹치지 않는 일치들, 앞에서부터.
    pub fn find_iter(&self, text: &str) -> Vec<Match> {
        let re = match self.pick(text, Kind::Search) {
            Pick::Fast(re) => re,
            Pick::Exact(py) => return py.find_iter(text),
        };
        let mut out = Vec::new();
        let mut pos = 0;
        let mut after_empty = false;
        while pos <= text.len() {
            let Some(m) = re.captures_at(text, pos) else {
                break;
            };

            // After an empty match python wants a longer one at the same place
            let empty = m.start() == m.end();
            if after_empty && empty && m.start() == pos {
                if pos == text.len() {
                    break;
                }
                return self.exact().find_iter(text);
            }
            after_empty = empty;
            pos = m.end();
            out.push(m);
        }
        out
    }

    /// python `pattern.split(text)`. 잡는 괄호의 글은 끼워 넣지 않는다([`py_re::Regex::split`] 과 같다).
    pub fn split<'t>(&self, text: &'t str) -> Vec<&'t str> {
        let mut out = Vec::new();
        let mut last = 0;
        for m in self.find_iter(text) {
            out.push(&text[last..m.start()]);
            last = m.end();
        }
        out.push(&text[last..]);
        out
    }

    /// python `pattern.sub(f, text)`: 일치마다 `f` 가 낸 글로 바꾼다.
    pub fn replace_all(&self, text: &str, mut f: impl FnMut(&Match) -> String) -> String {
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

    /// 이 글의 [`Regex::find_iter`] 가 py::re 의 finditer 와 괄호마다 같은가(시험용, [`crate::testkit::assert_agree`]).
    ///
    /// 갈림 글자가 든 글은 늘 py::re 가 도니 참이다. 그 밖의 글에서 옮긴 패턴과 regex crate 가 python 과 같은지를 본다.
    pub fn agrees_with_py(&self, text: &str) -> bool {
        self.find_iter(text) == self.exact().find_iter(text)
    }

    // 이 글을 돌릴 엔진: ASCII 글은 ASCII 엔진, 갈림 글자가 든 글은 py::re, 나머지는 Unicode 엔진
    fn pick(&self, text: &str, kind: Kind) -> Pick<'_> {
        if self.diverges(text) {
            return Pick::Exact(self.exact());
        }
        if text.is_ascii()
            && let Some(re) = self.ascii.get(kind, self.flags)
        {
            return Pick::Fast(re);
        }
        match self.unicode.get(kind, self.flags) {
            Some(re) => Pick::Fast(re),
            None => panic!("regex crate cannot take {:?}", self.source),
        }
    }

    // 이 글에서 regex crate 가 python 과 다르게 볼 수 있는가
    fn diverges(&self, text: &str) -> bool {
        let u = self.uses;
        if u.dollar && text.ends_with('\n') {
            return true;
        }
        if text.is_ascii() || !(u.word || u.digit || u.icase) {
            return false;
        }

        // Characters outside ASCII the two engines read apart
        text.chars().filter(|c| !c.is_ascii()).any(|c| {
            let c = u32::from(c);
            (u.word && in_ranges(tables::WORD, c))
                || (u.digit && in_ranges(tables::DIGIT, c))
                || (u.icase && in_ranges(tables::CASE, c))
        })
    }

    fn exact(&self) -> &py_re::Regex {
        self.exact.get_or_init(|| {
            py_re::Regex::with_flags(&self.source, self.flags)
                .unwrap_or_else(|e| panic!("py::re cannot take {:?}: {e}", self.source))
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::py::text::is_space;
    use crate::py::unicode::{case_fixes, is_decimal, is_word, lower};

    // Does python IGNORECASE fold ASCII `a` and `c` (sre lower and `_casefix`)
    fn py_same_letter(a: char, c: char) -> bool {
        let lo = lower(u32::from(a));
        let got = lower(u32::from(c));
        got == lo || case_fixes(lo).contains(&got)
    }

    fn one(pattern: &str) -> regex::Regex {
        regex::Regex::new(&format!(r"\A(?:{pattern})\z")).unwrap()
    }

    // Ranges where the two engines differ over all code points
    fn differing() -> [Vec<(u32, u32)>; 4] {
        let (w, s, d) = (one(r"\w"), one(r"\s"), one(r"\d"));
        let letters: Vec<(char, regex::Regex)> =
            ('a'..='z').map(|a| (a, one(&format!("(?i){a}")))).collect();
        let any_letter = one("(?i)[a-z]");
        let mut out: [Vec<(u32, u32)>; 4] = Default::default();
        let mut buf = [0u8; 4];
        for code in 0..=0x10_FFFFu32 {
            let Some(c) = char::from_u32(code) else {
                continue;
            };
            let s1 = c.encode_utf8(&mut buf);
            let case_differs = !c.is_ascii() && {
                let py: Vec<char> = ('a'..='z').filter(|&a| py_same_letter(a, c)).collect();
                let rx: Vec<char> = if any_letter.is_match(s1) {
                    letters
                        .iter()
                        .filter(|(_, r)| r.is_match(s1))
                        .map(|(a, _)| *a)
                        .collect()
                } else {
                    Vec::new()
                };
                py != rx
            };
            let differs = [
                is_word(code) != w.is_match(s1),
                is_space(c) != s.is_match(s1),
                is_decimal(code) != d.is_match(s1),
                case_differs,
            ];
            for (table, d) in out.iter_mut().zip(differs) {
                if !d {
                    continue;
                }
                match table.last_mut() {
                    Some(last) if last.1 + 1 == code => last.1 = code,
                    _ => table.push((code, code)),
                }
            }
        }
        out
    }

    /// 갈림 표가 지금 두 엔진의 차이와 같다(Unicode 판이 바뀌면 실패한다, 다시 만드는 법은 tables.rs 머리).
    #[test]
    fn tables_are_current() {
        let [word, space, digit, case] = differing();
        assert_eq!(word, tables::WORD, "WORD");
        // translate adds these to every \s, so no guard table is needed
        assert_eq!(space, [(0x1c, 0x1f)], "SPACE");
        assert_eq!(digit, tables::DIGIT, "DIGIT");
        assert_eq!(case, tables::CASE, "CASE");

        // The ASCII part the fast check relies on: only the \x1c..\x1f spaces
        let ascii = |t: &[(u32, u32)]| t.iter().filter(|r| r.0 < 0x80).copied().collect::<Vec<_>>();
        assert!(ascii(tables::WORD).is_empty() && ascii(tables::DIGIT).is_empty());
        assert!(ascii(tables::CASE).is_empty());
    }

    /// 표를 Rust 글로 찍는다(`cargo test -p harness-hook rx::tests::print_tables -- --ignored --nocapture`).
    #[test]
    #[ignore]
    fn print_tables() {
        let names = ["WORD", "SPACE", "DIGIT", "CASE"];
        for (name, table) in names.iter().zip(differing()) {
            let body: Vec<String> = table
                .iter()
                .map(|(a, b)| format!("(0x{a:X}, 0x{b:X})"))
                .collect();
            println!("{name} ({} ranges): &[{}];", table.len(), body.join(", "));
        }
    }

    /// 서로게이트 자리표(U+10F800..)는 python 의 서로게이트처럼 \w, \s, \d 가 아니고 대소문자가 없다.
    #[test]
    fn placeholders_act_like_surrogates() {
        for code in [0x10_F800u32, 0x10_FC80, 0x10_FFFF] {
            let c = char::from_u32(code).unwrap().to_string();
            for p in [r"\w", r"\s", r"\d", "(?i)[a-z]"] {
                assert!(!one(p).is_match(&c), "{p} on U+{code:X}");
            }
            assert!(Regex::new(r"\W\S\D").is_match(&c.repeat(3)));
        }
    }

    // Results of both engines (a range per group)
    type Spans = Vec<Option<(usize, usize)>>;

    fn spans(m: Option<Match>, groups: usize) -> Option<Spans> {
        m.map(|m| (0..=groups).map(|i| m.group(i)).collect())
    }

    const PATTERNS: &[(&str, bool)] = &[
        (r"&&|\|\||[;|\n]", false),
        (r"[A-Za-z_][A-Za-z0-9_]*=\S*", false),
        (r"[\d.]+[smhd]?", false),
        (r"(?:^|[;&|\s(])([A-Za-z_]\w*)=(\S*)", false),
        (r"\$\{?([A-Za-z_]\w*)\}?", false),
        (r"-(?:\d+|(?:SIG)?[A-Z][A-Z0-9]+(?:[+-]\d+)?)", false),
        (r"\AExit code (\d+)", false),
        (r"(^|[;&|(\s])git(\s+-[Cc]\s+\S+)*\s+commit\b", false),
        (r"handover|checkpoint", true),
        (
            r"^\s*/(?:qwreey-sessions:)?(handover|checkpoint)\b|\b(handover|핸드오버|인계)\b",
            true,
        ),
        (
            r"core dumped|Segmentation fault|Bus error|Illegal instruction|Floating point exception|\bSIG(?:SEGV|ABRT|BUS|FPE|ILL|QUIT|TRAP|SYS)\b|signal: (?:3|4|5|6|7|8|11|31)\b",
            false,
        ),
        (r"\u2014|[\u00c0-\u024f]+|[가-힣]x", false),
        (r"^[\s\-/#*!]+", false),
        (r"`[^`]*`", false),
        (r"https?://\S+", false),
        (r"\S*/\S*|\S+\.\w{1,5}\b", false),
        (r"\b(?:previously|recently)\b", true),
        (r"description:[ \t]*(.*)$", false),
        (r"^\s*(`{3,}|~{3,})", false),
        (r"[가-힣]{2,}", false),
        ("(?m)^name\\s*=\\s*\"([^\"]+)\"", false),
        (r"\b[A-Z]{1,2}-\d{2,4}\b", false),
        (r"x{,2}y", false),
        (r"a{", false),
        (r"\w*", false),
        (r"(?m)^", false),
        (r"(?m)$", false),
        (r"$", false),
        (r"a|ab", false),
        (r"(a|ab)(c|bcd)(d*)$", false),
        (r"(?s)^---\s*\n(.*?)\n---", false),
        (r#"[^\s`'"()<>\[\]]+\.md\b"#, false),
        (r"^\s*(?:[-*>]\s*)?\**status\**\s*:", true),
        (r"[[]x", false),
        (r"\s+", false),
        (r"(?P<k>start|end)-replace(?P<rest>.*?)[ \t]*$", false),
        (r"\bR(?:6|15)\b", false),
        (r"\d+", false),
        (r"[\w./@-]+\.(?:py|ts)\b", false),
        (r"(?:--|//|#|/\*|\{/\*)\s*@dup-ok\b:?[ \t]*([^\n]*)", false),
        (r"\Z", false),
        (r"\bi\B", true),
        (r"[^a-z]+", true),
        (r"x*", false),
        (r"\W+", false),
    ];

    const HAYSTACKS: &[&str] = &[
        "",
        "a",
        "git commit -m x",
        "cd a && git -C /x commit",
        "a=1 b=$X ${Y} && c | d;e\nf",
        "previously, recently",
        "이전에 previously 한국어 단어",
        "\u{2714}\u{fe0f}previously ok",
        "x\u{b2}previously",
        "a.py\u{b2}, b.md x/y.ts",
        "status: done\n",
        "name = \"pkg\"\nname=\"x\"\n",
        "\u{1c}a b\u{1d}",
        "Exit code 137\nmore",
        "kill -9 -SIGTERM -HUP+1",
        "D-12 AB-1234 ABC-12 R6 R15x",
        "ab cd\n",
        "xxy {a} a{",
        "--- \n\nkey: v\n---\nbody",
        "\u{130}\u{131} \u{17f}\u{212a} STATUS: I",
        "https://x.y/z a/b.c",
        "`code` and ```\n~~~",
        "\u{10fc80}word\u{10f800}",
        "start-replace rest  \nend-replace",
        "# @dup-ok: reason here\n",
        "aaa xx",
        "a\u{301}b \u{200d}c",
    ];

    /// 고정 패턴 표본이 모든 표본 글에서 py::re 와 같은 일치를 낸다(search, 위치 search, match, fullmatch, finditer, split).
    #[test]
    fn same_as_py_re() {
        for &(p, icase) in PATTERNS {
            let flags = if icase {
                Flags::IGNORECASE
            } else {
                Flags::NONE
            };
            let rx = Regex::with_flags(p, flags);
            rx.check();
            let py = py_re::Regex::with_flags(p, flags).unwrap();
            let g = py.groups();
            assert_eq!(rx.groups(), g, "{p}");
            for &h in HAYSTACKS {
                let at = format!("{p:?} on {h:?}");
                assert_eq!(
                    spans(rx.search(h), g),
                    spans(py.search(h), g),
                    "search {at}"
                );
                assert_eq!(rx.is_match(h), py.is_match(h), "is_match {at}");
                assert_eq!(
                    spans(rx.match_start(h), g),
                    spans(py.match_start(h), g),
                    "match {at}"
                );
                assert_eq!(
                    spans(rx.fullmatch(h), g),
                    spans(py.fullmatch(h), g),
                    "fullmatch {at}"
                );
                let all =
                    |v: Vec<Match>| v.into_iter().map(|m| spans(Some(m), g)).collect::<Vec<_>>();
                assert_eq!(all(rx.find_iter(h)), all(py.find_iter(h)), "finditer {at}");
                assert_eq!(rx.split(h), py.split(h), "split {at}");
                for pos in (0..=h.len()).filter(|&k| h.is_char_boundary(k)).step_by(3) {
                    assert_eq!(
                        spans(rx.search_from(h, pos), g),
                        spans(py.search_from(h, pos), g),
                        "search at {pos} {at}"
                    );
                }
            }
        }
    }

    /// 갈림 검사가 regex crate 만으로는 python 과 달라질 글을 py::re 로 넘긴다.
    #[test]
    fn guard_catches_known_differences() {
        for (p, flags, h) in [
            // U+FE0F is a combining mark: regex calls it a word char, python does not
            (r"\bprev", Flags::NONE, "\u{2714}\u{fe0f}prev"),
            // Superscript digits are word chars only in python
            (r"y\b", Flags::NONE, "py\u{b2}"),
            // python `$` also matches before a final newline
            (r"a$", Flags::NONE, "a\n"),
            // python IGNORECASE folds dotless i and dotted I to i
            ("i", Flags::IGNORECASE, "\u{131}"),
        ] {
            // The pattern as is in the regex crate disagrees with python
            let rx = Regex::with_flags(p, flags);
            let py = py_re::Regex::with_flags(p, flags).unwrap();
            let naive = regex::Regex::build(p, flags).unwrap();
            assert_ne!(naive.is_match(h), py.is_match(h), "{p:?} {h:?}");

            // rx hands the text to py::re
            assert!(rx.diverges(h), "{p:?} {h:?}");
            assert_eq!(rx.is_match(h), py.is_match(h), "{p:?} {h:?}");
        }

        // Plain text keeps the fast engines
        assert!(!Regex::new(r"\bprev\s$").diverges("이전 prev 값"));

        // U+001C, which python `\s` takes, is accepted by the translated text
        for h in ["\u{1c}", "\u{1c}\u{d55c}"] {
            assert!(!Regex::new(r"\s").diverges(h));
            assert!(Regex::new(r"\s").is_match(h) && !Regex::new(r"\S\S").is_match(h));
        }
    }

    /// 패턴마다 처음 쓸 때 드는 값(만들기와 짧은 글 한 번)을 엔진별로 찍는다(판정은 하지 않는다).
    /// `cargo test --release -p harness-hook rx::tests::first_use_cost -- --ignored --nocapture`
    #[test]
    #[ignore]
    fn first_use_cost() {
        let time = |f: &dyn Fn()| {
            let n = 200;
            let started = std::time::Instant::now();
            for _ in 0..n {
                f();
            }
            started.elapsed().as_secs_f64() * 1e6 / f64::from(n)
        };
        for &(p, icase) in PATTERNS {
            let flags = if icase {
                Flags::IGNORECASE
            } else {
                Flags::NONE
            };
            let ascii = time(&|| {
                assert!(
                    Regex::with_flags(p, flags)
                        .ascii
                        .get(Kind::Search, flags)
                        .is_some()
                        || true
                )
            });
            let unicode = time(&|| {
                let _ = Regex::with_flags(p, flags).unicode.get(Kind::Search, flags);
            });
            let py = time(&|| {
                let _ = py_re::Regex::with_flags(p, flags)
                    .unwrap()
                    .is_match("git status && ls -la");
            });
            println!("{ascii:8.1} us ascii {unicode:8.1} us unicode {py:8.1} us py::re  {p}");
        }
    }

    /// 빈 일치 바로 뒤에서 python 은 같은 자리의 더 긴 일치를 찾는다. regex crate 가 못 하는 자리는 py::re 가 돈다.
    #[test]
    fn empty_matches_iterate_like_python() {
        // python: re.findall(r"^|\w+", "foo bar") == ["", "foo", "bar"]
        let rx = Regex::new(r"^|\w+");
        let got: Vec<(usize, usize)> = rx
            .find_iter("foo bar")
            .iter()
            .map(|m| (m.start(), m.end()))
            .collect();
        assert_eq!(got, [(0, 0), (0, 3), (4, 7)]);

        // python: [m.span() for m in re.finditer(r"\w*", "ab cd")]
        let got: Vec<(usize, usize)> = Regex::new(r"\w*")
            .find_iter("ab cd")
            .iter()
            .map(|m| (m.start(), m.end()))
            .collect();
        assert_eq!(got, [(0, 2), (2, 2), (3, 5), (5, 5)]);
    }
}
