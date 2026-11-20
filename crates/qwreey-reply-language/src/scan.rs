//! python `URL`, `PATHLIKE` 정규식의 일치를 선형 시간에(python `url_spans`, `path_spans`). 범위는 바이트 위치다.
//!
//! why not 정규식: 두 패턴은 긴 줄(공백 없는 글, `[\w@.~/-]` 글자 줄)의 시작 자리마다 줄 끝까지 다시 훑는다. 그래서 python re 와
//! py::re 는 제곱 시간이고("x."*20000 에 python 6 초, 훅 제한은 5 초), regex crate 판도 앞 보기를 흉내 내느라 자리마다 다시 찾아
//! 10 초를 넘겼다. 여기서는 오른쪽부터 한 번 센 줄 끝으로 자리마다 상수 시간에 판정한다. 글자 판정은 python 의 것
//! (`\w` 는 [`is_word`], `\s` 는 [`is_space`], re.I 의 `[a-z]` 는 ASCII 글자와 네 글자)이라 엔진 사이의 갈림 글자도 없다.
//! python 판도 긴 줄에서는 같은 훑기를 쓴다. 두 판과 정규식이 같은 일치를 내는지는 이 파일과 python 시험이 무작위 글로 본다.

use harness_hook::py::text::is_space;
use harness_hook::py::unicode::is_word;

// re.I 의 [a-z]: python 은 이 네 글자도 ASCII 글자와 같게 본다
const ICASE_EXTRA: [char; 4] = ['\u{130}', '\u{131}', '\u{17f}', '\u{212a}'];

fn icase_letter(c: char) -> bool {
    c.is_ascii_alphabetic() || ICASE_EXTRA.contains(&c)
}

// re.I 의 [a-z0-9+.-]
fn scheme_char(c: char) -> bool {
    icase_letter(c) || c.is_ascii_digit() || matches!(c, '+' | '.' | '-')
}

fn word(c: char) -> bool {
    is_word(u32::from(c))
}

// [\w@.-]
fn segment_char(c: char) -> bool {
    word(c) || matches!(c, '@' | '.' | '-')
}

// [\w-]
fn name_char(c: char) -> bool {
    word(c) || c == '-'
}

/// 글자와 그 바이트 위치. python 의 글자 위치로 판정하고 바이트 범위로 돌려준다.
struct Chars {
    chars: Vec<char>,
    /// 글자 `i` 의 바이트 위치. 끝에 글 길이가 하나 더 있다.
    at: Vec<usize>,
}

impl Chars {
    fn new(text: &str) -> Chars {
        let (at, chars): (Vec<usize>, Vec<char>) = text.char_indices().unzip();
        let mut at = at;
        at.push(text.len());
        Chars { chars, at }
    }

    fn len(&self) -> usize {
        self.chars.len()
    }

    fn bytes(&self, (start, end): (usize, usize)) -> (usize, usize) {
        (self.at[start], self.at[end])
    }
}

// 자리마다 그 자리에서 시작하는 `member` 글자 줄의 끝(그 자리 글자가 아니면 그 자리). 끝 자리 n 도 있다
fn run_ends(chars: &[char], member: fn(char) -> bool) -> Vec<usize> {
    let n = chars.len();
    let mut ends = vec![n; n + 1];
    for i in (0..n).rev() {
        ends[i] = if member(chars[i]) { ends[i + 1] } else { i };
    }
    ends
}

/// python `URL.finditer(text)`(`\b[a-z][a-z0-9+.-]*://\S+|\bwww\.\S+`, re.I) 의 범위들.
///
/// 일치는 공백 없는 줄 하나 안에서 처음 맞는 자리부터 그 줄 끝까지다(`\S+` 가 줄 끝까지 먹는다). 그래서 줄마다 많아야 하나다.
pub fn url_spans(text: &str) -> Vec<(usize, usize)> {
    let t = Chars::new(text);
    let n = t.len();
    let scheme_end = run_ends(&t.chars, scheme_char);

    // Each whitespace-free run [start, end)
    let mut out = Vec::new();
    let mut start = 0;
    while start < n {
        if is_space(t.chars[start]) {
            start += 1;
            continue;
        }
        let end = (start..n).find(|&i| is_space(t.chars[i])).unwrap_or(n);
        if let Some(s) = (start..end).find(|&s| url_at(&t.chars, &scheme_end, s, end)) {
            out.push(t.bytes((s, end)));
        }
        start = end;
    }
    out
}

// 공백 없는 줄 [.., end) 의 자리 s 에서 URL 의 두 갈래 가운데 하나가 맞는가
fn url_at(chars: &[char], scheme_end: &[usize], s: usize, end: usize) -> bool {
    // \b before a letter: the previous char is not a word char (whitespace never is)
    let c = chars[s];
    if !word(c) || (s > 0 && word(chars[s - 1])) {
        return false;
    }

    // ':' 는 scheme 글자가 아니라 "://" 는 scheme 줄 바로 뒤에만 올 수 있다
    let r = scheme_end[s + 1];
    if icase_letter(c) && chars[r..].starts_with(&[':', '/', '/']) && r + 3 < end {
        return true;
    }
    s + 4 < end && chars[s..s + 3].iter().all(|&w| matches!(w, 'w' | 'W')) && chars[s + 3] == '.'
}

/// python `PATHLIKE.finditer(text)` 의 범위들: 경로(`a/b`, `./x/`)와 확장자 붙은 이름(`main.rs`).
///
/// 패턴은 `(?<![\w])(?:[~.]{0,2}/)?[\w@.-]+(?:/[\w@.-]+)+/?|[\w-]+\.(?:[a-z]{1,5})\b`(re.I)다. 한 자리에서는 경로 갈래가 먼저다.
pub fn pathlike_spans(text: &str) -> Vec<(usize, usize)> {
    let t = Chars::new(text);
    let path = Path::new(&t.chars);

    // Leftmost match, the path branch first at one start
    let mut out = Vec::new();
    let mut s = 0;
    while s < t.len() {
        match path.dirs_at(s).or_else(|| path.file_at(s)) {
            Some(end) => {
                out.push(t.bytes((s, end)));
                s = end;
            }
            None => s += 1,
        }
    }
    out
}

/// [`pathlike_spans`] 가 자리마다 보는 줄 끝들(오른쪽부터 한 번 센다).
struct Path<'a> {
    chars: &'a [char],
    /// 글자마다 단어 글자인가. 끝에 거짓이 하나 더 있다(글 끝은 `\b` 에서 단어 글자가 아니다).
    word: Vec<bool>,
    segment_end: Vec<usize>,
    name_end: Vec<usize>,
    letter_end: Vec<usize>,
    /// `[\w@.-]+(?:/[\w@.-]+)*` 를 가장 길게 이은 끝(segment 글자 자리만 뜻이 있다).
    chain_end: Vec<usize>,
}

impl<'a> Path<'a> {
    fn new(chars: &'a [char]) -> Path<'a> {
        let n = chars.len();
        let mut word_of: Vec<bool> = chars.iter().map(|&c| word(c)).collect();
        word_of.push(false);
        let segment_end = run_ends(chars, segment_char);

        // Chain ends, right to left
        let mut chain_end = vec![0; n + 1];
        for i in (0..n).rev() {
            let r = segment_end[i];
            if r > i {
                chain_end[i] = if slash_then_segment(chars, &segment_end, r) {
                    chain_end[r + 1]
                } else {
                    r
                };
            }
        }

        Path {
            chars,
            word: word_of,
            segment_end,
            name_end: run_ends(chars, name_char),
            letter_end: run_ends(chars, icase_letter),
            chain_end,
        }
    }

    // `(?<![\w])(?:[~.]{0,2}/)?` 다음 `[\w@.-]+(?:/[\w@.-]+)+/?` 의 끝
    fn dirs_at(&self, s: usize) -> Option<usize> {
        if s > 0 && self.word[s - 1] {
            return None;
        }

        // 가장 긴 [~.] 줄(3 자 이상이면 둘째 뒤가 [~.] 라) 뒤에만 '/' 가 올 수 있다
        let n = self.chars.len();
        let prefix = (0..3)
            .take_while(|&k| s + k < n && matches!(self.chars[s + k], '~' | '.'))
            .count();
        if prefix <= 2
            && s + prefix + 1 < n
            && self.chars[s + prefix] == '/'
            && let Some(end) = self.dirs_from(s + prefix + 1)
        {
            return Some(end);
        }
        self.dirs_from(s)
    }

    // `[\w@.-]+(?:/[\w@.-]+)+/?` 의 끝. '/' 는 [\w@.-] 가 아니라 되돌려 줄여도 맞는 일이 없다
    fn dirs_from(&self, q: usize) -> Option<usize> {
        let r = self.segment_end[q];
        if r == q || !slash_then_segment(self.chars, &self.segment_end, r) {
            return None;
        }
        let end = self.chain_end[q];
        Some(if self.chars.get(end) == Some(&'/') {
            end + 1
        } else {
            end
        })
    }

    // `[\w-]+\.(?:[a-z]{1,5})\b`: 이름 줄 전체 뒤의 '.', 그 뒤 글자 줄 전체가 1..5 자이고 다음이 단어 글자가 아닐 때만
    fn file_at(&self, s: usize) -> Option<usize> {
        let f = self.name_end[s];
        if f == s || self.chars.get(f) != Some(&'.') {
            return None;
        }
        let end = self.letter_end[f + 1];
        ((1..=5).contains(&(end - f - 1)) && !self.word[end]).then_some(end)
    }
}

// 자리 r 이 '/' 이고 그 뒤에 [\w@.-] 글자가 있는가
fn slash_then_segment(chars: &[char], segment_end: &[usize], r: usize) -> bool {
    r + 1 < chars.len() && chars[r] == '/' && segment_end[r + 1] > r + 1
}

#[cfg(test)]
mod tests {
    use std::time::{Duration, Instant};

    use harness_hook::py::re::{Flags, Regex as PyRegex};
    use harness_hook::testkit::corpus;

    use super::*;

    const PY_URL: &str = r"\b[a-z][a-z0-9+.-]*://\S+|\bwww\.\S+";
    const PY_PATHLIKE: &str =
        r"(?<![\w])(?:[~.]{0,2}/)?[\w@.-]+(?:/[\w@.-]+)+/?|[\w-]+\.(?:[a-z]{1,5})\b";

    const PIECES: &[&str] = &[
        "a",
        "x",
        "Z",
        "_",
        "9",
        "\u{e9}",
        "\u{130}",
        "\u{131}",
        "\u{17f}",
        "\u{212a}",
        "\u{b2}",
        "\u{903}",
        "\u{d55c}",
        "\u{10f800}",
        ".",
        "-",
        "@",
        "~",
        "/",
        ":",
        "://",
        "+",
        " ",
        "\n",
        "\u{1c}",
        "\u{3000}",
        "www",
        "WwW.",
        "rs",
        "html",
        "abcdef",
        "http",
        "a/b",
        "./",
        "../",
        "~/",
        ".~/",
        "~~/",
        "...",
        "//",
        "`",
        "!",
        "\u{a0}",
        "x.",
        "a-",
        "foo.rs",
        "K",
        "s",
    ];

    fn py_spans(pattern: &str, text: &str) -> Vec<(usize, usize)> {
        PyRegex::with_flags(pattern, Flags::IGNORECASE)
            .expect("python pattern")
            .find_iter(text)
            .iter()
            .map(|m| (m.start(), m.end()))
            .collect()
    }

    /// 두 훑기가 python 패턴(py::re)과 같은 일치를 낸다(만든 글 3000 개와 그것을 세 번 이은 긴 글).
    #[test]
    fn scanners_match_the_python_patterns() {
        for piece_text in corpus(PIECES, 3000) {
            for text in [piece_text.clone(), piece_text.repeat(3)] {
                assert_eq!(url_spans(&text), py_spans(PY_URL, &text), "URL {text:?}");
                assert_eq!(
                    pathlike_spans(&text),
                    py_spans(PY_PATHLIKE, &text),
                    "PATHLIKE {text:?}"
                );
            }
        }
    }

    // python 글자 집합 패턴, 그 플래그, 그것을 손으로 적은 판정
    type Class = (&'static str, Flags, fn(char) -> bool);

    /// 손으로 적은 글자 판정이 모든 코드 포인트에서 python 패턴(py::re)의 판정과 같다.
    #[test]
    fn char_classes_follow_python() {
        let classes: [Class; 5] = [
            ("[a-z]", Flags::IGNORECASE, icase_letter),
            ("[a-z0-9+.-]", Flags::IGNORECASE, scheme_char),
            // url_at reads "www" as w or W only
            ("w", Flags::IGNORECASE, |c| matches!(c, 'w' | 'W')),
            // re.I leaves \w as is in python (all code points checked there); py::re folds with Rust's newer case table (U+A7D2)
            (r"[\w@.-]", Flags::NONE, segment_char),
            (r"[\w-]", Flags::NONE, name_char),
        ];
        for (pattern, flags, ours) in classes {
            let py = PyRegex::with_flags(pattern, flags).expect("python pattern");
            for c in (0..=0x10_FFFFu32).filter_map(char::from_u32) {
                let s = c.to_string();
                assert_eq!(
                    ours(c),
                    py.fullmatch(&s).is_some(),
                    "{pattern} U+{:04X}",
                    u32::from(c)
                );
            }
        }
    }

    /// 정규식이 제곱 시간이던 글(python 3 초 넘게, 고치기 전 Rust 판 10 초 넘게)을 두 훑기가 debug 빌드에서도 1 초 안에 본다.
    #[test]
    fn long_runs_take_linear_time() {
        let texts = [
            "x.".repeat(20000),
            "a-".repeat(20000),
            "http".repeat(10000),
            format!("{} a/b", "see foo.rs and ".repeat(5000)),
            "x.foo".repeat(8000),
            "~./".repeat(13000),
        ];

        for text in &texts {
            // Time both scanners on one text
            let started = Instant::now();
            std::hint::black_box((url_spans(text), pathlike_spans(text)));
            let took = started.elapsed();

            assert!(
                took < Duration::from_secs(1),
                "{took:?} on {:?}...",
                &text[..12]
            );
        }
    }
}
