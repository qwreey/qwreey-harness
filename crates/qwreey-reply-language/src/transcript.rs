//! 메인 대화 transcript 읽기(python `last_user_prompt`, `read_new_lines`, `interim_texts`).
//!
//! 줄마다 python `json.loads(bytes)` 로 읽는다([`crate::pyval::loads_bytes`]). 읽지 못한 줄은 건너뛰고, 객체가 아닌 줄처럼
//! python 이 예외를 내는 꼴은 [`Abort`] 다(훅 전체가 아무것도 내지 않고 끝난다).

use std::io::{Read, Seek, SeekFrom};

use harness_hook::py::fs::os_path;
use harness_hook::py::value::{Dict, Value};

use crate::pyval::{Abort, Num, Result, loads_bytes};

const PROMPT_TAIL_BYTES: u64 = 1_000_000;
const FIRST_READ_BYTES: i128 = 200_000;

fn flag(d: &Dict, key: &str) -> bool {
    d.get(key).is_some_and(Value::truthy)
}

// 한 줄을 객체로. 읽지 못하면 None, 객체가 아니면 python 의 AttributeError
fn record(raw: &[u8]) -> Result<Option<Dict>> {
    match loads_bytes(raw) {
        None => Ok(None),
        Some(value) => value
            .into_dict()
            .map(Some)
            .map_err(|_| Abort("transcript line is not an object")),
    }
}

// (j.get("message") or {}).get("content")
fn content(rec: &Dict) -> Result<Option<&Value>> {
    match rec.get("message").filter(|v| v.truthy()) {
        None => Ok(None),
        Some(Value::Dict(m)) => Ok(m.get("content")),
        Some(_) => Err(Abort("message has no get")),
    }
}

// b.get("text") or "": 글이 아닌 참 값은 python 이 잇거나 검사하다 예외로 끝난다
fn block_text(block: &Dict) -> Result<&str> {
    match block.get("text").filter(|v| v.truthy()) {
        None => Ok(""),
        Some(Value::Str(s)) => Ok(s),
        Some(_) => Err(Abort("text is not a string")),
    }
}

/// python `last_user_prompt(path)`: 끝 1 MB 안의 가장 최근 실제 사용자 프롬프트. 도구 결과, 메타, 서브에이전트 항목은 건너뛴다.
pub fn last_user_prompt(path: &str) -> Result<Option<String>> {
    let Some(os) = os_path(path) else {
        return Err(Abort("transcript path cannot be encoded"));
    };
    let Ok((start, chunk)) = read_from_end(&os, PROMPT_TAIL_BYTES) else {
        return Ok(None);
    };

    let mut lines: Vec<&[u8]> = chunk.split(|&b| b == b'\n').collect();
    if start > 0 {
        lines.remove(0);
    }
    for raw in lines.into_iter().rev() {
        let Some(rec) = record(raw)? else { continue };
        if rec.get("type").and_then(Value::as_str) != Some("user")
            || flag(&rec, "isSidechain")
            || flag(&rec, "isMeta")
        {
            continue;
        }
        let text = match content(&rec)? {
            Some(Value::List(blocks)) => {
                let dicts: Vec<&Dict> = blocks.iter().filter_map(Value::as_dict).collect();
                if dicts
                    .iter()
                    .any(|b| b.get("type").and_then(Value::as_str) == Some("tool_result"))
                {
                    continue;
                }
                let mut parts = Vec::new();
                for b in dicts
                    .iter()
                    .filter(|b| b.get("type").and_then(Value::as_str) == Some("text"))
                {
                    parts.push(block_text(b)?);
                }
                parts.join(" ")
            }
            Some(Value::Str(s)) => s.clone(),
            _ => continue,
        };
        if !harness_hook::py::text::strip(&text).is_empty() {
            return Ok(Some(text));
        }
    }
    Ok(None)
}

fn read_from_end(path: &std::path::Path, tail: u64) -> std::io::Result<(u64, Vec<u8>)> {
    let mut file = std::fs::File::open(path)?;
    let size = file.metadata()?.len();
    let start = size.saturating_sub(tail);
    file.seek(SeekFrom::Start(start))?;
    let mut chunk = Vec::new();
    file.read_to_end(&mut chunk)?;
    Ok((start, chunk))
}

/// python `read_new_lines(path, st)` 의 결과: 완결된 새 줄과 바뀐 오프셋.
pub struct NewLines {
    pub lines: Vec<Vec<u8>>,
    /// 상태의 `offset` 에 쓸 값. python 이 파일을 읽지 못한 경우는 `None`(오프셋을 그대로 둔다).
    pub offset: Option<Num>,
}

/// python `read_new_lines`: 오프셋부터 개행으로 끝난 줄만. 처음(또는 파일이 줄었으면)은 끝 200 KB 만 보고 잘린 첫 줄을 버린다.
///
/// `offset` 은 상태의 값이다. python 이 `seek` 에서 TypeError 를 내는 값(float, 글 등)은 [`Abort`].
pub fn read_new_lines(path: &str, offset: Option<&Value>) -> Result<NewLines> {
    let unread = NewLines {
        lines: Vec::new(),
        offset: None,
    };
    let Some(os) = os_path(path) else {
        return Err(Abort("transcript path cannot be encoded"));
    };
    let Ok(size) = std::fs::metadata(&os).map(|m| i128::from(m.len())) else {
        return Ok(unread);
    };

    // Where to start: the stored offset, or the tail on first read
    let stored = match offset {
        None | Some(Value::Null) => None,
        Some(Value::Int(n)) => Some(*n),
        Some(Value::Bool(b)) => Some(i128::from(*b)),
        // python: a float or huge int past the end resets; one inside makes seek() raise
        Some(Value::Float(f)) if *f > size as f64 => None,
        Some(Value::BigInt(d)) if !d.starts_with('-') => None,
        Some(Value::BigInt(_)) => return Ok(unread),
        Some(_) => return Err(Abort("offset is not an int")),
    };
    let (off, skip_first) = match stored {
        Some(off) if off <= size => (off, false),
        _ => {
            let off = (size - FIRST_READ_BYTES).max(0);
            (off, off > 0)
        }
    };
    // python f.seek(음수) 는 OSError 다
    let Ok(start) = u64::try_from(off) else {
        return Ok(unread);
    };
    let Ok(chunk) = read_at(&os, start) else {
        return Ok(unread);
    };

    // Only complete lines; the offset moves past them
    let Some(end) = chunk.iter().rposition(|&b| b == b'\n') else {
        return Ok(NewLines {
            lines: Vec::new(),
            offset: Some(Num::Int(off)),
        });
    };
    let complete = &chunk[..=end];
    let mut lines: Vec<Vec<u8>> = complete[..end]
        .split(|&b| b == b'\n')
        .map(<[u8]>::to_vec)
        .collect();
    if skip_first && !lines.is_empty() {
        lines.remove(0);
    }
    Ok(NewLines {
        lines,
        offset: Some(Num::Int(off + complete.len() as i128)),
    })
}

fn read_at(path: &std::path::Path, start: u64) -> std::io::Result<Vec<u8>> {
    let mut file = std::fs::File::open(path)?;
    file.seek(SeekFrom::Start(start))?;
    let mut chunk = Vec::new();
    file.read_to_end(&mut chunk)?;
    Ok(chunk)
}

/// python `interim_texts(lines)`: 메인 대화의 assistant 글 블록들(서브에이전트 항목은 뺀다).
pub fn interim_texts(lines: &[Vec<u8>]) -> Result<Vec<String>> {
    let mut out = Vec::new();
    for raw in lines {
        let Some(rec) = record(raw)? else { continue };
        if rec.get("type").and_then(Value::as_str) != Some("assistant") || flag(&rec, "isSidechain")
        {
            continue;
        }
        match content(&rec)? {
            Some(Value::List(blocks)) => {
                for b in blocks.iter().filter_map(Value::as_dict) {
                    if b.get("type").and_then(Value::as_str) == Some("text") {
                        out.push(block_text(b)?.to_owned());
                    }
                }
            }
            Some(Value::Str(s)) => out.push(s.clone()),
            _ => {}
        }
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn write(name: &str, text: &str) -> String {
        let dir = std::env::temp_dir().join(format!("qrl-transcript-{}", std::process::id()));
        std::fs::create_dir_all(&dir).expect("temp dir");
        let path = dir.join(name);
        std::fs::write(&path, text).expect("write");
        path.to_string_lossy().into_owned()
    }

    /// 마지막 사용자 프롬프트: 도구 결과, 메타, 서브에이전트 줄은 건너뛰고 글 블록을 잇는다.
    #[test]
    fn last_prompt_skips_tool_results() {
        let path = write(
            "a.jsonl",
            concat!(
                r#"{"type": "user", "message": {"content": [{"type": "text", "text": "첫"}, {"type": "text", "text": "질문"}]}}"#,
                "\n",
                r#"{"type": "user", "message": {"content": [{"type": "tool_result", "content": "x"}]}}"#,
                "\n",
                r#"{"type": "user", "isMeta": true, "message": {"content": "meta"}}"#,
                "\n",
                "not json\n",
            ),
        );
        assert_eq!(last_user_prompt(&path), Ok(Some("첫 질문".to_owned())));
    }

    /// 새 줄 읽기: 개행으로 끝난 줄까지만, 오프셋은 그 뒤로 옮긴다.
    #[test]
    fn new_lines_stop_at_the_last_newline() {
        let path = write("b.jsonl", "one\ntwo\nthr");
        let got = read_new_lines(&path, Some(&Value::Int(0))).expect("readable");
        assert_eq!(got.lines, [b"one".to_vec(), b"two".to_vec()]);
        assert_eq!(got.offset.map(|n| n.value()), Some(Value::Int(8)));
        assert!(
            read_new_lines(&path, Some(&Value::Float(1.0))).is_err(),
            "python seek(1.0) raises TypeError"
        );
    }
}
