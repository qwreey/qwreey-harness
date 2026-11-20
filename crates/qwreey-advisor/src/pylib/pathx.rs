//! `harness_hook::py::path` 에 없는 python 경로 함수: pathlib 의 `name`, `parent.name`.

use harness_hook::py::path::pathlib_str;

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
    }
}
