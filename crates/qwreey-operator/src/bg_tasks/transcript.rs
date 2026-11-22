//! 서브에이전트 트랜스크립트에서 그 에이전트가 띄운 작업 찾기(python `tool_result_text`, `own_tasks`).
//!
//! 입력의 `background_tasks` 는 세션 전체의 작업이라 주인을 밝히는 필드가 없다. 그래서 서브에이전트의 tool_result 글에
//! id 가 나온 작업만 그 서브에이전트의 것으로 본다(Bash 백그라운드 결과는 "Command running in background with ID: <id>" 꼴).

use harness_hook::py::fs::{FsError, read_text_replace};
use harness_hook::py::json::{EnsureAscii, dumps};
use harness_hook::py::json_load;
use harness_hook::py::unicode::is_word;
use harness_hook::py::value::Value;

use crate::stop::{Result, Stop};

/// 트랜스크립트의 tool_result 글을 모두 줄바꿈으로 이은 것. 읽지 못하면 `None`.
///
/// 줄은 `"tool_result"` 가 든 것만 JSON 으로 읽고, 읽지 못하는 줄은 넘긴다. python 은 JSON 이지만 dict 가 아닌 줄,
/// dict 가 아닌 참 값의 `message`, 너무 깊은 줄에서 예외로 끝나 훅이 아무것도 내지 않는다.
pub fn tool_result_text(path: Option<&Value>) -> Result<Option<String>> {
    let Some(Value::Str(path)) = path.filter(|v| v.truthy()) else {
        return Ok(None);
    };
    let text = match read_text_replace(path) {
        Ok(text) => text,
        Err(FsError::Os(_)) => return Ok(None),
        Err(FsError::Value) => return Err(Stop::Raises("open() of a path with NUL")),
    };

    let mut parts = Vec::new();
    for line in text.split_inclusive('\n') {
        if !line.contains("\"tool_result\"") {
            continue;
        }
        let record = match json_load::loads(line) {
            Ok(record) => record,
            Err(e) if e.too_deep() => return Err(Stop::Raises("RecursionError on a deep line")),
            Err(_) => continue,
        };
        collect_results(&record, &mut parts)?;
    }
    Ok(Some(parts.join("\n")))
}

// 줄 하나의 message.content 에 든 tool_result 글
fn collect_results(record: &Value, parts: &mut Vec<String>) -> Result<()> {
    let Value::Dict(record) = record else {
        return Err(Stop::Raises("line.get on a non-dict"));
    };
    let content = match record.get("message").filter(|v| v.truthy()) {
        None => None,
        Some(Value::Dict(message)) => message.get("content"),
        Some(_) => return Err(Stop::Raises("message.get on a non-dict")),
    };
    let Some(Value::List(blocks)) = content else {
        return Ok(());
    };

    for block in blocks {
        let Value::Dict(block) = block else {
            continue;
        };
        if block.get("type").and_then(Value::as_str) != Some("tool_result") {
            continue;
        }
        parts.push(match block.get("content") {
            Some(Value::Str(text)) => text.clone(),
            Some(inner) => dumps(inner, EnsureAscii::No, None),
            None => "null".to_owned(),
        });
    }
    Ok(())
}

/// python `re.search(r"(?<![\w-])%s(?![\w-])" % re.escape(id), text)`: 앞뒤가 단어 글자나 `-` 가 아닌 자리에 id 가 있나.
pub fn mentions(text: &str, id: &str) -> bool {
    let joins = |c: Option<char>| c.is_some_and(|c| c == '-' || is_word(u32::from(c)));
    let mut from = 0;
    while let Some(off) = text[from..].find(id) {
        let start = from + off;
        let end = start + id.len();
        if !joins(text[..start].chars().next_back()) && !joins(text[end..].chars().next()) {
            return true;
        }
        from = start + text[start..].chars().next().map_or(1, char::len_utf8);
    }
    false
}

#[cfg(test)]
mod tests {
    use super::*;

    /// id 는 단어 글자나 `-` 에 붙어 있으면 세지 않는다.
    #[test]
    fn mentions_need_boundaries() {
        assert!(mentions("ID: b12x.", "b12x"));
        assert!(!mentions("ID: b12xy", "b12x"));
        assert!(!mentions("a-b12x", "b12x"));
        assert!(mentions("ab12x b12x", "b12x"));
        assert!(!mentions("\u{d55c}b12x", "b12x"));
    }
}
