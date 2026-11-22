//! PreToolUse(Bash) 의 스냅숏(python `bash_writes.snapshot`): bash-bypass-reminder 가 쓰기 신호를 보면 부른다.
//!
//! 저장소(명령 cwd 의 git 최상위, git 이 아니면 프로젝트 폴더) 안에서 명령에 든 경로의 지금 글과 (mtime, 크기), git 이면 HEAD 와
//! porcelain 에 나온 파일의 (mtime, 크기)와 검사 대상 파일의 글을 적는다.

use std::collections::HashSet;
use std::sync::LazyLock;

use harness_hook::HookInput;
use harness_hook::py::path::{basename, dirname, join};
use harness_hook::rx::Regex;

use super::files::{self, CANDIDATE_MAX, Recorded, TEXT_MAX, TOTAL_MAX, char_len};
use super::repo::{self, Porcelain};
use super::snap::{self, Snapshot};
use super::{checked_ext, inside, plain_path};
use crate::context::Context;
use crate::halt::Result;

/// porcelain 에서 적는 파일 수 한도(python `DIRTY_MAX`).
pub const DIRTY_MAX: usize = 400;

/// worktree 를 다시 쓰는 git 하위 명령(python `GIT_REWRITE`). git 의 전역 옵션(`-C dir`, `-c k=v`, `--no-pager`) 뒤까지 본다.
pub static GIT_REWRITE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(
        r"\bgit(?:\s+(?:-[Cc]\s+\S+|--[\w-]+(?:=\S+)?|-[A-Za-z]+))*\s+(?:checkout|switch|stash|reset|merge|rebase|pull|cherry-pick|revert|restore|am)\b|\bgh\s+pr\s+checkout\b",
    )
});

/// 명령 하나의 스냅숏 재료.
pub struct Before<'a> {
    pub cmd: &'a str,
    pub cwd: &'a str,
    /// 명령에 든 절대 경로들(리다이렉트 대상, 그다음 경로 꼴 낱말).
    pub candidates: &'a [String],
    /// 쓰기 신호(제자리 편집, 쓰는 인터프리터 스크립트, 저장소 안으로의 리다이렉트)가 있는가.
    pub signal: bool,
}

/// python `snapshot(data, cmd, cwd, candidates, signal)`: 명령 전 상태를 스냅숏 파일로 적는다.
///
/// 쓰기 신호가 없거나, 검사와 rule 주입이 모두 꺼졌거나, 적을 것이 없으면 아무것도 쓰지 않는다.
pub fn take(ctx: &Context, input: &HookInput, before: &Before<'_>) -> Result<()> {
    if !before.signal
        || (ctx.is_off("CONVENTIONS_CHECK") && ctx.is_off("HARNESS_CONVENTIONS_RULES"))
    {
        return Ok(());
    }
    let (root, head, is_git) = match repo::repo(before.cwd)? {
        Some((root, head)) => (root, head, true),
        None => {
            let root = ctx
                .env
                .get_nonempty("CLAUDE_PROJECT_DIR")
                .unwrap_or(before.cwd);
            (root.to_owned(), None, false)
        }
    };
    let mut snap = Snapshot {
        root,
        head,
        ..Snapshot::default()
    };

    // Named paths: text while the total fits, (mtime, size) always
    let mut total = 0;
    let mut seen = HashSet::new();
    for p in before.candidates {
        if !seen.insert(p.as_str()) || !inside(p, &snap.root) || !plain_path(p) {
            continue;
        }
        snap.named.push(p.clone());
        snap.stats.push((p.clone(), files::stat(p)?));
        let t = files::read(p, CANDIDATE_MAX.min(TOTAL_MAX.saturating_sub(total)))?;
        total += t.text().map_or(0, char_len);
        snap.texts.push((p.clone(), t));
    }

    // Dirty files: (mtime, size) and text within the limits
    snap.rewrite = GIT_REWRITE.is_match(before.cmd);
    let st = if is_git && !snap.rewrite {
        repo::porcelain(&snap.root)?
    } else {
        None
    };
    record_dirty(&mut snap, st.as_ref(), &mut total)?;
    if snap.texts.is_empty() && st.is_none() {
        return Ok(());
    }

    // Private file in a private folder
    let fp = snap::snap_path(ctx, input)?;
    if !snap::own_dir(dirname(&fp)) {
        return Ok(());
    }
    snap.wide = st.is_some();
    snap.overflow = st.as_ref().is_some_and(|s| s.len() > DIRTY_MAX);
    snap.concurrent = snap::pending(ctx, input, Some(basename(&fp)))?;
    snap::write(&fp, &snap)
}

// porcelain 의 처음 DIRTY_MAX 개: (mtime, 크기), 검사 대상 확장자면 한도 안에서 글
fn record_dirty(snap: &mut Snapshot, st: Option<&Porcelain>, total: &mut u64) -> Result<()> {
    let Some(st) = st else {
        return Ok(());
    };
    let mut have: HashSet<String> = snap.texts.iter().map(|(p, _)| p.clone()).collect();
    for (rel, _) in st.iter().take(DIRTY_MAX) {
        let ap = join(&snap.root, rel);
        snap.dirty.push((rel.clone(), files::stat(&ap)?));
        if have.contains(&ap) || !checked_ext(rel) || *total >= TOTAL_MAX {
            continue;
        }
        if let Recorded::Text(t) = files::read(&ap, TEXT_MAX.min(TOTAL_MAX.saturating_sub(*total)))?
        {
            *total += char_len(&t);
            have.insert(ap.clone());
            snap.texts.push((ap, Recorded::Text(t)));
        }
    }
    Ok(())
}
