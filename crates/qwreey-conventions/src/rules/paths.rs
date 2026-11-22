//! rules-inject 가 보는 경로와 저장소 설정(python `rules_inject` 의 `project_root`, `skipped_dir`, `should_skip`, `repo_config`).

use harness_hook::py::fs;
use harness_hook::py::json_load::loads;
use harness_hook::py::path::{join, normpath};
use harness_hook::py::surrogate::from_os;
use harness_hook::py::value::{Dict, Value};

use crate::context::Context;
use crate::halt::{Halt, Result};
use crate::pyval::dict_or_empty;

/// 이 폴더 아래 파일에는 rule 을 넣지 않는다(python `SKIP_DIRS`): 의존성, 산출물, 캐시.
pub const SKIP_DIRS: &[&str] = &[
    "node_modules",
    ".git",
    "dist",
    "build",
    ".venv",
    "vendor",
    "__pycache__",
];

/// python `project_root(data)`: `$CLAUDE_PROJECT_DIR`, 없으면 입력의 `cwd`, 없으면 지금 폴더.
///
/// `cwd` 가 글이 아닌 참값이면 python 은 뒤의 경로 함수에서 예외로 끝난다.
pub fn project_root(ctx: &Context, cwd: Option<&Value>) -> Result<String> {
    if let Some(dir) = ctx.hook.env.get_nonempty("CLAUDE_PROJECT_DIR") {
        return Ok(dir.to_owned());
    }
    match cwd {
        Some(Value::Str(c)) if !c.is_empty() => Ok(c.clone()),
        Some(v) if v.truthy() => Err(Halt::PyError("cwd is not a string")),
        _ => getcwd(),
    }
}

/// python `os.getcwd()`.
pub fn getcwd() -> Result<String> {
    std::env::current_dir()
        .map(|d| from_os(d.as_os_str()))
        .map_err(|_| Halt::PyError("os.getcwd failed"))
}

// root 를 끝 `/` 하나로(python `root.rstrip("/") + "/"`)
fn dir_prefix(root: &str) -> String {
    format!("{}/", root.trim_end_matches('/'))
}

/// python `skipped_dir(abs_path, root)`: 의존성이나 산출물 폴더 아래인가.
///
/// 프로젝트 안이면 프로젝트 기준 경로의 폴더만 본다(상위 폴더 이름 `/home/build` 에 걸리지 않게).
pub fn skipped_dir(abs_path: &str, root: &str) -> bool {
    let p = normpath(abs_path);
    let r = dir_prefix(root);
    let tail = p.strip_prefix(r.as_str()).unwrap_or(&p);
    let parts: Vec<&str> = tail.split('/').collect();
    parts[..parts.len() - 1]
        .iter()
        .any(|x| SKIP_DIRS.contains(x))
}

/// python `is_memory_path(abs_path)`: 설정 디렉터리의 `projects/<p>/memory/...` 인가.
fn is_memory_path(ctx: &Context, abs_path: &str) -> bool {
    let base = format!(
        "{}/",
        join(
            &normpath(&crate::plugins::config_dir(&ctx.hook.env)),
            "projects"
        )
    );
    let p = normpath(abs_path);
    let Some(tail) = p.strip_prefix(base.as_str()) else {
        return false;
    };
    let parts: Vec<&str> = tail.split('/').collect();
    parts.len() >= 3 && parts[1] == "memory"
}

/// python `should_skip(tool, abs_path, root)`: 건너뛸 폴더 아래이거나, 프로젝트 밖을 Read 했다(설정 디렉터리의 메모리는 넣는다).
pub fn should_skip(ctx: &Context, tool: Option<&Value>, abs_path: &str, root: &str) -> bool {
    if skipped_dir(abs_path, root) {
        return true;
    }
    if tool.and_then(Value::as_str) == Some("Read") {
        let inside = normpath(abs_path).starts_with(&dir_prefix(root));
        return !inside && !is_memory_path(ctx, abs_path);
    }
    false
}

/// python `repo_config(root)`: 저장소 `.claude/conventions.json`, 없으면 `.claude/comments.json`.
///
/// 먼저 있는 파일 하나만 본다. 읽지 못하거나(일반 파일이 아닌 FIFO 등 포함) dict 가 아니면 빈 dict.
pub fn repo_config(root: &str) -> Dict {
    for name in ["conventions.json", "comments.json"] {
        let fp = join(&join(root, ".claude"), name);
        if fs::exists(&fp) {
            return fs::read_regular_text(&fp)
                .ok()
                .and_then(|t| loads(&t).ok())
                .and_then(|v| v.into_dict().ok())
                .unwrap_or_default();
        }
    }
    Dict::new()
}

/// python `excluded(root)`: 저장소 설정 `rules_exclude` 의 이름들(목록일 때만).
///
/// 목록이나 dict 원소는 python `set()` 이 TypeError 로 끝나는 자리다. 글이 아닌 원소는 rule 이름과 같을 수 없어 뺀다.
pub fn excluded(root: &str) -> Result<Vec<String>> {
    let cfg = repo_config(root);
    let Some(Value::List(items)) = cfg.get("rules_exclude") else {
        return Ok(Vec::new());
    };
    if items
        .iter()
        .any(|v| matches!(v, Value::List(_) | Value::Dict(_)))
    {
        return Err(Halt::PyError("rules_exclude has an unhashable item"));
    }
    Ok(items
        .iter()
        .filter_map(Value::as_str)
        .map(str::to_owned)
        .collect())
}

/// 입력에서 편집한 경로(python `next(ti[k] for k in PATH_KEYS if isinstance(ti.get(k), str) and ti.get(k))`).
pub fn edited_path(tool_input: Option<&Value>) -> Result<Option<String>> {
    let ti = dict_or_empty(tool_input)?;
    Ok(["file_path", "notebook_path"]
        .iter()
        .find_map(|k| match ti.and_then(|d| d.get(k)) {
            Some(Value::Str(s)) if !s.is_empty() => Some(s.clone()),
            _ => None,
        }))
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 프로젝트 안은 상대 경로의 폴더만, 밖은 모든 폴더를 본다.
    #[test]
    fn skipped_dirs_inside_and_outside() {
        assert!(skipped_dir("/p/node_modules/x.ts", "/p"));
        assert!(!skipped_dir("/home/build/p/x.ts", "/home/build/p"));
        assert!(skipped_dir("/elsewhere/build/x.ts", "/p"));
        assert!(!skipped_dir("/p/build", "/p"));
    }
}
