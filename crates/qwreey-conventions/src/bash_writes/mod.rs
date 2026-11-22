//! bash-writes(python `hooks/bash_writes.py`): Bash 로 바꾼 파일에 Edit, Write 와 같은 추가 줄 검사를 돌리고 아직 안 보인 rule 을 넣는다.
//!
//! heredoc, sed -i, 인터프리터 스크립트, tee, 리다이렉트로 쓰면 Edit|Write 매처의 훅(conventions-check, rules-inject)이 돌지 않는다.
//! 그래서 두 단계로 본다.
//! - PreToolUse(Bash): bash-bypass-reminder 가 쓰기 신호를 보면 명령 전 상태를 스냅숏으로 적는다([`before`]).
//! - PostToolUse(Bash), PostToolUseFailure(Bash): 스냅숏이 있으면 바뀐 파일과 그 전 글을 찾고([`changes`]), 추가 줄에
//!   conventions-check 의 `file_notice` 를, 코드 파일에 reuse-check 를, 바뀐 파일에 맞는 rule 에 rules-inject 를 돌린다([`notice`]).
//!
//! 스냅숏 파일은 python 판과 같은 자리, 같은 꼴이다. 한쪽의 Pre 와 다른 쪽의 Post 가 이어져도 된다(세션이 다시 읽는 사이).
//! python 판은 본문 전체를 try 로 감싸 무엇이 틀려도 조용히 0 으로 끝난다. 이 판도 그렇다.
//!
//! python 과 다른 곳: python 은 사본 검사(reuse-check)를 파일마다 하위 프로세스로 나란히 띄우고, 이 판은 차례로 부른다.
//! 같은 세션 상태 파일을 나란히 쓰다 한쪽 기록이 지워지는 python 의 경합은 여기 없다.

pub mod before;
pub mod changes;
pub mod files;
pub mod notice;
pub mod repo;
pub mod snap;

use std::time::{Duration, Instant};

use harness_hook::HookInput;
use harness_hook::output::{EnsureAscii, HookOutput};
use harness_hook::py::fs;
use harness_hook::py::path::{normpath, splitext};

use crate::check;
use crate::context::Context;
use crate::halt::Result;
use crate::rules::plugin_root;
use notice::OUTPUT_BUDGET;

/// 바뀐 파일을 찾는 시간 한도(python `CHANGES_S`, 훅 시작부터).
const CHANGES_S: Duration = Duration::from_millis(1500);
/// 추가 줄을 검사하는 확장자(python `CHECK_EXT`).
pub const CHECK_EXT: &[&str] = &[
    ".luau", ".lua", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".astro", ".rs", ".py", ".go", ".kt",
    ".sh", ".html", ".htm", ".md",
];

/// 검사 대상 확장자인가(python `os.path.splitext(rel)[1].lower() in CHECK_EXT`).
pub fn checked_ext(path: &str) -> bool {
    CHECK_EXT.contains(&splitext(path).1.to_lowercase().as_str())
}

/// python `_inside(path, root)`: 정리한 경로가 `root/` 아래인가.
pub fn inside(path: &str, root: &str) -> bool {
    normpath(path).starts_with(&format!("{}/", normpath(root).trim_end_matches('/')))
}

/// bash-writes 훅 하나. python 이 조용히 넘기는 실패는 모두 `None` 이다.
pub fn run(ctx: &Context, input: &HookInput) -> Result<Option<String>> {
    let t0 = Instant::now();
    Ok(after(ctx, input, t0).unwrap_or(None))
}

fn after(ctx: &Context, input: &HookInput, t0: Instant) -> Result<Option<String>> {
    if input.tool_name() != Some("Bash") {
        return Ok(None);
    }
    // 실패한 명령만 그 이벤트 이름으로 답하고, 그 밖은 PostToolUse
    let event = if input.hook_event_name() == Some("PostToolUseFailure") {
        "PostToolUseFailure"
    } else {
        "PostToolUse"
    };

    // The snapshot this command's PreToolUse took, used once
    let fp = snap::snap_path(ctx, input)?;
    let Some(snapshot) = snap::load(&fp)? else {
        return Ok(None);
    };
    if let Some(os) = fs::os_path(&fp) {
        let _ = std::fs::remove_file(os);
    }

    // What the command changed
    let restrict = snap::pending(ctx, input, None)?;
    let found = changes::changes(&snapshot, Some(t0 + CHANGES_S), restrict)?;
    if found.touched.is_empty() {
        return Ok(None);
    }

    // Added-line checks, then copy notes in the room left
    let mut out = String::new();
    if !ctx.is_off("CONVENTIONS_CHECK") && (!found.items.is_empty() || !found.unread.is_empty()) {
        let plugin_root = plugin_root(ctx)?;
        let n = notice::notices(
            ctx,
            input,
            &plugin_root,
            &snapshot.root,
            &found.items,
            &found.unread,
            t0,
        )?;
        let mut body = n.body;
        for note in notice::reuse_notes(ctx, input, &n.code) {
            let mut trial = body.clone();
            trial.push(note.clone());
            if check::notice_tag(ctx, input, &trial)?.chars().count() <= OUTPUT_BUDGET {
                body.push(note);
            }
        }
        if !body.is_empty() {
            out = check::notice_tag(ctx, input, &body)?;
        }
    }

    // Notice first, then rules in the room left
    let room = OUTPUT_BUDGET as i64 - out.chars().count() as i64 - 1;
    let rules = notice::rules_block(ctx, input, &found.touched, room)?;
    let context: Vec<&str> = [out.as_str(), rules.as_str()]
        .into_iter()
        .filter(|x| !x.is_empty())
        .collect();
    if context.is_empty() {
        return Ok(None);
    }
    Ok(Some(
        HookOutput::context(event, context.join("\n")).render(EnsureAscii::No),
    ))
}
