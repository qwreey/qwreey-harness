//! compact 회차(python `compact_epoch.py`, 정본 `lib/compact_epoch.py`)의 읽는 쪽과 회차별 상태 파일 경로.
//!
//! 회차 파일은 `<임시 폴더>/claude-<plugin>-epoch/<sid>` 이고 PreCompact 의 python 훅이 올린다. 여기서는 읽기만 한다.

use harness_hook::py::num::parse_int;
use harness_hook::py::path::join;
use harness_hook::py::unicode::is_word;

use crate::abort::{Abort, Result};
use crate::pylib::fs::{makedirs, read_text};

/// python `_sid(value)`(정규식 `[^\w-]` 지우기). `value` 는 `str(value or "nosession")` 한 글이다.
pub fn sanitize(value: &str) -> String {
    let text = if value.is_empty() { "nosession" } else { value };
    text.chars()
        .filter(|&c| c == '-' || is_word(u32::from(c)))
        .collect()
}

/// 이 세션의 회차(python `epoch(plugin, session_id)`). 파일을 읽지 못하면 0.
///
/// python `int()` 가 받지만 i128 을 넘는 값도 0 으로 본다(그런 회차는 쓰이지 않는다).
pub fn epoch(tempdir: &str, plugin: &str, session_id: &str) -> i128 {
    let dir = join(
        tempdir,
        &format!("claude-{}-epoch", sanitize_plugin(plugin)),
    );
    match read_text(&join(&dir, &sanitize(session_id))) {
        Ok(text) => parse_int(&text).unwrap_or(0),
        Err(_) => 0,
    }
}

// python `_plugin(plugin)`: 빈 글을 nosession 으로 바꾸지 않는다
fn sanitize_plugin(plugin: &str) -> String {
    plugin
        .chars()
        .filter(|&c| c == '-' || is_word(u32::from(c)))
        .collect()
}

/// python `state_path(plugin, namespace, session_id)`: `<임시 폴더>/<namespace>/<sid>.c<회차>.json`. 폴더를 만든다.
pub fn state_path(
    tempdir: &str,
    plugin: &str,
    namespace: &str,
    session_id: &str,
) -> Result<String> {
    let dir = join(tempdir, namespace);
    makedirs(&dir).map_err(|_| Abort("cannot create the state folder"))?;
    let name = format!(
        "{}.c{}.json",
        sanitize(session_id),
        epoch(tempdir, plugin, session_id)
    );
    Ok(join(&dir, &name))
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 세션 id 에서 단어 글자와 `-` 만 남기고, 빈 id 는 nosession 이다.
    #[test]
    fn sanitize_keeps_word_chars() {
        assert_eq!(sanitize("a/b.c-d_\u{d55c}"), "abc-d_\u{d55c}");
        assert_eq!(sanitize(""), "nosession");
    }
}
