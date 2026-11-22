//! 색인에 넣을 파일 고르기와 저장소 파일 목록(python reuse-check 의 `indexable`, `list_files`).
//!
//! git 이 되면 `git ls-files`(무시 규칙을 따른다), 아니면 python `os.walk` 와 같은 차례로 걷는다.

use std::ffi::OsString;
use std::sync::LazyLock;
use std::time::Duration;

use harness_hook::py::fs;
use harness_hook::py::path::{basename, dirname, join, relpath, splitext};
use harness_hook::py::re::Flags;
use harness_hook::py::surrogate::from_os;
use harness_hook::rx::Regex;

use crate::edit::{GEN_MARK_PATTERN, SKIP_PARTS, SKIP_SUFFIX};
use crate::git;

/// 규칙과 사본 검사를 거는 확장자(python `RULE_EXT`).
pub const RULE_EXT: &[&str] = &[
    ".luau", ".lua", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".astro", ".rs", ".py", ".go", ".kt",
];
/// 겹침(H1)을 보는 확장자(python `H1_EXT`).
pub const H1_EXT: &[&str] = &[
    ".luau", ".lua", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".rs", ".py",
];
/// JSON 파일(표시만 본다, python `JSON_EXT`).
pub const JSON_EXT: &[&str] = &[".json", ".jsonc"];
/// 경로에 이 조각이 있으면 보지 않는다(python `SKIP_DIRS` = `SKIP_PARTS` 와 시험, 예시 폴더).
const MORE_SKIP_DIRS: &[&str] = &[
    ".claude",
    "stories",
    "gallery",
    "examples",
    "tests",
    "test",
    "__tests__",
    "spec",
    "specs",
];
/// 걷기의 git 대신 쓰는 한도(python `subprocess.run(..., timeout=3)`).
const GIT_TIMEOUT: Duration = Duration::from_secs(3);

static TEST_FILE: LazyLock<Regex> = LazyLock::new(|| {
    Regex::with_flags(
        r"\.(spec|test|story)\.|_test\.|(^|/)test[-_]|tests\.rs$",
        Flags::IGNORECASE,
    )
});
static GEN: LazyLock<Regex> =
    LazyLock::new(|| Regex::with_flags(&format!("{GEN_MARK_PATTERN}|생성:"), Flags::IGNORECASE));

/// python `LANG.get(ext)`: 같은 언어끼리만 서로 import 할 수 있다.
pub fn lang(ext: &str) -> Option<&'static str> {
    Some(match ext {
        ".luau" | ".lua" => "luau",
        ".ts" | ".tsx" | ".js" | ".jsx" | ".mjs" | ".astro" => "ts",
        ".rs" => "rust",
        ".py" => "py",
        ".go" => "go",
        ".kt" => "kt",
        _ => return None,
    })
}

/// 경로의 소문자 확장자(python `os.path.splitext(p)[1].lower()`).
pub fn ext_of(path: &str) -> String {
    splitext(path).1.to_lowercase()
}

/// python `p in SKIP_DIRS`.
pub fn skip_dir(part: &str) -> bool {
    SKIP_PARTS.contains(&part) || MORE_SKIP_DIRS.contains(&part)
}

/// 머리 6줄에 생성 파일 표시(python `GEN`, `생성:` 포함)가 있는가.
pub fn generated(text: &str) -> bool {
    let head: Vec<&str> = text.splitn(7, '\n').take(6).collect();
    GEN.is_match(&head.join("\n"))
}

/// python `indexable(rel, vendored)`: 색인에 넣을 파일인가(경로만 본다).
pub fn indexable(rel: &str, vendored: &[String]) -> bool {
    if !RULE_EXT.contains(&ext_of(rel).as_str())
        || SKIP_SUFFIX.iter().any(|s| rel.ends_with(s))
        || TEST_FILE.is_match(rel)
    {
        return false;
    }
    let parts: Vec<&str> = rel.split('/').collect();
    let (last, dirs) = parts.split_last().unwrap_or((&"", &[]));
    if dirs.iter().any(|p| skip_dir(p) || p.contains("-ignoreme")) || last.contains("-ignoreme") {
        return false;
    }
    !vendored.iter().any(|v| rel.starts_with(v.as_str()))
}

/// python `list_files(root)`: 저장소의 코드 파일(루트 기준 상대 경로).
pub fn list_files(root: &str) -> Vec<String> {
    let names = if fs::exists(&join(root, ".git")) {
        git_ls_files(root)
    } else {
        None
    };
    let names = names.unwrap_or_else(|| walk(root));

    // vendor.lock.json 이 있는 폴더는 벤더 트리다
    let vendored: Vec<String> = names
        .iter()
        .filter(|n| basename(n) == "vendor.lock.json" && !dirname(n).is_empty())
        .map(|n| format!("{}/", dirname(n)))
        .collect();
    names
        .into_iter()
        .filter(|n| indexable(n, &vendored))
        .collect()
}

// `git -C root ls-files -z --cached --others --exclude-standard`. 실패, 0 이 아닌 종료, 3 초 넘김은 None(걷기로)
fn git_ls_files(root: &str) -> Option<Vec<String>> {
    let mut args = vec!["-C".into(), git::os_arg(root).ok()?];
    args.extend(
        [
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
        ]
        .map(OsString::from),
    );
    let out = git::output(&args, None, GIT_TIMEOUT)?;

    // python decode("utf-8", "replace") then split on NUL
    Some(
        String::from_utf8_lossy(&out)
            .split('\0')
            .filter(|n| !n.is_empty())
            .map(str::to_owned)
            .collect(),
    )
}

// python os.walk(root) 를 위에서부터, 디렉터리가 주는 순서로. 건너뛸 폴더는 내려가지 않는다(dn[:] 자르기).
// 읽다 실패한 폴더는 통째로 건너뛰고(onerror 없음), 폴더 링크는 목록에 들되 따라가지 않는다
fn walk(root: &str) -> Vec<String> {
    let mut names = Vec::new();
    let mut stack = vec![root.to_owned()];
    while let Some(top) = stack.pop() {
        let Some((dirs, files)) = scan(&top) else {
            continue;
        };
        for f in &files {
            if let Some(rel) = relpath(&join(&top, f), root) {
                names.push(rel);
            }
        }

        // Prune, then descend in listing order
        let keep = dirs
            .iter()
            .filter(|d| !skip_dir(d) && !d.starts_with('.') && !d.contains("-ignoreme"));
        let below: Vec<String> = keep.map(|d| join(&top, d)).collect();
        for path in below.into_iter().rev() {
            let is_link = fs::os_path(&path)
                .and_then(|os| std::fs::symlink_metadata(os).ok())
                .is_some_and(|m| m.file_type().is_symlink());
            if !is_link {
                stack.push(path);
            }
        }
    }
    names
}

// 한 폴더의 (폴더 이름들, 나머지 이름들). 링크는 따라가 폴더인지 본다(python entry.is_dir())
fn scan(dir: &str) -> Option<(Vec<String>, Vec<String>)> {
    let entries = std::fs::read_dir(fs::os_path(dir)?).ok()?;
    let mut dirs = Vec::new();
    let mut files = Vec::new();
    for entry in entries {
        let entry = entry.ok()?;
        let name = from_os(&entry.file_name());
        let is_dir = match entry.file_type() {
            Ok(t) if t.is_symlink() => fs::is_dir(&join(dir, &name)),
            Ok(t) => t.is_dir(),
            Err(_) => false,
        };
        if is_dir {
            dirs.push(name);
        } else {
            files.push(name);
        }
    }
    Some((dirs, files))
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 시험 파일, 건너뛸 폴더, 벤더 트리, 생성 접미사는 색인에 넣지 않는다.
    #[test]
    fn indexable_like_python() {
        assert!(indexable("src/a.py", &[]));

        // Tests, skipped folders and vendored trees
        for rel in [
            "m/test-x.py",
            "a/foo.spec.ts",
            "tests/t.py",
            "x-ignoreme/a.py",
            "a/b.d.ts",
            "src/tests.rs",
        ] {
            assert!(!indexable(rel, &[]), "{rel}");
        }
        assert!(!indexable("lock/src/x.py", &["lock/".to_owned()]));

        // Extension check is case-insensitive like python lower()
        assert!(indexable("A.PY", &[]));
        assert!(!indexable("a.txt", &[]));
    }

    /// 생성 표시는 머리 6줄에서만 찾는다.
    #[test]
    fn generated_reads_six_lines() {
        assert!(generated("# 생성: tools/gen.py\nx"));
        assert!(!generated("1\n2\n3\n4\n5\n6\n# generated\n"));
        assert!(generated("1\n2\n3\n4\n5\n# Generated\n"));
    }

    /// 이 모듈의 고정 패턴이 모두 regex crate 로 옮겨지고 엔진이 만들어진다.
    #[test]
    fn fixed_patterns_build() {
        TEST_FILE.check();
        GEN.check();
    }
}
