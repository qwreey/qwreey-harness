//! 저장소의 기록 보관 위치 설정과 기록 경로 판정(python `sllib/records_home.py` 의 읽는 쪽).
//!
//! 설정은 저장소 안 `.claude/session-log.json` 이다: `{"records_home": "docs/sessions"}` 면 그 폴더로 import 하고,
//! `{"archive_only": true}` 면 기록을 저장소 밖에만 두고 pending 알림을 끈다.

use harness_hook::py::json_load::{Decode, from_bytes};
use harness_hook::py::path::{join, normpath};
use harness_hook::py::text::strip;
use harness_hook::py::value::{Dict, Value};

use crate::fsx;

const FILE: &str = ".claude/session-log.json";
/// 이미 있으면 보관 위치로 제안할 만한 이력 폴더.
const HISTORY_CANDIDATES: &[&str] = &[
    "handover",
    "handoff",
    "audit",
    "history",
    "docs/history",
    "docs/handoff",
    ".claude/audit",
    ".claude/handoff",
];

/// 설정 파일(python `load`). 없거나 읽지 못하거나 dict 가 아니면 빈 dict.
pub fn load(root: &str) -> Dict {
    let Some(os) = fsx::os_path(&join(root, FILE)) else {
        return Dict::new();
    };
    let parsed = std::fs::read(os)
        .ok()
        .and_then(|bytes| from_bytes(&bytes, Decode::Strict).ok());
    parsed.and_then(|v| v.into_dict().ok()).unwrap_or_default()
}

/// 기록을 저장소 밖에만 두는가(`archive_only` 가 참).
pub fn archive_only(root: &str) -> bool {
    load(root).get("archive_only").is_some_and(Value::truthy)
}

/// 설정된 보관 폴더(저장소 상대, 끝 `/` 없음). 없거나 저장소 밖을 가리키면 `None`.
pub fn home_rel(root: &str) -> Option<String> {
    let dict = load(root);
    let configured = strip(dict.get("records_home")?.as_str()?);
    if configured.is_empty() {
        return None;
    }
    let p = normpath(configured);
    let outside = p.starts_with('/') || p == ".." || p.starts_with("../");
    (!outside).then_some(p)
}

/// 저장소에 있는 이력 폴더들(끝에 `/`).
pub fn history_dirs(root: &str) -> Vec<String> {
    HISTORY_CANDIDATES
        .iter()
        .filter(|c| fsx::is_dir(&join(root, c)))
        .map(|c| format!("{c}/"))
        .collect()
}

/// `path` 가 `directory` 이거나 그 아래인가(둘 다 normpath 한 글로 본다).
///
/// python 과 같이 `directory` 가 `/` 면 `//` 로 시작하는 경로만 아래로 본다.
pub fn is_under(path: &str, directory: &str) -> bool {
    let (p, d) = (normpath(path), normpath(directory));
    p == d || p.starts_with(&format!("{d}/"))
}

/// 기록 폴더 이름 -> 종류(coderag agent-records 규약의 고정 폴더).
// python 판과 같은 표다. tests/parity_sessions.rs 가 python 의 값과 대조한다
// @copy-of: plugins/qwreey-sessions/scripts/sllib/records_home.py#BUILTIN_KINDS
const BUILTIN_KINDS: &[(&str, &str)] = &[
    ("plan", "living"),
    ("base", "living"),
    ("research", "living"),
    ("audit", "snapshot"),
    ("handoff", "snapshot"),
    ("sessions", "snapshot"),
    ("session", "snapshot"),
    ("archive", "archive"),
];
/// `.claude/scopes/<경로>/` 와 `packs/<pack>/` 는 저장소 한 부분의 기록이다.
const SCOPE_DIRS: &[&str] = &["scopes", "packs"];

fn kind(dir: &str) -> Option<&'static str> {
    BUILTIN_KINDS
        .iter()
        .find(|(name, _)| *name == dir)
        .map(|(_, kind)| *kind)
}

/// 경로가 어느 저장소의 `.claude/` 스냅숏 폴더 아래인가(글자만 본다). `skip_dirs` 의 `.claude` 는 건너뛴다.
pub fn is_snapshot(path: &str, skip_dirs: &[String]) -> bool {
    let normalized = normpath(path);
    let parts: Vec<&str> = normalized.split('/').collect();
    let skip: Vec<String> = skip_dirs.iter().map(|d| normpath(d)).collect();
    let last = parts.len().saturating_sub(2);
    for (i, part) in parts[..last].iter().enumerate() {
        if *part != ".claude" || skip.contains(&parts[..=i].join("/")) {
            continue;
        }

        // 범위 폴더는 그 아래 처음 나오는 기록 폴더 이름으로 본다
        let rest = &parts[i + 1..parts.len() - 1];
        let first = if SCOPE_DIRS.contains(&rest[0]) {
            rest[1..]
                .iter()
                .copied()
                .find(|r| kind(r).is_some())
                .unwrap_or("")
        } else {
            rest[0]
        };
        if kind(first) == Some("snapshot") {
            return true;
        }
    }
    false
}

#[cfg(test)]
mod tests {
    use super::*;

    /// audit, handoff 같은 스냅숏 폴더 안의 파일만 스냅숏이다.
    #[test]
    fn snapshot_folders_are_recognized() {
        assert!(is_snapshot("/r/.claude/audit/1/a.md", &[]));
        assert!(is_snapshot("/r/.claude/scopes/x/y/handoff/a.md", &[]));
        assert!(!is_snapshot("/r/.claude/plan/a.md", &[]));
        assert!(
            !is_snapshot("/r/.claude/audit", &[]),
            "the folder itself holds no file"
        );
    }

    /// 사용자 홈의 `.claude` 아래는 스냅숏 이름이어도 스냅숏이 아니다.
    #[test]
    fn user_claude_dir_is_never_a_snapshot() {
        assert!(!is_snapshot(
            "/h/.claude/sessions/a",
            &["/h/.claude/".to_owned()]
        ));
    }

    /// `is_under` 는 폴더 경계로 비교하고 루트는 아무것도 품지 않는다.
    #[test]
    fn under_compares_whole_path_parts() {
        assert!(is_under("/a/b", "/a/"));
        assert!(!is_under("/ab", "/a"), "ab is a sibling of a, not inside");
        assert!(!is_under("/x", "/"));
    }
}
