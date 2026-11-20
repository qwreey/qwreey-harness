//! 답변 언어 이탈 판정(python `strip_text`, `drift_ratio`, `is_drift`).
//!
//! 코드, URL, 경로를 뗀 글에서 목표 문자 체계 글자와 라틴 글자를 센다. 목표 비율이 0.25 미만이면서 라틴 글자가 20자
//! 이상이면 이탈이다(한글 프롬프트에 영어로 답한 턴과 아닌 턴이 이 문턱에서 깨끗이 갈렸다).

use std::sync::LazyLock;

use harness_hook::py::re::Flags;
use harness_hook::py::text::strip;
use harness_hook::rx::Regex;

use crate::language::Script;
use crate::scan::{pathlike_spans, url_spans};

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

static FENCE: LazyLock<Regex> =
    LazyLock::new(|| Regex::with_flags(r"```.*?(?:```|\Z)|~~~.*?(?:~~~|\Z)", DOTALL));
static INLINE: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"`[^`\n]*`"));

/// python `PASTED.sub` 가 떼는 붙여 넣은 블록. 쓰는 곳은 일치 범위만 본다.
// python 판 `<(pasted_content|pasted_text|paste)[^>]*>.*?(?:</\1>|\Z)` 의 괄호 참조는 rx 가 옮기지 않는다. 태그 이름마다의
// 갈래로 펼쳐도 한 자리에서 같은 순서로 해 보고 `>` 를 지나면 늘 맞으므로 범위가 같다(시험이 py::re 의 원래 패턴과 견준다)
pub static PASTED: LazyLock<Regex> = LazyLock::new(|| {
    Regex::with_flags(
        concat!(
            r"<pasted_content[^>]*>.*?(?:</pasted_content>|\Z)",
            r"|<pasted_text[^>]*>.*?(?:</pasted_text>|\Z)",
            r"|<paste[^>]*>.*?(?:</paste>|\Z)"
        ),
        IGNORECASE_DOTALL,
    )
});

/// python `strip_text(text)`: 코드 블록, 인라인 코드, URL, 경로를 공백 하나로 바꾼다.
pub fn strip_text(text: &str) -> String {
    let mut out = text.to_owned();
    for rx in [&FENCE, &INLINE] {
        out = rx.replace_all(&out, |_| " ".to_owned());
    }
    out = replace_spans(&out, &url_spans(&out));
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

    use harness_hook::py::re::Regex as PyRegex;
    use harness_hook::testkit::{assert_agree, corpus};

    const PIECES: &[&str] = &[
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
        "\u{130}",
        "\u{17f}",
        "\u{212a}",
        "_",
        "9",
    ];

    fn py(pattern: &str, flags: Flags) -> PyRegex {
        PyRegex::with_flags(pattern, flags).expect("python pattern")
    }

    /// 고정 정규식이 python 판(py::re)과 같은 자리에 맞고, 펼친 PASTED 가 괄호 참조 원래 패턴과 같은 범위를 뗀다(만든 글 3000개).
    #[test]
    fn fixed_patterns_agree_with_python() {
        assert_agree(
            &[
                ("FENCE", &*FENCE),
                ("INLINE", &*INLINE),
                ("PASTED", &*PASTED),
            ],
            PIECES,
        );

        // The python hook's PASTED, back reference and all
        let original = py(
            r"<(pasted_content|pasted_text|paste)[^>]*>.*?(?:</\1>|\Z)",
            IGNORECASE_DOTALL,
        );
        let spans = |ms: Vec<harness_hook::py::re::Match>| {
            ms.iter().map(|m| (m.start(), m.end())).collect::<Vec<_>>()
        };
        for text in corpus(PIECES, 3000) {
            assert_eq!(
                spans(PASTED.find_iter(&text)),
                spans(original.find_iter(&text)),
                "{text:?}"
            );
        }
    }

    /// strip_text 가 python 의 네 정규식(py::re)을 차례로 sub 한 글과 같다(만든 글과 세 번 이은 긴 글).
    #[test]
    fn strip_text_matches_the_python_regexes() {
        let patterns = [
            py(r"```.*?(?:```|\Z)|~~~.*?(?:~~~|\Z)", DOTALL),
            py(r"`[^`\n]*`", Flags::NONE),
            py(r"\b[a-z][a-z0-9+.-]*://\S+|\bwww\.\S+", Flags::IGNORECASE),
            py(
                r"(?<![\w])(?:[~.]{0,2}/)?[\w@.-]+(?:/[\w@.-]+)+/?|[\w-]+\.(?:[a-z]{1,5})\b",
                Flags::IGNORECASE,
            ),
        ];

        // Repeating makes long runs, the case the scanners exist for
        for piece_text in corpus(PIECES, 3000) {
            for text in [piece_text.clone(), piece_text.repeat(3)] {
                let want = patterns
                    .iter()
                    .fold(text.clone(), |t, rx| rx.replace_all(&t, |_| " ".to_owned()));
                assert_eq!(strip_text(&text), want, "{text:?}");
            }
        }
    }

    /// 정규식이 제곱 시간이던 답(Stop 에서 고치기 전 Rust 판 10 초, 훅 제한 5 초)을 debug 빌드에서도 1 초 안에 판정한다.
    #[test]
    fn slow_replies_are_judged_in_time() {
        let reply = format!("{} a/b", "see foo.rs and ".repeat(5000));
        let started = std::time::Instant::now();
        let (drifted, _, latin) = is_drift(&reply, Script::Hangul);
        let took = started.elapsed();
        assert!(took < std::time::Duration::from_secs(1), "{took:?}");

        // "see", "and" stay after foo.rs and a/b are stripped
        assert!(drifted && latin == 6 * 5000, "latin {latin}");
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
