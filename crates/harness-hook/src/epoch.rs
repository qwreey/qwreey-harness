//! compact 회차(정본 `lib/compact_epoch.py`): 플러그인마다 자기 회차를 갖는다. 여기서는 읽는 쪽만 옮겼다.
//!
//! "세션당 한 번" 알림의 dedup 단위는 (session_id, agent_id 또는 main, 회차)다. compact 는 session_id 를 유지하면서
//! 이전 알림을 맥락에서 지우기 때문이다. 회차 파일은 `<임시 폴더>/claude-<plugin>-epoch/<sid>` 이고 PreCompact 의
//! python 훅(`compact_epoch.py <plugin>`)이 올린다.

use crate::py::fs::{self, FsError};
use crate::py::num::parse_int;
use crate::py::path::join;
use crate::py::unicode::is_word;

/// python `_sid(value)`: `str(value or "nosession")` 에서 단어 글자와 `-` 만 남긴다.
///
/// `text` 는 이미 python `str(value)` 한 글이다. 빈 글은 python 에서 거짓이라 `nosession` 이 된다.
pub fn sanitize(text: &str) -> String {
    let text = if text.is_empty() { "nosession" } else { text };
    text.chars()
        .filter(|&c| c == '-' || is_word(u32::from(c)))
        .collect()
}

/// 이 세션의 회차(python `epoch(plugin, session_id)`). 파일을 읽지 못하거나 정수가 아니면 0.
///
/// python `int()` 가 받지만 i128 을 넘는 값도 0 으로 본다(그런 회차는 쓰이지 않는다).
pub fn epoch(tempdir: &str, plugin: &str, session_id: &str) -> i128 {
    let dir = join(tempdir, &format!("claude-{}-epoch", sanitize(plugin)));
    match fs::read_text(&join(&dir, &sanitize(session_id))) {
        Ok(text) => parse_int(&text).unwrap_or(0),
        Err(_) => 0,
    }
}

/// 이 회차의 dedup 상태 파일 경로(python `state_path`): `<임시 폴더>/<namespace>/<sid>.c<회차>[.a<agent>].json`.
///
/// 폴더를 만든다. 만들지 못하면 python 은 예외로 끝나므로 그 오류를 돌려준다. `agent_id` 는 python 에서 참인 값의 `str()` 이다.
pub fn state_path(
    tempdir: &str,
    plugin: &str,
    namespace: &str,
    session_id: &str,
    agent_id: Option<&str>,
) -> Result<String, FsError> {
    let dir = join(tempdir, namespace);
    let os = fs::os_path(&dir).ok_or(FsError::Value)?;
    std::fs::create_dir_all(os).map_err(|e| FsError::Os(e.kind()))?;

    let who = match agent_id {
        Some(agent) => format!(".a{}", sanitize(agent)),
        None => String::new(),
    };
    let name = format!(
        "{}.c{}{who}.json",
        sanitize(session_id),
        epoch(tempdir, plugin, session_id)
    );
    Ok(join(&dir, &name))
}

#[cfg(test)]
mod tests {
    use super::*;

    /// id 에서 단어 글자와 `-` 만 남기고, 빈 id 는 nosession 이다.
    #[test]
    fn sanitize_keeps_word_chars() {
        assert_eq!(sanitize("a/b.c-d_\u{d55c}"), "abc-d_\u{d55c}");
        assert_eq!(sanitize(""), "nosession");
    }

    /// 플러그인의 회차 파일을 읽어 상태 파일 이름에 넣는다.
    #[test]
    fn reads_the_plugin_epoch() {
        let tmp = std::env::temp_dir().join(format!("hh-epoch-{}", std::process::id()));
        let tmp = tmp.to_str().unwrap().to_owned();
        let dir = join(&tmp, "claude-p-epoch");
        std::fs::create_dir_all(&dir).unwrap();
        std::fs::write(join(&dir, "s1"), " 3\n").unwrap();
        assert_eq!(epoch(&tmp, "p", "s1"), 3);
        assert_eq!(epoch(&tmp, "p", "s2"), 0);
        assert_eq!(
            state_path(&tmp, "p", "ns", "s1", Some("a/1")).unwrap(),
            join(&join(&tmp, "ns"), "s1.c3.aa1.json")
        );
        std::fs::remove_dir_all(&tmp).unwrap();
    }
}
