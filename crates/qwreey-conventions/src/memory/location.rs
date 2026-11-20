//! auto memory 폴더인가(python `lib/memory_signals.py` 의 config_home, memory_dirs, is_memory_path).
//!
//! 기본 자리는 `<설정 디렉터리>/projects/<키>/memory/` 이고, settings.json 의 `autoMemoryDirectory`(절대 경로나 `~/`)가 더해진다.
//! 경로 비교는 pathlib 의 `relative_to` 처럼 정규화한 조각으로 한다.

use harness_hook::Env;
use harness_hook::py::fs;
use harness_hook::py::json_load::loads;
use harness_hook::py::path::{abspath, expanduser, pathlib_join, pathlib_str};
use harness_hook::py::value::Value;

/// python 이 예외로 끝나는 자리(훅은 그 예외를 잡아 조용히 끝난다).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Raised;

/// python `config_home()`: `$CLAUDE_CONFIG_DIR`, 없으면 홈의 `.claude`. 홈을 모르면 python 은 RuntimeError 다.
pub fn config_home(env: &Env) -> Result<String, Raised> {
    if let Some(dir) = env.get_nonempty("CLAUDE_CONFIG_DIR") {
        return Ok(pathlib_str(dir));
    }
    let home = expanduser("~", env);
    if home == "~" {
        return Err(Raised);
    }
    Ok(pathlib_join(&home, ".claude"))
}

/// python `memory_dirs(cwd)`: (기본 뿌리 `<config>/projects`, autoMemoryDirectory 들).
///
/// `cwd` 와 그 위 폴더마다 `.claude/` 가 있으면 그 settings.json 과 settings.local.json 도 읽는다. 글이 아닌 cwd 는 python 의 TypeError 다.
pub fn memory_dirs(cwd: Option<&Value>, env: &Env) -> Result<(String, Vec<String>), Raised> {
    let home = config_home(env)?;
    let mut files = vec![pathlib_join(&home, "settings.json")];

    // Settings next to the session folder and above it
    match cwd {
        Some(Value::Str(c)) if !c.is_empty() => {
            for d in with_parents(&pathlib_str(c)) {
                let claude = pathlib_join(&d, ".claude");
                if fs::is_dir(&claude) {
                    files.push(pathlib_join(&claude, "settings.json"));
                    files.push(pathlib_join(&claude, "settings.local.json"));
                }
            }
        }
        Some(v) if v.truthy() => return Err(Raised),
        _ => {}
    }

    // autoMemoryDirectory values that are absolute or under ~
    let mut extra = Vec::new();
    for f in &files {
        let parsed = fs::read_text(f).ok().and_then(|t| loads(&t).ok());
        let Some(Ok(settings)) = parsed.map(Value::into_dict) else {
            continue;
        };
        if let Some(Value::Str(v)) = settings.get("autoMemoryDirectory")
            && (v.starts_with('/') || v.starts_with("~/"))
        {
            extra.push(pathlib_str(&expanduser(v, env)));
        }
    }
    Ok((pathlib_join(&home, "projects"), extra))
}

/// python `is_memory_path(file_path, cwd)`: `file_path` 가 auto memory 폴더 안인가.
pub fn is_memory_path(file_path: &str, cwd: Option<&Value>, env: &Env) -> Result<bool, Raised> {
    let fp = pathlib_str(&abspath(&expanduser(file_path, env)).ok_or(Raised)?);
    let (root, custom) = memory_dirs(cwd, env)?;

    // <config>/projects/<key>/memory/...
    let root = pathlib_str(&abspath(&root).ok_or(Raised)?);
    if let Some(rel) = relative_to(&fp, &root)
        && rel.len() >= 3
        && rel[1] == "memory"
    {
        return Ok(true);
    }

    // Any custom memory folder
    for c in custom {
        let c = pathlib_str(&abspath(&c).ok_or(Raised)?);
        if relative_to(&fp, &c).is_some() {
            return Ok(true);
        }
    }
    Ok(false)
}

// pathlib 의 (앵커, 조각들): `//` 로 시작하면 앵커 `//`, `/` 면 `/`, 아니면 빈 앵커
fn split_anchor(path: &str) -> (&str, Vec<&str>) {
    let anchor = if path.starts_with("//") && !path.starts_with("///") {
        "//"
    } else if path.starts_with('/') {
        "/"
    } else {
        ""
    };
    let tail = path[anchor.len()..]
        .split('/')
        .filter(|p| !p.is_empty() && *p != ".")
        .collect();
    (anchor, tail)
}

// python Path(path).relative_to(base) 의 조각들(base 가 path 자신이거나 조상일 때만)
fn relative_to<'a>(path: &'a str, base: &str) -> Option<Vec<&'a str>> {
    let (anchor, parts) = split_anchor(path);
    let (base_anchor, base_parts) = split_anchor(base);
    if anchor != base_anchor
        || base_parts.len() > parts.len()
        || parts[..base_parts.len()] != base_parts[..]
    {
        return None;
    }
    Some(parts[base_parts.len()..].to_vec())
}

// python [p, *p.parents]: pathlib 꼴 경로와 그 부모들(앵커까지, 상대 경로는 `.` 앞까지)
fn with_parents(path: &str) -> Vec<String> {
    let (anchor, parts) = split_anchor(path);
    let mut out = Vec::new();
    for end in (0..=parts.len()).rev() {
        let joined = format!("{anchor}{}", parts[..end].join("/"));
        out.push(if joined.is_empty() {
            ".".to_owned()
        } else {
            joined
        });
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    /// relative_to 는 같은 앵커의 조상만 받는다.
    #[test]
    fn relative_to_like_pathlib() {
        // An ancestor gives the remaining parts
        assert_eq!(
            relative_to("/c/projects/k/memory/x.md", "/c/projects"),
            Some(vec!["k", "memory", "x.md"])
        );
        assert_eq!(relative_to("/c/projects", "/c/projects"), Some(vec![]));

        // A sibling prefix or another anchor is not an ancestor
        assert_eq!(relative_to("/c/projectsx/a", "/c/projects"), None);
        assert_eq!(relative_to("//c/a", "/c"), None);
    }

    /// 부모 목록은 pathlib 의 parents 와 같다.
    #[test]
    fn parents_like_pathlib() {
        // Absolute paths stop at the root, relative ones at "."
        assert_eq!(with_parents("/a/b"), vec!["/a/b", "/a", "/"]);
        assert_eq!(with_parents("a/b"), vec!["a/b", "a", "."]);
        assert_eq!(with_parents("."), vec!["."], "Path('.').parents is empty");
    }
}
