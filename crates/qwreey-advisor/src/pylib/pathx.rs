//! `harness_hook::py::path` 에 없는 python 경로 함수: `os.path.basename`, `os.path.relpath`, pathlib 의 `name`.

use harness_hook::py::path::{abspath, pathlib_str};

/// python `os.path.basename(path)`: 마지막 `/` 뒤.
pub fn basename(path: &str) -> &str {
    path.rsplit('/').next().unwrap_or(path)
}

/// python `os.path.relpath(path, start)`. 현재 디렉터리를 읽지 못하면 `None`(python 은 OSError).
///
/// `path` 가 비면 python 은 ValueError 다. 부르는 곳은 늘 정리한 경로(빈 글이 아님)를 넘긴다.
pub fn relpath(path: &str, start: &str) -> Option<String> {
    let start_abs = abspath(start)?;
    let path_abs = abspath(path)?;
    let start_list = parts(&start_abs);
    let path_list = parts(&path_abs);

    // Shared head, then climb out of the rest of start
    let common = start_list
        .iter()
        .zip(&path_list)
        .take_while(|(a, b)| a == b)
        .count();
    let mut rel: Vec<&str> = vec![".."; start_list.len() - common];
    rel.extend_from_slice(&path_list[common..]);
    if rel.is_empty() {
        return Some(".".to_owned());
    }
    Some(rel.join("/"))
}

// python: abspath(p).lstrip("/").split("/"), 빈 글이면 빈 목록
fn parts(abs: &str) -> Vec<&str> {
    let tail = abs.trim_start_matches('/');
    if tail.is_empty() {
        Vec::new()
    } else {
        tail.split('/').collect()
    }
}

/// python `Path(path).name`: pathlib 이 정리한 마지막 조각(루트와 `.` 은 빈 글).
pub fn pathlib_name(path: &str) -> String {
    let clean = pathlib_str(path);
    components(&clean).last().copied().unwrap_or("").to_owned()
}

/// python `Path(path).parent.name`.
pub fn pathlib_parent_name(path: &str) -> String {
    let clean = pathlib_str(path);
    let parts = components(&clean);
    match parts.len() {
        0 | 1 => String::new(),
        n => parts[n - 2].to_owned(),
    }
}

fn components(clean: &str) -> Vec<&str> {
    clean
        .split('/')
        .filter(|p| !p.is_empty() && *p != ".")
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    /// relpath 는 공통 앞부분을 빼고 남은 start 만큼 `..` 로 올라간다.
    #[test]
    fn relpath_like_posixpath() {
        assert_eq!(relpath("/a/b/c", "/a").as_deref(), Some("b/c"));
        assert_eq!(relpath("/a", "/a/b").as_deref(), Some(".."));
        assert_eq!(relpath("/a", "/a").as_deref(), Some("."));
        assert_eq!(relpath("/x/y", "/a/b").as_deref(), Some("../../x/y"));
        assert_eq!(relpath("/", "/").as_deref(), Some("."));
    }

    /// pathlib 의 name 과 parent.name: 루트, 상대 경로 한 조각은 빈 글이다.
    #[test]
    fn pathlib_names() {
        assert_eq!(pathlib_parent_name("/code/repo/.git"), "repo");
        assert_eq!(pathlib_parent_name("/.git"), "", "the parent is the root");
        assert_eq!(
            pathlib_parent_name("a"),
            "",
            "the parent of a single part is `.`"
        );
        assert_eq!(pathlib_name("/code/repo/"), "repo");
        assert_eq!(pathlib_name("/"), "");
        assert_eq!(basename("a/b"), "b");
        assert_eq!(basename("git"), "git");
    }
}
