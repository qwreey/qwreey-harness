//! 백그라운드 작업 하나의 진척 신호: 출력 파일의 크기와 수정 시각(python `signal`, `task_output_paths`, `task_roots`).
//!
//! 서브에이전트는 트랜스크립트(`<메인 트랜스크립트 디렉터리>/<sid>/subagents/**/agent-<id>.jsonl`), 그 밖의 작업(셸 등)은
//! Claude Code 가 쓰는 `<tmp>/claude-<uid>/<프로젝트 키>/<sid>/tasks/<id>.output` 이다. 신호를 못 찾으면 `None`.

use harness_hook::HookEnv;
use harness_hook::epoch::sanitize;
use harness_hook::py::fs::{FsError, listdir, os_path, stat};
use harness_hook::py::path::{basename, dirname, join, splitext};
use harness_hook::py::repr::truthy_str;
use harness_hook::py::value::{Dict, Value};

use crate::stop::{Result, Stop};

/// 출력 파일 하나의 상태(python `[st_size, st_mtime, 경로 또는 None]`).
#[derive(Clone, Debug, PartialEq)]
pub struct Signal {
    pub size: u64,
    /// python `st_mtime`(초, float).
    pub mtime: f64,
    /// 알림에 실을 출력 경로. 서브에이전트의 트랜스크립트는 모델이 읽을 것이 아니라 `None`.
    pub path: Option<String>,
}

impl Signal {
    /// 상태 파일에 쓰는 꼴 `[size, mtime, path]`.
    pub fn value(&self) -> Value {
        Value::List(vec![
            Value::Int(i128::from(self.size)),
            Value::Float(self.mtime),
            self.path.clone().map_or(Value::Null, Value::Str),
        ])
    }
}

/// python `signal(task, data)`: 후보 경로 가운데 처음 stat 되는 것의 신호.
pub fn signal(hook: &HookEnv, task: &Dict, input: &Dict, tempdir: &str) -> Result<Option<Signal>> {
    let tid = word_chars(&truthy_str(task.get("id")));
    let sub = task.get("type").and_then(Value::as_str) == Some("subagent");

    // Paths the task names, then the transcript, then Claude Code's task output
    let mut paths: Vec<String> = ["output_file", "outputFile", "output_path"]
        .iter()
        .filter_map(|k| task.get(k).and_then(Value::as_str).map(str::to_owned))
        .collect();
    let transcript = input.get("transcript_path").filter(|v| v.truthy());
    if let Some(tp) = transcript
        && !tid.is_empty()
        && sub
    {
        let Value::Str(tp) = tp else {
            return Err(Stop::Raises("os.path.splitext of a value that is not text"));
        };
        let base = join(splitext(tp).0, "subagents");
        let name = format!("agent-{tid}.jsonl");
        paths.push(join(&base, &name));
        paths.extend(glob_dirs(&join(&base, "workflows"), &name)?);
    }
    paths.extend(task_output_paths(hook, &tid, input, tempdir)?);

    // The first path that stats
    for path in paths {
        match stat(&path) {
            Ok(st) => {
                return Ok(Some(Signal {
                    size: st.size,
                    mtime: st_mtime(st.mtime_ns),
                    path: (!sub).then_some(path),
                }));
            }
            Err(FsError::Os(_)) => continue,
            Err(FsError::Value) => return Err(Stop::Raises("os.stat of a path with NUL")),
        }
    }
    Ok(None)
}

// python re.sub(r"[^\w-]", "", text): 빈 글은 그대로(sanitize 는 빈 글을 nosession 으로 바꾼다)
fn word_chars(text: &str) -> String {
    if text.is_empty() {
        String::new()
    } else {
        sanitize(text)
    }
}

// CPython fill_time: sec + nsec * 1e-9
fn st_mtime(mtime_ns: i128) -> f64 {
    let sec = mtime_ns.div_euclid(1_000_000_000);
    let nsec = mtime_ns.rem_euclid(1_000_000_000);
    sec as f64 + nsec as f64 * 1e-9
}

/// python `glob.glob(join(dir, "*", name))`: `dir` 아래 숨기지 않은 폴더마다 `name` 이 있으면(깨진 링크도) 그 경로.
///
/// 차례는 폴더를 읽은 차례다. `dir` 에 glob 특수 글자가 있으면 python 은 그것을 패턴으로 읽는다: 옮기지 않았다.
fn glob_dirs(dir: &str, name: &str) -> Result<Vec<String>> {
    if has_magic(dir) {
        return Err(Stop::Unported("glob of a path with *, ? or ["));
    }
    let Ok(entries) = listdir(dir) else {
        return Ok(Vec::new());
    };
    Ok(entries
        .into_iter()
        .filter(|entry| !entry.starts_with('.'))
        .map(|entry| join(dir, &entry))
        .filter(|sub| harness_hook::py::fs::is_dir(sub))
        .map(|sub| join(&sub, name))
        .filter(|path| lexists(path))
        .collect())
}

fn has_magic(text: &str) -> bool {
    text.contains(['*', '?', '['])
}

// python os.path.lexists
fn lexists(path: &str) -> bool {
    os_path(path).is_some_and(|p| std::fs::symlink_metadata(p).is_ok())
}

/// python `task_output_paths(tid, data)`: Claude Code 가 쓴 작업 출력 파일 후보.
///
/// 작업 출력 루트마다 `claude-<uid>/<프로젝트 키>/<sid>/tasks/<tid>.output` 이 있으면 그 경로다.
fn task_output_paths(
    hook: &HookEnv,
    tid: &str,
    input: &Dict,
    tempdir: &str,
) -> Result<Vec<String>> {
    let sid = word_chars(&truthy_str(input.get("session_id")));
    let key = match input.get("transcript_path") {
        Some(Value::Str(tp)) => basename(dirname(tp)).to_owned(),
        _ => String::new(),
    };
    if tid.is_empty() || sid.is_empty() || key.is_empty() {
        return Ok(Vec::new());
    }

    // glob.escape makes these literal; a magic character would go through pattern matching
    let rel = join(
        &join(&join(&join(&owner(), &key), &sid), "tasks"),
        &format!("{tid}.output"),
    );
    let mut out = Vec::new();
    for root in task_roots(hook, tempdir) {
        if has_magic(&root) || has_magic(&key) {
            return Err(Stop::Unported("glob of a path with *, ? or ["));
        }
        let path = join(&root, &rel);
        if lexists(&path) {
            out.push(path);
        }
    }
    Ok(out)
}

// claude-<uid>(uid 가 없는 플랫폼의 claude-* 는 옮기지 않았다)
#[cfg(unix)]
fn owner() -> String {
    format!("claude-{}", rustix::process::getuid().as_raw())
}

#[cfg(not(unix))]
fn owner() -> String {
    "claude-*".to_owned()
}

/// python `task_roots()`: `$CLAUDE_CODE_TMPDIR`, 임시 폴더, `/tmp`(겹치면 한 번).
fn task_roots(hook: &HookEnv, tempdir: &str) -> Vec<String> {
    let mut roots: Vec<String> = Vec::new();
    let candidates = [
        hook.var("CLAUDE_CODE_TMPDIR"),
        Some(tempdir.to_owned()),
        Some("/tmp".to_owned()),
    ];
    for root in candidates.into_iter().flatten() {
        if !root.is_empty() && !roots.contains(&root) {
            roots.push(root);
        }
    }
    roots
}

#[cfg(test)]
mod tests {
    use super::*;

    /// st_mtime 은 초와 ns 를 python 처럼 float 로 합친다.
    #[test]
    fn mtime_like_cpython() {
        assert_eq!(
            st_mtime(1_700_000_000_123_456_789),
            1_700_000_000.0 + 123_456_789.0 * 1e-9
        );
        assert_eq!(st_mtime(-1), -1.0 + 999_999_999.0 * 1e-9);
    }

    /// id 의 단어 글자와 `-` 만 남기되, 빈 id 는 빈 글이다.
    #[test]
    fn word_chars_keep_empty() {
        assert_eq!(word_chars(""), "");
        assert_eq!(word_chars("a/b-1"), "ab-1");
        assert_eq!(word_chars("//"), "");
    }
}
