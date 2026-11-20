//! python `re` 의 부분 집합: 같은 패턴 글을 같은 뜻으로 읽고, 같은 글에 같은 자리에서 맞는다.
//!
//! why not regex, fancy-regex: 훅은 사용자가 쓴 python 정규식(pgrep 패턴 등)을 python 과 똑같이 판정해야 한다.
//! 두 crate 는 문법(`[[:alpha:]]`, `\Z`, 모르는 escape, `{` 를 글자로 읽는 규칙), 오류가 나는 패턴, `\w` 와 IGNORECASE 의
//! Unicode 규칙이 python 과 달라 같은 패턴의 판정이 갈린다. 여기서는 python `re._parser` 의 읽는 순서와 sre 의 맞추는
//! 규칙(되돌아가며 찾기)을 그대로 옮겼다.
//!
//! 옮긴 것: 글자, `.`, `[...]`, `\d \w \s \b \A \Z` 와 반대, `^ $`, 갈래, 괄호(잡기, 묶음, 이름), 되풀이(`* + ? {m,n}`, 게으른 꼴),
//! 소유 되풀이, 원자 괄호, 앞뒤 보기, 괄호 참조, 맨 앞 인라인 플래그 `(?i) (?m) (?s)`, 플래그 IGNORECASE, MULTILINE, DOTALL.
//! 옮기지 않은 것([`Error::Unsupported`]): 조건 괄호, 범위 플래그, `(?a)`, `(?x)`, `\N{...}`,
//! lookbehind 안의 괄호 참조, 1000 보다 큰 되풀이 수.

mod ast;
mod class;
mod compile;
mod parse;
mod vm;

use compile::Program;

/// python 플래그(`re.I`, `re.M`, `re.S`).
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct Flags {
    pub ignore_case: bool,
    pub multiline: bool,
    pub dotall: bool,
}

impl Flags {
    /// 플래그 없음.
    pub const NONE: Flags = Flags {
        ignore_case: false,
        multiline: false,
        dotall: false,
    };
    /// `re.IGNORECASE`.
    pub const IGNORECASE: Flags = Flags {
        ignore_case: true,
        multiline: false,
        dotall: false,
    };
}

/// 패턴을 쓸 수 없는 이유.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Error {
    /// python 이 `re.error` 를 내는 패턴.
    Syntax(String),
    /// python 이 `OverflowError` 를 내는 패턴(되풀이 수가 2^32-1 이상). `re.error` 를 잡는 코드도 이것은 잡지 못한다.
    Overflow,
    /// python 은 읽지만 여기서는 옮기지 않은 문법.
    Unsupported(&'static str),
}

impl std::fmt::Display for Error {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            Error::Syntax(msg) => write!(f, "re.error: {msg}"),
            Error::Overflow => f.write_str("OverflowError: the repetition number is too large"),
            Error::Unsupported(what) => write!(f, "not supported here: {what}"),
        }
    }
}

impl std::error::Error for Error {}

/// 읽어 둔 패턴(python `re.compile` 의 결과).
#[derive(Clone, Debug)]
pub struct Regex {
    prog: Program,
}

/// 일치 하나. 위치는 바이트 단위다(글을 그대로 자를 수 있다).
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Match {
    slots: Vec<Option<usize>>,
}

impl Match {
    /// 일치의 시작.
    pub fn start(&self) -> usize {
        self.slots[0].expect("a match has group 0")
    }

    /// 일치의 끝.
    pub fn end(&self) -> usize {
        self.slots[1].expect("a match has group 0")
    }

    /// 괄호 `i` 가 잡은 범위. 맞지 않은 괄호는 `None`(python `m.group(i)` 가 None).
    pub fn group(&self, i: usize) -> Option<(usize, usize)> {
        Some((
            *self.slots.get(2 * i)?.as_ref()?,
            (*self.slots.get(2 * i + 1)?)?,
        ))
    }

    /// 괄호 `i` 가 잡은 글.
    pub fn text<'t>(&self, text: &'t str, i: usize) -> Option<&'t str> {
        self.group(i).map(|(a, b)| &text[a..b])
    }
}

impl Regex {
    /// python `re.compile(pattern)`.
    pub fn new(pattern: &str) -> Result<Regex, Error> {
        Regex::with_flags(pattern, Flags::NONE)
    }

    /// python `re.compile(pattern, flags)`.
    pub fn with_flags(pattern: &str, flags: Flags) -> Result<Regex, Error> {
        let parsed = parse::parse(pattern, flags)?;
        Ok(Regex {
            prog: compile::compile(&parsed)?,
        })
    }

    /// python `pattern.search(text, pos)`. `pos` 는 바이트 위치(글자 경계)다. 앞 글은 lookbehind 와 `\b` 가 본다.
    pub fn search_from(&self, text: &str, pos: usize) -> Option<Match> {
        vm::search(&self.prog, text, pos, vm::Mode::Search)
    }

    /// python `pattern.search(text)`.
    pub fn search(&self, text: &str) -> Option<Match> {
        self.search_from(text, 0)
    }

    /// `search` 가 맞는가.
    pub fn is_match(&self, text: &str) -> bool {
        self.search(text).is_some()
    }

    /// python `pattern.fullmatch(text)`.
    pub fn fullmatch(&self, text: &str) -> Option<Match> {
        vm::search(&self.prog, text, 0, vm::Mode::Full)
    }

    /// python `pattern.match(text)`: 맨 앞에서만, 끝은 어디든.
    pub fn match_start(&self, text: &str) -> Option<Match> {
        vm::match_at(&self.prog, text, 0)
    }

    /// python `pattern.finditer(text)`: 겹치지 않는 일치들, 앞에서부터.
    pub fn find_iter(&self, text: &str) -> Vec<Match> {
        let mut out = Vec::new();
        let mut pos = 0;
        let mut mode = vm::Mode::Search;
        while pos <= text.len() {
            let Some(m) = vm::search(&self.prog, text, pos, mode) else {
                break;
            };

            // 빈 일치 다음은 같은 자리의 빈 일치를 건너뛴다
            pos = m.end();
            mode = if m.end() == m.start() {
                vm::Mode::SearchAdvance
            } else {
                vm::Mode::Search
            };
            out.push(m);
        }
        out
    }

    /// python `pattern.split(text)`. 잡는 괄호가 있는 패턴은 python 이 그 글도 끼워 넣지만 여기서는 넣지 않는다.
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
}

/// python `re.escape(text)`: 정규식 특수 글자와 공백 앞에 `\`.
pub fn escape(text: &str) -> String {
    const SPECIAL: &str = "()[]{}?*+-|^$\\.&~# \t\n\r\u{b}\u{c}";
    let mut out = String::with_capacity(text.len());
    for c in text.chars() {
        if SPECIAL.contains(c) {
            out.push('\\');
        }
        out.push(c);
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn found(pattern: &str, text: &str) -> bool {
        Regex::new(pattern).unwrap().is_match(text)
    }

    #[test]
    fn basic_matching() {
        assert!(found("a.c", "xabc"));
        assert!(!found("^b", "ab"));
        assert!(found("(?<![A-Za-z])bench", "run-bench"));
        assert!(!found("(?<![A-Za-z])bench", "xbench"));
        assert!(found(r"perf(?:orm)?(?![A-Za-z])", "perform."));
        assert!(found(r"(a|ab)(c|bcd)(d*)$", "abcd"));
        assert!(found(r"(\w+) \1", "hey hey"));
        assert!(found("[t]est", "a test"));
        assert!(found("x{,2}y", "xxy"));
        assert!(found("a{", "a{"));
        assert!(found(r"(a*)*b", "aab"));
        assert!(Regex::new("a|ab").unwrap().fullmatch("ab").is_some());
    }

    #[test]
    fn ignore_case_follows_python() {
        let re = Regex::with_flags("stress", Flags::IGNORECASE).unwrap();
        assert!(re.is_match("STRE\u{17f}S"));
        let re = Regex::with_flags("(?<![A-Za-z])kit", Flags::IGNORECASE).unwrap();
        assert!(!re.is_match("\u{212a}kit"));
    }

    #[test]
    fn errors_follow_python() {
        let err = |p: &str| Regex::new(p).unwrap_err();
        assert!(matches!(err("*a"), Error::Syntax(_)));
        assert!(matches!(err("a**"), Error::Syntax(_)));
        assert!(matches!(err("(a"), Error::Syntax(_)));
        assert!(matches!(err("a)"), Error::Syntax(_)));
        assert!(matches!(err(r"\q"), Error::Syntax(_)));
        assert!(matches!(err("(?<=a+)b"), Error::Syntax(_)));
        assert!(matches!(err("a{99999999999}"), Error::Overflow));
        assert!(matches!(err("(?(1)a|b)"), Error::Unsupported(_)));
        assert!(!found("^c++$", "cc+") && found("^c++$", "cc"));
        assert!(!found("(?>a*)a", "aaa") && found("(?>a|ab)c", "ac"));
        assert!(Regex::new("[[:alpha:]]").is_ok());
    }

    #[test]
    fn iterates_splits_and_escapes() {
        let re = Regex::new(r"&&|\|\||[;|\n]").unwrap();
        assert_eq!(re.split("a && b | c;d"), vec!["a ", " b ", " c", "d"]);
        let re = Regex::new(r"\$\{?([A-Za-z_]\w*)\}?").unwrap();
        assert_eq!(
            re.replace_all("$A-${B}", |m| format!(
                "<{}>",
                m.text("$A-${B}", 1).unwrap()
            )),
            "<A>-<B>"
        );
        assert_eq!(escape("a.b-c d"), r"a\.b\-c\ d");
    }
}
