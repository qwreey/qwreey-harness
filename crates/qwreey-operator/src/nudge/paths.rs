//! 이 도구 호출이 쓴 코드 파일(python `written_paths`, `is_code`).

use std::sync::LazyLock;

use harness_hook::HookEnv;
use harness_hook::py::repr::truthy_str;
use harness_hook::py::text::strip;
use harness_hook::py::value::{Dict, Value};
use harness_hook::rx::Regex;

use super::bash;
use crate::stop::{Result, Stop};

/// 파일을 쓰는 도구(python `WRITE_TOOLS`).
pub const WRITE_TOOLS: &[&str] = &["Edit", "Write", "MultiEdit", "NotebookEdit"];
/// 코드로 세지 않는 확장자(python `NONCODE`).
const NONCODE: &[&str] = &[
    "md", "json", "toml", "yaml", "yml", "txt", "log", "out", "csv", "lock", "tmp",
];

static EXT: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"\.([A-Za-z0-9]{1,6})$"));

/// 이 호출이 쓴 코드 경로들. 쓰는 도구는 입력 값 그대로(python 은 `str()` 로만 판정한다), Bash 는 찾은 글이다.
///
/// `tool` 은 이미 글인 도구 이름이다. python 은 `tool_input` 이 dict 가 아닌 참 값이면 `.get` 에서, Bash 의 `command` 가
/// 글이 아닌 참 값이면 정규식에서 예외로 끝난다.
pub fn written_paths(hook: &HookEnv, tool: &str, input: &Dict) -> Result<Vec<Value>> {
    let empty = Dict::new();
    let tool_input = match input.get("tool_input") {
        Some(Value::Dict(d)) => d,
        Some(v) if v.truthy() => return Err(Stop::Raises("tool_input.get on a non-dict")),
        _ => &empty,
    };

    // File tools: the path value itself
    if WRITE_TOOLS.contains(&tool) {
        let path = tool_input
            .get("file_path")
            .filter(|v| v.truthy())
            .or_else(|| tool_input.get("notebook_path"));
        return Ok(match path {
            Some(p) if is_code(hook, Some(p))? => vec![p.clone()],
            _ => Vec::new(),
        });
    }

    // Bash: candidates from the command text
    if tool != "Bash" {
        return Ok(Vec::new());
    }
    let command = match tool_input.get("command") {
        Some(Value::Str(cmd)) => cmd.as_str(),
        Some(v) if v.truthy() => return Err(Stop::Raises("re.sub on a non-text command")),
        _ => "",
    };
    let mut out = Vec::new();
    for found in bash::candidates(command) {
        if is_code(hook, Some(&Value::Str(found.clone())))? {
            out.push(Value::Str(strip_quotes(&found).to_owned()));
        }
    }
    Ok(out)
}

/// python `is_code(path)`: 코드 파일 경로로 보이나. `/dev/`, 임시 폴더, 코드가 아닌 확장자는 아니다.
pub fn is_code(hook: &HookEnv, path: Option<&Value>) -> Result<bool> {
    let text = truthy_str(path);
    let p = strip_quotes(strip(&text));
    if p.is_empty() || p.starts_with("/dev/") {
        return Ok(false);
    }

    // Temporary folders
    let tempdir = hook
        .tempdir()
        .ok_or(Stop::Raises("tempfile.gettempdir() found no folder"))?;
    let tmp_prefix = format!("{}/", tempdir.trim_end_matches('/'));
    if p == "/tmp" || p.starts_with("/tmp/") || p.starts_with(&tmp_prefix) {
        return Ok(false);
    }

    // A short extension that is not in the non-code list
    Ok(EXT.search(p).and_then(|m| m.text(p, 1)).is_some_and(|ext| {
        let ext = ext.to_ascii_lowercase();
        !NONCODE.contains(&ext.as_str())
    }))
}

// python `p.strip("\"'")`
fn strip_quotes(text: &str) -> &str {
    text.trim_matches(['"', '\''])
}

#[cfg(test)]
mod tests {
    use super::*;
    use harness_hook::Env;

    fn hook() -> HookEnv {
        HookEnv::new(Env::from_pairs([("TMPDIR", std::env::temp_dir())]), None)
    }

    /// 확장자가 코드인지, 따옴표와 공백을 떼고 본다. `/dev/` 와 `/tmp` 아래는 코드가 아니다.
    #[test]
    fn code_paths_like_python() {
        let code = |p: &str| is_code(&hook(), Some(&Value::Str(p.into()))).unwrap();
        assert!(code(" 'src/a.PY' "));
        assert!(code("a.py\n"));
        assert!(!code("notes.md"));
        assert!(!code("a.toolong7"));
        assert!(!code("/dev/null"));
        assert!(!code("/tmp/x/a.py"));
        assert!(code("/home/x/a.py"));
        assert!(is_code(&hook(), Some(&Value::Float(1.5))).unwrap());
        assert!(!is_code(&hook(), Some(&Value::Int(0))).unwrap());
    }
}
