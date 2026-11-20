//! compact 회차(python `compact_epoch.py`, 정본 `lib/compact_epoch.py`의 읽는 쪽). 정의는 [`harness_hook::epoch`] 에 있다.
//!
//! "세션당 한 번" 알림의 dedup 단위는 (session_id, agent_id 또는 main, 회차)다. 회차 파일은
//! `<임시 폴더>/claude-qwreey-sessions-epoch/<sid>` 이고 PreCompact 의 python 훅이 올린다. 여기서는 읽기만 한다.

use harness_hook::epoch as shared;

use crate::abort::{Abort, Result};

/// 이 플러그인의 이름(회차 폴더 `claude-<이름>-epoch`).
const PLUGIN: &str = "qwreey-sessions";

/// python `_sid(value)`: `str(value or "nosession")` 에서 단어 글자와 `-` 만 남긴다. `value` 는 이미 `str()` 한 글이다.
pub fn sanitize(value: Option<&str>) -> String {
    shared::sanitize(value.unwrap_or(""))
}

/// 이 세션의 회차(python `epoch`). 임시 폴더가 없거나 파일을 읽지 못하면 0.
pub fn epoch(tempdir: Option<&str>, session_id: Option<&str>) -> i128 {
    let Some(tmp) = tempdir else { return 0 };
    shared::epoch(tmp, PLUGIN, session_id.unwrap_or(""))
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
    shared::state_path(tmp, PLUGIN, namespace, session_id, agent_id).map_err(|e| match e {
        harness_hook::py::fs::FsError::Value => Abort("unencodable temp dir"),
        harness_hook::py::fs::FsError::Os(_) => Abort("cannot create marker dir"),
    })
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
