//! 보고 글의 권고, 선택지, 열린 질문 신호(python `handback_notice.signals`, `carries_decisions`).
//!
//! 기계적 휴리스틱이다: 제목 줄(마크다운 제목, 줄 전체 굵게, 콜론으로 끝나는 짧은 줄)의 권고, 제안, 열린 질문 같은 말이
//! 하나라도 있거나, 본문 문구 신호가 둘 이상이면 참이다. 코드 블록은 보지 않는다.

use std::collections::BTreeSet;
use std::sync::LazyLock;

use harness_hook::py::re::Flags;

use crate::fixed_re::Fixed;

const DOTALL: Flags = Flags {
    ignore_case: false,
    multiline: false,
    dotall: true,
};

fn regex(pattern: &'static str, flags: Flags) -> Fixed {
    Fixed::with_flags(pattern, flags)
}

static FENCE: LazyLock<Fixed> = LazyLock::new(|| regex(r"```.*?```", DOTALL));
static HEADLINE: LazyLock<Fixed> = LazyLock::new(|| {
    regex(
        r"(?m)^\s{0,3}(?:(?:[-*]|\d+[.)])\s+)?(?:#{1,6}\s+(?P<h>[^\n]{1,80})|\*\*(?P<b>[^*\n]{1,80})\*\*:?\s*$|(?P<c>[^\n:]{1,50}):\s*$)",
        Flags::NONE,
    )
});
static HEAD_KEY: LazyLock<Fixed> = LazyLock::new(|| {
    regex(
        concat!(
            r"(?i)\b(recommendations?|recommended|proposals?|proposed changes?|suggestions?|open questions?|questions? for (?:you|the user|main)|",
            r"decisions? (?:needed|pending|for (?:you|the user|main))|to decide|choices for (?:you|the user)|options for)\b|",
            r"(권고|추천|제안|선택지|결정 필요|필요한 결정|결정할|사용자 결정|미결|열린 질문|사용자에게 물을|사용자 질문|확인 대기)"
        ),
        Flags::NONE,
    )
});
static PHRASE: LazyLock<Fixed> = LazyLock::new(|| {
    regex(
        concat!(
            r"(?i)\b(?:open questions?|recommendation)\s*:|",
            r"\b(?:I recommend|I'd recommend|my recommendation|your call|",
            r"the user(?:'s)? (?:to decide|decision|should decide|call)|for you to decide|needs? (?:your|the user's) (?:decision|confirmation|approval)|",
            r"pending (?:user )?(?:confirmation|decision)|awaiting (?:your |a )?decision|do you want)\b|\(recommended\)|",
            r"권장한다|권합니다|추천한다|추천합니다|제안한다|제안합니다|사용자 결정이? 필요|사용자 결정입니다|사용자가 정할|사용자 판단이? 필요|",
            r"결정이 필요|결정해 주|정해 주세요|어느 쪽[이을]|할까요\?"
        ),
        Flags::NONE,
    )
});
static QLINE: LazyLock<Fixed> = LazyLock::new(|| {
    regex(
        r"(?m)^\s*(?:[-*]\s*|\|\s*)?(?:\*\*)?(?:Q\d+|Option [A-Z0-9]|선택지 ?\d|안 ?[A-D1-4][.):])",
        Flags::NONE,
    )
});
static SPACES: LazyLock<Fixed> = LazyLock::new(|| regex(r"\s+", Flags::NONE));

/// python `signals(text)`: `head:<말>` 과 문구 신호의 집합.
pub fn signals(text: &str) -> BTreeSet<String> {
    let text = FENCE.replace_all(text, |_| String::new());
    let mut found = BTreeSet::new();

    // Headline keywords
    for m in HEADLINE.find_iter(&text) {
        let head = (1..=3)
            .filter_map(|i| m.text(&text, i).filter(|s| !s.is_empty()))
            .next()
            .unwrap_or("");
        if let Some(k) = HEAD_KEY.search(head) {
            let word = k
                .text(head, 1)
                .filter(|s| !s.is_empty())
                .or_else(|| k.text(head, 2))
                .unwrap_or("");
            found.insert(format!("head:{}", word.to_lowercase()));
        }
    }

    // Body phrases and option lines
    for m in PHRASE.find_iter(&text) {
        let phrase = &text[m.start()..m.end()];
        found.insert(
            SPACES
                .replace_all(phrase, |_| " ".to_owned())
                .to_lowercase(),
        );
    }
    if QLINE.find_iter(&text).len() >= 2 {
        found.insert("qlines".to_owned());
    }
    found
}

/// python `carries_decisions(text)`: 제목 신호가 하나라도, 또는 신호가 둘 이상.
pub fn carries_decisions(text: &str) -> bool {
    let found = signals(text);
    found.iter().any(|s| s.starts_with("head:")) || found.len() >= 2
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 이 모듈의 고정 정규식이 regex 판과 python 판(py::re)에서 같은 자리에 맞는다(만든 글 3000개).
    #[test]
    fn fixed_patterns_agree_with_python() {
        crate::fixed_re::assert_agree(
            &[
                ("FENCE", &*FENCE),
                ("HEADLINE", &*HEADLINE),
                ("HEAD_KEY", &*HEAD_KEY),
                ("PHRASE", &*PHRASE),
                ("QLINE", &*QLINE),
                ("SPACES", &*SPACES),
            ],
            &[
                "## ",
                "**",
                "Recommendations",
                "recommended",
                "Open questions",
                ":",
                "\n",
                " ",
                "Q1",
                "Q2: x",
                "- ",
                "1. ",
                "I recommend",
                "your call",
                "(recommended)",
                "권고",
                "할까요?",
                "```",
                "x",
                "Decisions needed",
                "options for",
                "\t",
                "é",
                "_",
                "9",
                "Option A",
                "안 1.",
                "\u{2167}",
                "\u{301}",
                "\u{a0}",
            ],
        );
    }

    /// 모든 내장 정규식이 읽힌다.
    #[test]
    fn built_in_patterns_compile() {
        for re in [&FENCE, &HEADLINE, &HEAD_KEY, &PHRASE, &QLINE, &SPACES] {
            LazyLock::force(re);
        }
    }

    /// 제목 하나면 충분하고, 문구는 둘이 있어야 하며, 코드 블록 안은 세지 않는다.
    #[test]
    fn decisions_like_python() {
        // A headline alone is enough
        assert!(carries_decisions("## Recommendations\n- do x"));
        assert!(carries_decisions("**열린 질문**\n1. a"));

        // One phrase is not, two are
        assert!(!carries_decisions("I recommend the first one."));
        assert!(carries_decisions("I recommend the first one. Your call."));

        // Fenced code is ignored
        assert!(!carries_decisions("```\n## Recommendations\n```\nall good"));

        // Option lines count once as a group
        assert_eq!(
            signals("Q1: a\nQ2: b"),
            BTreeSet::from(["qlines".to_owned()]),
            "two Q lines make one signal; `Q1: a` is not a headline (text after the colon)"
        );
    }
}
