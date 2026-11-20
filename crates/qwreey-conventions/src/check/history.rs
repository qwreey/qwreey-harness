//! 주석 줄 검사(python `scan`, `reason_words`, `check_lines`): 이력 표지, 이유 없는 `Ref:` 꼬리, 기호, 이스케이프.

use std::sync::LazyLock;

use harness_hook::py::re::{Flags, Regex};

use super::Category;
use super::chars::{ESCAPE, odd_chars};
use super::config::{Cfg, Patterns};
use crate::edit::Added;
use crate::halt::Result;
use crate::lex::{Row, comment_body};

/// `Ref:` 꼬리 줄(python `REF_LINE`).
static REF_LINE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::with_flags(r"^\s*Ref\s*:", Flags::IGNORECASE).expect("constant pattern")
});

/// 이유 문장의 낱말(python `WORD`).
static WORD: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"[A-Za-zÀ-ɏ]{2,}|[가-힣]{2,}").expect("constant pattern"));

/// 지시자 줄(python `DIRECTIVE`): 도구에게 하는 말이라 검사와 언어 판정에서 뺀다.
pub static DIRECTIVE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::with_flags(
        r"^\s*(?:!|@|-\*-|eslint|prettier|noqa|type:|pyright|pylint|mypy|selene|stylua|luau-lsp|region|endregion|nolint|lint:|coding[:=]|vim:|go:|nocheck|<reference)",
        Flags::IGNORECASE,
    )
    .expect("constant pattern")
});

/// 줄의 주석 조각 가운데 지시자가 있는가.
pub fn has_directive(row: &Row) -> bool {
    row.c.iter().any(|c| DIRECTIVE.match_start(c).is_some())
}

/// python `scan(body, pats, pub)` 의 지운 본문: 공개 식별자를 공백으로 지운다.
pub fn scrub_public(body: &str, pats: &Patterns) -> String {
    let mut body = body.to_owned();
    for p in &pats.public {
        body = p.replace_all(&body, |_| " ".to_owned());
    }
    body
}

/// python `scan(body, pats, pub)[0]` 가 비지 않았나: 공개 식별자를 지운 본문에 이력 패턴이 있는가.
pub fn has_history(body: &str, pats: &Patterns) -> bool {
    let body = scrub_public(body, pats);
    pats.history.iter().any(|(_, rx)| rx.is_match(&body))
}

/// python `reason_words(body, pats)`: 이력 패턴을 지운 뒤 남은 낱말 수.
fn reason_words(body: &str, pats: &Patterns) -> usize {
    let mut body = body.to_owned();
    for (_, rx) in &pats.history {
        body = rx.replace_all(&body, |_| " ".to_owned());
    }
    WORD.find_iter(&body).len()
}

/// python `check_lines(rows, added, pats, pub, cfg)`: 추가한 줄의 (줄 번호(1 기반), 범주). 한 줄에 범주가 여럿일 수 있다.
///
/// 주석 덩어리는 코드 없이 주석만 있는 줄이 이어진 것이고, 코드와 한 줄에 있는 주석은 줄마다 따로다.
/// `Ref:` 꼬리는 같은 덩어리에 이유 문장(낱말 `min_reason_words` 개 이상)이 있으면 통과한다.
pub fn check_lines(
    rows: &[Row],
    added: &Added,
    pats: &Patterns,
    cfg: &Cfg,
) -> Result<Vec<(usize, Category)>> {
    let segs: Vec<Option<String>> = rows
        .iter()
        .map(|r| {
            (!r.c.is_empty()).then(|| {
                r.c.iter()
                    .map(|c| comment_body(c))
                    .collect::<Vec<_>>()
                    .join(" ")
            })
        })
        .collect();
    let standalone: Vec<bool> = rows.iter().map(|r| !r.c.is_empty() && !r.code).collect();
    let allow = cfg.allow();
    let min_words = cfg.min_reason_words()?;
    let mut problems = Vec::new();

    let n = rows.len();
    let mut i = 0;
    while i < n {
        if segs[i].is_none() {
            i += 1;
            continue;
        }

        // One comment block
        let mut j = i + 1;
        if standalone[i] {
            while j < n && standalone[j] && segs[j].is_some() {
                j += 1;
            }
        }
        let block = i..j;
        i = j;
        if !block.clone().any(|k| added.contains(&k)) {
            continue;
        }

        // Lines of the block this edit added
        let mut has_reason: Option<bool> = None;
        for k in block.clone() {
            let Some(body) = segs[k].as_deref().filter(|b| !b.is_empty()) else {
                continue;
            };
            if !added.contains(&k) || has_directive(&rows[k]) {
                continue;
            }
            let allow = allow.as_ref().map_err(|e| *e)?;
            if odd_chars(body, allow) {
                problems.push((k + 1, Category::Symbol));
            }
            if ESCAPE.is_match(body) {
                problems.push((k + 1, Category::Escape));
            }
            if REF_LINE.match_start(body).is_some() && cfg.allow_ref_tail() {
                let reason = *has_reason.get_or_insert_with(|| {
                    block.clone().any(|b| {
                        segs[b].as_deref().is_some_and(|s| {
                            !s.is_empty()
                                && REF_LINE.match_start(s).is_none()
                                && reason_words(&scrub_public(s, pats), pats) as i128 >= min_words
                        })
                    })
                });
                if !reason {
                    problems.push((k + 1, Category::RefTail));
                }
                continue;
            }
            if has_history(body, pats) {
                problems.push((k + 1, Category::History));
            }
        }
    }
    Ok(problems)
}
