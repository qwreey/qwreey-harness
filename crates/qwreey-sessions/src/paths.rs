//! 저장소 루트와 외부 저장소 키(python `sllib/paths.py`).
//!
//! - 루트: 시작 디렉터리에서 위로 올라가며 `.git` 을 찾는다. `.git` 이 파일(worktree)이면 gitdir 의 `commondir` 를 따라
//!   본 체크아웃으로 올린다. 그래서 worktree 에서 시작한 세션도 본 체크아웃과 같은 키를 쓴다.
//! - 키: 루트 경로의 영숫자 아닌 글자(코드 포인트 하나마다)를 `-` 로.

use harness_hook::Env;
use harness_hook::py::path::{RealpathError, expanduser, pathlib_join, pathlib_str, realpath};
use harness_hook::py::text::strip;

use crate::abort::{Abort, Result};
use crate::fsx::{self, FsError};

/// python `Path(path).resolve()`(strict=False).
pub fn resolve(path: &str) -> Result<String> {
    match realpath(&pathlib_str(path)) {
        Ok(resolved) => Ok(pathlib_str(&resolved)),
        Err(RealpathError::Invalid) => Err(Abort("unencodable path")),
        Err(RealpathError::Cwd) => Err(Abort("no current directory")),
    }
}

// python _read: 글을 읽어 strip, OSError 는 빈 글. UTF-8 이 아니면 python 은 예외로 끝난다
fn read_stripped(path: &str) -> Result<String> {
    match fsx::read_text(path) {
        Ok(text) => Ok(strip(&text).to_owned()),
        Err(FsError::Os(_)) => Ok(String::new()),
        Err(FsError::Value) => Err(Abort("unreadable .git file")),
    }
}

// pathlib 의 parent: 마지막 조각을 뗀다. 루트와 "." 는 그대로
fn parent(path: &str) -> String {
    match path.rfind('/') {
        Some(0) => "/".to_owned(),
        // pathlib 이 남기는 `//` 루트
        Some(i) if path[..i].bytes().all(|b| b == b'/') => path[..=i].to_owned(),
        Some(i) => path[..i].to_owned(),
        None => ".".to_owned(),
    }
}

// pathlib 의 name: 마지막 조각(루트는 빈 글)
fn name(path: &str) -> &str {
    path.rsplit('/').next().unwrap_or("")
}

/// 저장소 루트(python `project_root(start)`). git 저장소가 아니면 시작 디렉터리를 푼 경로.
pub fn project_root(start: &str) -> Result<String> {
    let start = resolve(start)?;
    let mut dir = start.clone();
    loop {
        let git = pathlib_join(&dir, ".git");
        if fsx::is_dir(&git) {
            return Ok(dir);
        }

        // .git 파일: worktree 면 본 저장소, 서브모듈 등은 그 자리
        if fsx::is_file(&git) {
            let text = read_stripped(&git)?;
            if let Some(rest) = text.strip_prefix("gitdir:") {
                let mut gitdir = pathlib_str(strip(rest));
                if !gitdir.starts_with('/') {
                    gitdir = resolve(&pathlib_join(&dir, &gitdir))?;
                }
                let common = read_stripped(&pathlib_join(&gitdir, "commondir"))?;
                if !common.is_empty() {
                    let common = if common.starts_with('/') {
                        pathlib_str(&common)
                    } else {
                        resolve(&pathlib_join(&gitdir, &common))?
                    };
                    return Ok(if name(&common) == ".git" {
                        parent(&common)
                    } else {
                        common
                    });
                }
            }
            return Ok(dir);
        }

        // 위로
        let up = parent(&dir);
        if up == dir {
            return Ok(start);
        }
        dir = up;
    }
}

/// 세션 id 를 상태 파일 이름(`.state/<sid>.json` 등)에 써도 되는가(python `paths.safe_sid`).
///
/// `[A-Za-z0-9][A-Za-z0-9._-]{0,127}` 전체. Claude Code 의 id 는 UUID 다. `../x`, `/abs` 는 저장소 밖에 쓰게 된다.
pub fn safe_sid(sid: &str) -> bool {
    let bytes = sid.as_bytes();
    let ok_rest = |b: &u8| b.is_ascii_alphanumeric() || matches!(b, b'.' | b'_' | b'-');
    match bytes.split_first() {
        Some((first, rest)) => {
            first.is_ascii_alphanumeric() && rest.len() < 128 && rest.iter().all(ok_rest)
        }
        None => false,
    }
}

/// 외부 저장소 키(python `project_key`).
pub fn project_key(root: &str) -> String {
    root.chars()
        .map(|c| if c.is_ascii_alphanumeric() { c } else { '-' })
        .collect()
}

/// 홈 아래 경로를 `~` 꼴로(python `short_home`).
pub fn short_home(path: &str, env: &Env) -> String {
    let home = expanduser("~", env);
    let under = path == home || path.starts_with(&format!("{home}/"));
    if home != "/" && under {
        format!("~{}", &path[home.len()..])
    } else {
        path.to_owned()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn keys_parents_and_home() {
        assert_eq!(project_key("/a/b\u{d55c}.c"), "-a-b--c");
        assert_eq!(parent("/a/b"), "/a");
        assert_eq!(parent("/a"), "/");
        assert_eq!(parent("/"), "/");
        assert_eq!(name("/a/.git"), ".git");
        let env = Env::from_pairs([("HOME", "/h")]);
        assert_eq!(short_home("/h/x", &env), "~/x");
        assert_eq!(short_home("/hx", &env), "/hx");
        assert_eq!(short_home("/h", &env), "~");
    }
}
