//! 답변 언어 이탈 판정(python `strip_text`, `drift_ratio`, `is_drift`).
//!
//! 코드, URL, 경로를 뗀 글에서 목표 문자 체계 글자와 라틴 글자를 센다. 목표 비율이 0.25 미만이면서 라틴 글자가 20자
//! 이상이면 이탈이다(한글 프롬프트에 영어로 답한 턴과 아닌 턴이 이 문턱에서 깨끗이 갈렸다).

use std::sync::LazyLock;

use harness_hook::py::re::{Flags, Regex};
use harness_hook::py::text::strip;

use crate::language::Script;

const MIN_LATIN: usize = 20;
const THRESHOLD: f64 = 0.25;
const NO_RESPONSE: &str = "No response requested.";

fn regex(pattern: &str, flags: Flags) -> Regex {
    Regex::with_flags(pattern, flags).expect("built-in pattern")
}

const DOTALL: Flags = Flags {
    ignore_case: false,
    multiline: false,
    dotall: true,
};

static FENCE: LazyLock<Regex> =
    LazyLock::new(|| regex(r"```.*?(?:```|\Z)|~~~.*?(?:~~~|\Z)", DOTALL));
static INLINE: LazyLock<Regex> = LazyLock::new(|| regex(r"`[^`\n]*`", Flags::NONE));
static URL: LazyLock<Regex> =
    LazyLock::new(|| regex(r"\b[a-z][a-z0-9+.-]*://\S+|\bwww\.\S+", Flags::IGNORECASE));
static PATHLIKE: LazyLock<Regex> = LazyLock::new(|| {
    regex(
        r"(?<![\w])(?:[~.]{0,2}/)?[\w@.-]+(?:/[\w@.-]+)+/?|[\w-]+\.(?:[a-z]{1,5})\b",
        Flags::IGNORECASE,
    )
});
/// 붙여 넣은 블록(python `PASTED`).
pub static PASTED: LazyLock<Regex> = LazyLock::new(|| {
    let flags = Flags {
        ignore_case: true,
        dotall: true,
        multiline: false,
    };
    regex(
        r"<(pasted_content|pasted_text|paste)[^>]*>.*?(?:</\1>|\Z)",
        flags,
    )
});

/// python `strip_text(text)`: 코드 블록, 인라인 코드, URL, 경로를 공백 하나로 바꾼다.
pub fn strip_text(text: &str) -> String {
    let mut out = text.to_owned();
    for rx in [&FENCE, &INLINE, &URL, &PATHLIKE] {
        out = rx.replace_all(&out, |_| " ".to_owned());
    }
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

    /// 모든 내장 정규식이 읽힌다.
    #[test]
    fn built_in_patterns_compile() {
        for re in [&FENCE, &INLINE, &URL, &PATHLIKE, &PASTED] {
            LazyLock::force(re);
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
