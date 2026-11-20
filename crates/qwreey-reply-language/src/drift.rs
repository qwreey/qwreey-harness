//! 답변 언어 이탈 판정(python `strip_text`, `drift_ratio`, `is_drift`).
//!
//! 코드, URL, 경로를 뗀 글에서 목표 문자 체계 글자와 라틴 글자를 센다. 목표 비율이 0.25 미만이면서 라틴 글자가 20자
//! 이상이면 이탈이다(한글 프롬프트에 영어로 답한 턴과 아닌 턴이 이 문턱에서 깨끗이 갈렸다).

use std::sync::LazyLock;

use harness_hook::py::re::{Flags, Regex as PyRegex};
use harness_hook::py::text::strip;
use regex::{Regex, RegexBuilder};

use crate::fixed_re::{Fixed, divergent};
use crate::language::Script;

const MIN_LATIN: usize = 20;
const THRESHOLD: f64 = 0.25;
const NO_RESPONSE: &str = "No response requested.";

const DOTALL: Flags = Flags {
    ignore_case: false,
    multiline: false,
    dotall: true,
};
const IGNORECASE_DOTALL: Flags = Flags {
    ignore_case: true,
    multiline: false,
    dotall: true,
};

// python \Z 는 regex 의 \z 다
static FENCE: LazyLock<Fixed> = LazyLock::new(|| {
    Fixed::with_rust(
        r"```.*?(?:```|\Z)|~~~.*?(?:~~~|\Z)",
        r"```.*?(?:```|\z)|~~~.*?(?:~~~|\z)",
        DOTALL,
    )
});
static INLINE: LazyLock<Fixed> = LazyLock::new(|| Fixed::new(r"`[^`\n]*`"));
static URL: LazyLock<Fixed> =
    LazyLock::new(|| Fixed::with_flags(r"\b[a-z][a-z0-9+.-]*://\S+|\bwww\.\S+", Flags::IGNORECASE));
/// 붙여 넣은 블록(python `PASTED`). 괄호 참조 `</\1>` 는 regex 판에서 태그 이름마다의 갈래로 펼쳤다(같은 순서).
pub static PASTED: LazyLock<Fixed> = LazyLock::new(|| {
    Fixed::with_rust(
        r"<(pasted_content|pasted_text|paste)[^>]*>.*?(?:</\1>|\Z)",
        concat!(
            r"<pasted_content[^>]*>.*?(?:</pasted_content>|\z)",
            r"|<pasted_text[^>]*>.*?(?:</pasted_text>|\z)",
            r"|<paste[^>]*>.*?(?:</paste>|\z)"
        ),
        IGNORECASE_DOTALL,
    )
});

/// python `PATHLIKE`(re.I). 첫 갈래의 앞 보기 `(?<![\w])` 는 [`pathlike_spans`] 가 맡는다.
const PY_PATHLIKE: &str =
    r"(?<![\w])(?:[~.]{0,2}/)?[\w@.-]+(?:/[\w@.-]+)+/?|[\w-]+\.(?:[a-z]{1,5})\b";

fn ignore_case(pattern: &str) -> Regex {
    RegexBuilder::new(pattern)
        .case_insensitive(true)
        .build()
        .expect("built-in pattern")
}

static PATH_DIRS: LazyLock<Regex> =
    LazyLock::new(|| ignore_case(r"(?:[~.]{0,2}/)?[\w@.-]+(?:/[\w@.-]+)+/?"));
static PATH_FILE: LazyLock<Regex> = LazyLock::new(|| ignore_case(r"[\w-]+\.(?:[a-z]{1,5})\b"));
static PATHLIKE_PY: LazyLock<PyRegex> =
    LazyLock::new(|| PyRegex::with_flags(PY_PATHLIKE, Flags::IGNORECASE).expect("python pattern"));

/// python `PATHLIKE.finditer(text)` 의 범위: 경로(`a/b`, `./x/`)와 확장자 붙은 이름(`main.rs`).
///
/// 경로 갈래는 앞 글자가 단어 글자인 자리에서 시작하지 않는다. 같은 자리에서는 경로 갈래가 먼저다(python 의 갈래 순서).
pub fn pathlike_spans(text: &str) -> Vec<(usize, usize)> {
    // Chars the engines read differently: python's pattern decides
    if divergent(text) {
        return PATHLIKE_PY
            .find_iter(text)
            .iter()
            .map(|m| (m.start(), m.end()))
            .collect();
    }

    // Leftmost of the two branches; a tie goes to the path branch
    let mut out = Vec::new();
    let mut pos = 0;
    while pos <= text.len() {
        let dirs = first_dirs_match(text, pos);
        let file = PATH_FILE.find_at(text, pos).map(|m| (m.start(), m.end()));
        let next = match (dirs, file) {
            (Some(d), Some(f)) => Some(if d.0 <= f.0 { d } else { f }),
            (d, f) => d.or(f),
        };
        let Some((start, end)) = next else { break };
        out.push((start, end));
        pos = end;
    }
    out
}

// 앞 글자가 단어 글자가 아닌 첫 경로 일치(python 의 앞 보기). 갈리는 글자가 없는 글이라 regex 의 \w 로 본다
fn first_dirs_match(text: &str, mut pos: usize) -> Option<(usize, usize)> {
    loop {
        let m = PATH_DIRS.find_at(text, pos)?;
        let before = text[..m.start()].chars().next_back();
        if !before.is_some_and(regex_syntax::is_word_character) {
            return Some((m.start(), m.end()));
        }
        pos = m.start() + text[m.start()..].chars().next().map_or(1, char::len_utf8);
    }
}

/// python `strip_text(text)`: 코드 블록, 인라인 코드, URL, 경로를 공백 하나로 바꾼다.
pub fn strip_text(text: &str) -> String {
    let mut out = text.to_owned();
    for rx in [&FENCE, &INLINE, &URL] {
        out = rx.replace_all(&out, |_| " ".to_owned());
    }
    replace_spans(&out, &pathlike_spans(&out))
}

fn replace_spans(text: &str, spans: &[(usize, usize)]) -> String {
    let mut out = String::with_capacity(text.len());
    let mut last = 0;
    for &(start, end) in spans {
        out.push_str(&text[last..start]);
        out.push(' ');
        last = end;
    }
    out.push_str(&text[last..]);
    out
}

/// python `drift_ratio(text, script)`: (목표 문자 비율, 라틴 글자 수). 둘 다 없으면 비율 1.
pub fn drift_ratio(text: &str, script: Script) -> (f64, usize) {
    let t = strip_text(text);
    let target = script.count(&t);
    let latin = t.chars().filter(char::is_ascii_alphabetic).count();
    let ratio = if target + latin > 0 {
        target as f64 / (target + latin) as f64
    } else {
        1.0
    };
    (ratio, latin)
}

/// python `is_drift(text, script)`: (이탈인가, 비율, 라틴 글자 수). 빈 답과 "No response requested." 는 이탈이 아니다.
pub fn is_drift(text: &str, script: Script) -> (bool, f64, usize) {
    if text.is_empty() || strip(text) == NO_RESPONSE {
        return (false, 1.0, 0);
    }
    let (ratio, latin) = drift_ratio(text, script);
    (latin >= MIN_LATIN && ratio < THRESHOLD, ratio, latin)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 고정 정규식이 regex 판과 python 판(py::re)에서 같은 자리에 맞는다(만든 글 3000개).
    #[test]
    fn fixed_patterns_agree_with_python() {
        let pieces = [
            "```",
            "~~~",
            "`x`",
            "`",
            "\n",
            " ",
            "http://a.b/c",
            "HTTPS://x",
            "www.x",
            "a/b",
            "./c/",
            "~/d",
            "x.rs",
            "main.PY",
            "-",
            "@",
            ".",
            "/",
            "\u{d55c}\u{ae00}",
            "<paste>",
            "</paste>",
            "<PASTED_TEXT a>",
            "</pasted_text>",
            "<pasted_content>",
            "x",
            "\u{e9}",
            "\u{17f}",
            "\u{212a}",
            "_",
            "9",
        ];

        // Patterns the regex crate reads as written (PASTED with its backref expanded)
        crate::fixed_re::assert_agree(
            &[
                ("FENCE", &*FENCE),
                ("INLINE", &*INLINE),
                ("URL", &*URL),
                ("PASTED", &*PASTED),
            ],
            &pieces,
        );

        // PATHLIKE through its lookbehind emulation
        for text in crate::fixed_re::corpus(&pieces, 3000) {
            let want: Vec<(usize, usize)> = PATHLIKE_PY
                .find_iter(&text)
                .iter()
                .map(|m| (m.start(), m.end()))
                .collect();
            assert_eq!(pathlike_spans(&text), want, "{text:?}");
        }
    }

    /// 영어 답은 이탈, 한국어 답 속 코드와 경로는 세지 않는다.
    #[test]
    fn drift_like_python() {
        // English prose drifts
        let english = "This is an answer written entirely in English words.";
        assert!(is_drift(english, Script::Hangul).0);

        // Korean prose with code and paths does not
        let korean = "고쳤습니다. `cargo test --workspace` 와 src/main.rs 를 보세요.\n```\nfn main() {}\n```";
        assert!(!is_drift(korean, Script::Hangul).0);

        // Short English is under MIN_LATIN
        assert!(
            !is_drift("OK, done.", Script::Hangul).0,
            "fewer than 20 Latin letters"
        );
        assert!(!is_drift(" No response requested. ", Script::Hangul).0);
    }
}
