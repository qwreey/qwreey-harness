//! compact 회차(python `compact_epoch.py`, 정본 `lib/compact_epoch.py`의 읽는 쪽).
//!
//! "세션당 한 번" 알림의 dedup 단위는 (session_id, agent_id 또는 main, 회차)다. compact 는 session_id 를 유지하면서
//! 이전 알림을 맥락에서 지우기 때문이다. 회차 파일은 `<임시 폴더>/claude-qwreey-sessions-epoch/<sid>` 이고 PreCompact 의
//! python 훅이 올린다. 여기서는 읽기만 한다.

use harness_hook::py::num::parse_int;
use harness_hook::py::path::join;
use harness_hook::py::unicode::is_word;

use crate::abort::{Abort, Result};
use crate::fsx;

/// 이 플러그인의 회차 폴더 이름.
const EPOCH_DIR: &str = "claude-qwreey-sessions-epoch";

/// python `_sid(value)`: `str(value or "nosession")` 에서 단어 글자와 `-` 만 남긴다. `value` 는 이미 `str()` 한 글이다.
pub fn sanitize(value: Option<&str>) -> String {
    let text = value.filter(|v| !v.is_empty()).unwrap_or("nosession");
    text.chars()
        .filter(|&c| c == '-' || is_word(u32::from(c)))
        .collect()
}

/// 이 세션의 회차(python `epoch`). 임시 폴더가 없거나 파일을 읽지 못하면 0.
///
/// python `int()` 가 받지만 i128 을 넘는 값도 0 으로 본다(그런 회차는 쓰이지 않는다).
pub fn epoch(tempdir: Option<&str>, session_id: Option<&str>) -> i128 {
    let Some(tmp) = tempdir else { return 0 };
    let path = join(&join(tmp, EPOCH_DIR), &sanitize(session_id));
    match fsx::read_text(&path) {
        Ok(text) => parse_int(&text).unwrap_or(0),
        Err(_) => 0,
    }
}

/// 이 회차의 dedup 표식 경로(python `state_path`): `<임시 폴더>/<namespace>/<sid>.c<회차>[.a<agent>].json`. 폴더를 만든다.
///
/// 임시 폴더가 없거나 폴더를 만들지 못하면 python 은 예외로 끝난다.
pub fn state_path(
    tempdir: Option<&str>,
    namespace: &str,
    session_id: &str,
    agent_id: Option<&str>,
) -> Result<String> {
    let tmp = tempdir.ok_or(Abort("no temp dir"))?;
    let dir = join(tmp, namespace);
    let os = fsx::os_path(&dir).ok_or(Abort("unencodable temp dir"))?;
    std::fs::create_dir_all(os).map_err(|_| Abort("cannot create marker dir"))?;

    let who = match agent_id {
        Some(agent) => format!(".a{}", sanitize(Some(agent))),
        None => String::new(),
    };
    let name = format!(
        "{}.c{}{who}.json",
        sanitize(Some(session_id)),
        epoch(Some(tmp), Some(session_id))
    );
    Ok(join(&dir, &name))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sanitize_keeps_word_chars() {
        assert_eq!(sanitize(Some("a/b.c-d_\u{d55c}")), "abc-d_\u{d55c}");
        assert_eq!(sanitize(None), "nosession");
        assert_eq!(sanitize(Some("")), "nosession");
    }
}
