//! 모든 도구의 PostToolUse 가 지나가는 싼 길(python `quick_not_away`): JSON 을 읽기 전에 원문에서 session_id 만 뽑아
//! 원장의 away 표시를 본다.
//!
//! "확실히 away 가 아님"일 때만 참(그대로 끝)이다. 조금이라도 불확실하면 거짓이라 정상 길이 판단한다. python 판의 거친 글 찾기를
//! 그대로 옮겼다: 첫 `"session_id"` 뒤 `:` 다음의 따옴표 사이 글, 임시 폴더는 `$TMPDIR`, `$TEMP`, `$TMP`, `/tmp` 순서다.

use harness_hook::HookEnv;
use harness_hook::py::fs::{FsError, read_bytes};
use harness_hook::py::path::join;
use harness_hook::py::surrogate::decode_os;
use harness_hook::py::unicode::is_alnum;

use super::store::NAMESPACE;

/// 원장 파일이 UTF-8 이 아니다. python 은 이 자리에서 예외를 잡지 않아 traceback 과 종료 코드 1 로 끝난다.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Crash;

/// python `quick_not_away(raw)`.
pub fn not_away(hook: &HookEnv, raw: &[u8]) -> Result<bool, Crash> {
    if !contains(raw, b"\"PostToolUse\"")
        || contains(raw, b"\"Agent\"")
        || contains(raw, b"\"Task\"")
    {
        return Ok(false);
    }
    let Some(sid) = session_id(raw) else {
        return Ok(false);
    };

    // The ledger, if any, decides; a ledger without away on is cheap to rule out
    let tmp = ["TMPDIR", "TEMP", "TMP"]
        .iter()
        .find_map(|k| hook.var(k).filter(|v| !v.is_empty()))
        .unwrap_or_else(|| "/tmp".to_owned());
    let path = join(&join(&tmp, NAMESPACE), &format!("{sid}.json"));
    match read_bytes(&path) {
        Ok(bytes) => match std::str::from_utf8(&bytes) {
            Ok(text) => Ok(!text.contains("\"on\": true")),
            Err(_) => Err(Crash),
        },
        Err(FsError::Os(_)) => Ok(true),
        Err(FsError::Value) => Err(Crash),
    }
}

fn contains(hay: &[u8], needle: &[u8]) -> bool {
    hay.windows(needle.len()).any(|w| w == needle)
}

// python str.find(sub, start): 없으면 None
fn find(hay: &[u8], needle: u8, start: usize) -> Option<usize> {
    hay.get(start..)?
        .iter()
        .position(|&b| b == needle)
        .map(|i| start + i)
}

/// 원문의 session_id: 첫 `"session_id"` 뒤 첫 `:` 다음 따옴표부터 다음 따옴표 앞까지, 영숫자와 `_`, `-` 만. 비면 nosession.
///
/// 찾는 글이 모두 ASCII 라 바이트 자리로 찾아도 python 의 글자 자리와 같은 조각이 나온다.
fn session_id(raw: &[u8]) -> Option<String> {
    let key = b"\"session_id\"";
    let at = raw.windows(key.len()).position(|w| w == key)?;

    // python: j = raw.find('"', raw.find(":", i) + 1); a missing ":" searches from 0
    let colon = find(raw, b':', at);
    let open = find(raw, b'"', colon.map_or(0, |c| c + 1))?;
    let close = find(raw, b'"', open + 1)?;
    let inner = decode_os(&raw[open + 1..close]);
    let sid: String = inner
        .chars()
        .filter(|&c| is_alnum(c) || c == '_' || c == '-')
        .collect();
    Some(if sid.is_empty() {
        "nosession".to_owned()
    } else {
        sid
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 첫 session_id 의 따옴표 안 글에서 영숫자와 `_`, `-` 만 남긴다.
    #[test]
    fn session_id_like_python() {
        assert_eq!(
            session_id(b"{\"session_id\": \"a/b-1_\\u00e9\"}").as_deref(),
            Some("ab-1_u00e9")
        );
        assert_eq!(
            session_id("{\"session_id\": \"\u{e9}x\"}".as_bytes()).as_deref(),
            Some("\u{e9}x")
        );
        assert_eq!(
            session_id(br#"{"session_id": ""}"#).as_deref(),
            Some("nosession")
        );
        assert_eq!(session_id(br#"{"x": 1}"#), None);
        assert_eq!(session_id(br#"{"session_id": 5}"#), None);
    }
}
