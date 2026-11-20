//! 모델에게 가는 글(python `sllib/messages.py` 의 옮긴 훅이 쓰는 것). 글자 하나까지 python 판과 같아야 한다.
//!
//! 태그: `<harness-hook name="session-log" level="info|warn|action" nonce="...">` (`home/.claude/HOOK-MESSAGES.md`).

use std::cmp::Ordering;

use harness_hook::Nonce;
use harness_hook::py::text::strip;
use harness_hook::tag::{self, Level};

use crate::pyval::Num;

/// 태그 이름.
pub const TAG_NAME: &str = "session-log";

/// 본문 하나를 태그로 감싼다(python `wrap`). 앞뒤 공백을 떼고, 비면 빈 글.
pub fn wrap(body: &str, level: Level, nonce: Option<&Nonce>) -> String {
    let body = strip(body);
    if body.is_empty() {
        return String::new();
    }
    tag::harness_hook(TAG_NAME, level, nonce, body)
}

/// level 마다 태그 하나, level 은 처음 나온 순서로(python `wrap_parts`). 빈 글은 건너뛴다.
///
/// 순서가 [`harness_hook::Notices`] 의 action, warn, info 와 다르다: python 판은 넣은 순서를 지킨다.
pub fn wrap_parts(parts: &[(Level, String)], nonce: Option<&Nonce>) -> String {
    let mut groups: Vec<(Level, Vec<&str>)> = Vec::new();
    for (level, text) in parts.iter().filter(|(_, t)| !t.is_empty()) {
        match groups.iter_mut().find(|(l, _)| l == level) {
            Some((_, texts)) => texts.push(text),
            None => groups.push((*level, vec![text])),
        }
    }
    groups
        .iter()
        .map(|(level, texts)| wrap(&texts.join("\n"), *level, nonce))
        .collect::<Vec<_>>()
        .join("\n")
}

fn plural(n: impl PartialEq<i64> + Copy) -> &'static str {
    if n != 1 { "s" } else { "" }
}

// ---- 요약 완료와 진행 알림 ----

/// 요약을 백그라운드에서 시작했다. `line_from` 은 python 의 `f"{n}"` 글이다.
pub fn started(trigger: &str, line_from: &str, line_to: Option<&str>) -> String {
    let range = format!(
        "L{line_from}\u{2013}{}",
        line_to.map_or("end".to_owned(), |t| format!("L{t}"))
    );
    format!(
        "Session log: summarizing this session ({range}, {trigger}) in the background; you will get a note when it is saved."
    )
}

/// 요약 완료 알림(python `saved`). `files` 가 비면 python 은 IndexError 라 `None`.
///
/// 절 수와 표시한 항목 수는 알림 큐에서 더한 python 수라 float 일 수 있다(글과 단수 판정이 python 과 같게).
pub fn saved(sections: Num, files: &[String], pending: usize, flagged: Num) -> Option<String> {
    let first = files.first()?;
    let place = if files.len() == 1 {
        first.clone()
    } else {
        format!("{first} (+{} more)", files.len() - 1)
    };
    let mut out = format!(
        "Session log: saved {} new section{} to {place}.",
        sections.text(),
        num_plural(sections)
    );

    // 원문 대조에 걸린 항목, 받아 가지 않은 기록
    if flagged.compare(Num::Int(0)) != Some(Ordering::Equal) {
        out += &format!(
            " {} item{} failed the source check and are marked \u{26a0}.",
            flagged.text(),
            num_plural(flagged)
        );
    }
    if pending > 0 {
        out += &format!(
            " {pending} record{} pending import (`session-log pending`).",
            plural(pending as i64)
        );
    }
    Some(out)
}

fn num_plural(n: Num) -> &'static str {
    if n.compare(Num::Int(1)) == Some(Ordering::Equal) {
        ""
    } else {
        "s"
    }
}

// ---- pending(받아 가지 않은 기록) 알림 ----

/// 알림을 낸 까닭(python `REASONS` 의 키).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Trigger {
    SessionStart,
    Commit,
    PreCompact,
    Handover,
}

impl Trigger {
    /// dedup 키와 python 의 trigger 글.
    pub fn as_str(self) -> &'static str {
        match self {
            Trigger::SessionStart => "session_start",
            Trigger::Commit => "commit",
            Trigger::PreCompact => "precompact",
            Trigger::Handover => "handover",
        }
    }

    fn reason(self) -> &'static str {
        match self {
            Trigger::SessionStart => "",
            Trigger::Commit => {
                "You are about to commit. If they belong with this work, importing now puts them in this commit; otherwise leave them."
            }
            Trigger::PreCompact => {
                "Compaction is about to drop details; importing keeps them in the repo."
            }
            Trigger::Handover => "A handover is a good time to import or dismiss them.",
        }
    }
}

fn records(count: usize) -> String {
    format!(
        "{count} auto-summarized session record{}",
        plural(count as i64)
    )
}

/// 보관 위치가 정해졌거나(home) 아직 쌓이지 않았을 때의 pending 알림(python `pending`).
pub fn pending(
    count: usize,
    oldest_date: &str,
    oldest_days: i64,
    trigger: Trigger,
    home: Option<&str>,
) -> String {
    let days = format!("{oldest_days} day{}", plural(oldest_days));
    let mut head = format!(
        "Session log: {} pending import (oldest from {oldest_date}, {days}), not in git yet. ",
        records(count)
    );

    // import 를 바로 할 수 있나
    match home {
        Some(home) => {
            head += &format!(
                "`session-log import` copies them verbatim into {home} (no curation; each gets a snapshot header); `session-log dismiss <rid>...` drops them."
            );
        }
        None => {
            head += "No records home is set yet, so import will not run until the user picks one; see /qwreey-sessions:import. `session-log dismiss <rid>...` drops them.";
        }
    }

    // 지금 알리는 까닭
    let reason = trigger.reason();
    if !reason.is_empty() {
        head += " ";
        head += reason;
    }
    if trigger == Trigger::Commit {
        head += " (Not blocking.)";
    }
    head
}

/// 보관 위치가 없는데 기록이 쌓였을 때 위치를 제안하라는 알림(python `pending_propose`).
pub fn pending_propose(
    count: usize,
    oldest_date: &str,
    oldest_days: i64,
    history: &[String],
) -> String {
    // 고를 자리
    let mut options = vec![
        "`docs/sessions/` (team-visible)".to_owned(),
        "`.claude/sessions/` (for agents only)".to_owned(),
    ];
    if !history.is_empty() {
        let dirs: Vec<String> = history.iter().map(|h| format!("`{h}`")).collect();
        options.push(format!("the existing history dir {}", dirs.join(" or ")));
    }
    options.push(
        "keep them outside the repo as an archive only (`session-log home --archive-only`; turns off these reminders)".to_owned(),
    );

    format!(
        "Session log: {} have piled up outside the repo (oldest from {oldest_date}, {oldest_days} day{}) and this repo has no records home. \
         Propose a location to the user, one of: {}. \
         Save the choice with `session-log home <path>` (commit `.claude/session-log.json` so coworkers share it), \
         then run `session-log import`.",
        records(count),
        plural(oldest_days),
        options.join("; ")
    )
}

// ---- 기록을 읽을 때 ----

/// PostToolUse(Read, Grep) 에서 세션 기록을 읽었을 때.
pub const RECORD_READ: &str = "You read or searched session records. Records are snapshots of what was discussed then and may be stale: \
verify any decision or fact against current files and the git log before acting on it.";

/// 큰 기록을 offset, limit 없이 Read 하려 할 때의 deny 사유(python `record_read_gate`).
///
/// `coderag`: coderag 가 PATH 에 있고 파일이 저장소 `.claude` 기록일 때만 그 명령을 안내한다.
/// `gate_kb` 는 python `int(gate_kb)` 의 글이다.
pub fn record_read_gate(kb: u64, gate_kb: &str, path: &str, coderag: bool) -> String {
    let ways = format!(
        "{}Grep this file for the section, or /qwreey-sessions:recall for an earlier discussion",
        if coderag {
            format!("`coderag get {path} --sections` (sections with line ranges), ")
        } else {
            String::new()
        }
    );
    format!(
        "Read blocked: this record is {kb} KB ({gate_kb} KB or more) and the Read had no offset/limit. \
         It is a snapshot from its date and may be stale, and reading it whole fills the context. \
         Find the part you need first: {ways}; then Read only those lines with offset/limit. \
         If you do need all of it, Read it in chunks with offset/limit."
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn wrap_parts_keeps_first_seen_order() {
        let parts = vec![
            (Level::Info, "a".to_owned()),
            (Level::Warn, "b".to_owned()),
            (Level::Info, "c".to_owned()),
            (Level::Warn, String::new()),
        ];
        assert_eq!(
            wrap_parts(&parts, None),
            "<harness-hook name=\"session-log\" level=\"info\">\na\nc\n</harness-hook>\n\
             <harness-hook name=\"session-log\" level=\"warn\">\nb\n</harness-hook>"
        );
        assert_eq!(wrap(" \n", Level::Info, None), "");
    }
}
