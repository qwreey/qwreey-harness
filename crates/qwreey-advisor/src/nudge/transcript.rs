//! 서브에이전트 transcript 와 옆의 `agent-<id>.meta.json` 읽기(python `review_record.read_meta`, `head_text`,
//! `run_caller`, `handback_notice.handback_message`).
//!
//! 읽는 양은 python 과 같다: 앞 64 Ki 글자, 첫 user 기록까지, 끝 512 KiB. python 이 잡는 예외는 빈 값, 잡지 않는 것은 [`Abort`].

use std::io::{Read, Seek, SeekFrom};

use harness_hook::py::text::splitlines;
use harness_hook::py::value::{Dict, Value};

use crate::abort::{Abort, Result};
use crate::hookio::{loads_object, parse_object};
use crate::pylib::fs::{FsError, TextLines, os_path, read_bytes};
use crate::pylib::text::{take_chars, universal_newlines};
use crate::track_reviewer::RUN_LINE;

const HEAD_CHARS: usize = 64 * 1024;
const TAIL_BYTES: u64 = 512 * 1024;

/// python `read_meta(tpath)`: `<transcript 이름>.meta.json` 의 객체. 없거나 읽지 못하면 빈 dict.
pub fn read_meta(tpath: &str) -> Dict {
    let Some(stem) = tpath.strip_suffix(".jsonl").filter(|_| !tpath.is_empty()) else {
        return Dict::new();
    };
    let Ok(bytes) = read_bytes(&format!("{stem}.meta.json")) else {
        return Dict::new();
    };
    parse_object(&bytes).unwrap_or_default()
}

/// python `head_text(tpath)`: 앞 64 Ki 글자(UTF-8, 틀린 바이트는 U+FFFD, 줄 끝 바꿈). 열지 못하면 빈 글.
///
/// 바꿀 수 없는 경로(NUL, 짝 없는 high 서로게이트)는 python 이 잡지 않는 ValueError 다.
pub fn head_text(tpath: &str) -> Result<String> {
    let os = os_path(tpath).ok_or(Abort("transcript path cannot be encoded"))?;
    let Ok(file) = std::fs::File::open(os) else {
        return Ok(String::new());
    };

    // Enough bytes for 64 Ki characters of any width, plus a pending \r\n
    let mut bytes = Vec::new();
    let limit = (HEAD_CHARS * 4 + 2) as u64;
    if file.take(limit).read_to_end(&mut bytes).is_err() {
        return Ok(String::new());
    }
    let text = universal_newlines(&String::from_utf8_lossy(&bytes));
    Ok(take_chars(&text, HEAD_CHARS).to_owned())
}

/// python `run_caller(tpath)`: 첫 user 기록의 마지막 run 줄의 호출자. 없거나 읽지 못하면 `None`.
///
/// python 이 잡지 않는 예외(글이 아닌 `text` 를 잇는 TypeError)는 [`Abort`] 다.
pub fn run_caller(tpath: &str) -> Result<Option<String>> {
    let Ok(mut lines) = TextLines::open(tpath) else {
        return Ok(None);
    };
    while let Some(line) = lines.next_line() {
        // Any unreadable line before the first user record ends the search
        let Ok(line) = line else {
            return Ok(None);
        };
        let Ok(rec) = loads_object(&line) else {
            return Ok(None);
        };
        if rec.get("type").and_then(Value::as_str) != Some("user") {
            continue;
        }

        // The first user record decides
        let content = match rec.get("message").filter(|v| v.truthy()) {
            None => None,
            Some(Value::Dict(message)) => message.get("content"),
            Some(_) => return Ok(None),
        };
        let text = match content {
            Some(Value::List(items)) => join_texts(items)?,
            Some(Value::Str(s)) => s.clone(),
            _ => String::new(),
        };
        let found = RUN_LINE.find_iter(&text);
        return Ok(found
            .last()
            .and_then(|m| m.text(&text, 2))
            .map(str::to_owned));
    }
    Ok(None)
}

// python "\n".join(x.get("text", "") for x in c if isinstance(x, dict))
fn join_texts(items: &[Value]) -> Result<String> {
    let mut parts = Vec::new();
    for item in items {
        let Value::Dict(d) = item else { continue };
        match d.get("text") {
            None => parts.push(""),
            Some(Value::Str(s)) => parts.push(s.as_str()),
            Some(_) => return Err(Abort("content text is not a string")),
        }
    }
    Ok(parts.join("\n"))
}

/// python `handback_message(tpath)`: transcript 끝 512 KiB 의 마지막 SubagentHandback 호출 입력(message). 없으면 빈 글.
pub fn handback_message(tpath: &str) -> Result<String> {
    let os = os_path(tpath).ok_or(Abort("transcript path cannot be encoded"))?;
    let Ok(text) = read_tail(&os) else {
        return Ok(String::new());
    };

    for line in splitlines(&text).into_iter().rev() {
        if !line.contains("\"SubagentHandback\"") {
            continue;
        }
        let rec = match loads_object(line) {
            Ok(rec) => rec,
            Err(Some(_)) => return Err(Abort("handback line is not an object")),
            Err(None) => continue,
        };
        if let Some(message) = handback_in(&rec)? {
            return Ok(message);
        }
    }
    Ok(String::new())
}

fn read_tail(path: &std::path::Path) -> std::result::Result<String, FsError> {
    let mut file = std::fs::File::open(path).map_err(|_| FsError::Os)?;
    let size = file.seek(SeekFrom::End(0)).map_err(|_| FsError::Os)?;
    file.seek(SeekFrom::Start(size.saturating_sub(TAIL_BYTES)))
        .map_err(|_| FsError::Os)?;
    let mut bytes = Vec::new();
    file.read_to_end(&mut bytes).map_err(|_| FsError::Os)?;
    Ok(String::from_utf8_lossy(&bytes).into_owned())
}

// 한 기록의 content 를 뒤에서부터 보아 SubagentHandback 호출의 message
fn handback_in(rec: &Dict) -> Result<Option<String>> {
    let content = match rec.get("message").filter(|v| v.truthy()) {
        None => None,
        Some(Value::Dict(message)) => message.get("content").filter(|v| v.truthy()),
        Some(_) => return Err(Abort("message has no get")),
    };
    let blocks: &[Value] = match content {
        None => &[],
        Some(Value::List(items)) => items,
        // python reversed() of a str or dict yields no dict blocks
        Some(Value::Str(_) | Value::Dict(_)) => &[],
        Some(_) => return Err(Abort("content is not iterable")),
    };

    for block in blocks.iter().rev() {
        let Value::Dict(b) = block else { continue };
        if b.get("type").and_then(Value::as_str) != Some("tool_use")
            || b.get("name").and_then(Value::as_str) != Some("SubagentHandback")
        {
            continue;
        }
        let message = match b.get("input").filter(|v| v.truthy()) {
            None => None,
            Some(Value::Dict(input)) => input.get("message").filter(|v| v.truthy()),
            Some(_) => return Err(Abort("input has no get")),
        };
        return match message {
            None => Ok(Some(String::new())),
            Some(v) => v
                .scalar_str()
                .map(Some)
                .ok_or(Abort("message is a list or dict")),
        };
    }
    Ok(None)
}
