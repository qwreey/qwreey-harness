//! python 의 파일 함수(`os.path.isdir`, `Path.read_text` 등)를 python str 꼴 경로로.
//!
//! 경로는 python 이 쓰는 글 그대로 다룬다: UTF-8 이 아닌 바이트는 서로게이트 자리표다([`harness_hook::py::surrogate`]).
//! python 은 OS 바이트로 바꾸지 못하는 경로(짝 없는 high 서로게이트)와 NUL 이 든 경로에서 ValueError 를 낸다. 판정 함수
//! (`isdir`, `exists`)는 그것을 거짓으로 보고, 읽기 함수는 [`FsError::Value`] 로 돌려준다(호출하는 곳마다 잡는 예외가 다르다).

use std::fs;
use std::io::ErrorKind;
use std::path::PathBuf;

use harness_hook::py::surrogate::to_os;

/// python 에서 나는 예외의 갈래. 호출하는 곳이 python 처럼 잡거나 [`crate::abort::Abort`] 로 넘긴다.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum FsError {
    /// OSError(없음, 권한 등).
    Os(ErrorKind),
    /// ValueError: 바꿀 수 없는 경로, NUL, UTF-8 이 아닌 내용(UnicodeDecodeError).
    Value,
}

/// python 이 OS 에 넘기는 경로. 넘기지 못하면 `None`(python ValueError).
pub fn os_path(path: &str) -> Option<PathBuf> {
    if path.contains('\0') {
        return None;
    }
    to_os(path)
}

fn metadata(path: &str) -> Option<fs::Metadata> {
    fs::metadata(os_path(path)?).ok()
}

/// python `os.path.isdir`.
pub fn is_dir(path: &str) -> bool {
    metadata(path).is_some_and(|m| m.is_dir())
}

/// python `os.path.isfile`.
pub fn is_file(path: &str) -> bool {
    metadata(path).is_some_and(|m| m.is_file())
}

/// python `os.path.exists`.
pub fn exists(path: &str) -> bool {
    metadata(path).is_some()
}

/// python `os.path.getsize`.
pub fn getsize(path: &str) -> Result<u64, FsError> {
    let os = os_path(path).ok_or(FsError::Value)?;
    fs::metadata(os)
        .map(|m| m.len())
        .map_err(|e| FsError::Os(e.kind()))
}

/// python `open(path, encoding="utf-8").read()`: UTF-8(어긋나면 ValueError), 줄 끝 `\r\n`, `\r` 은 `\n` 으로.
pub fn read_text(path: &str) -> Result<String, FsError> {
    let os = os_path(path).ok_or(FsError::Value)?;
    let bytes = fs::read(os).map_err(|e| FsError::Os(e.kind()))?;
    let text = String::from_utf8(bytes).map_err(|_| FsError::Value)?;
    Ok(universal_newlines(&text))
}

/// python 글 모드의 읽기(newline=None): `\r\n` 과 `\r` 을 `\n` 으로.
pub fn universal_newlines(text: &str) -> String {
    if !text.contains('\r') {
        return text.to_owned();
    }
    text.replace("\r\n", "\n").replace('\r', "\n")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn newlines_and_bad_paths() {
        assert_eq!(universal_newlines("a\r\nb\rc\n"), "a\nb\nc\n");
        assert!(!is_dir("/\0"));
        assert_eq!(getsize("/a\0b"), Err(FsError::Value));
        assert!(is_dir("/"));
    }
}
