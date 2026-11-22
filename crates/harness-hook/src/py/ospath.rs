//! python `os.path` 를 이 OS 에 맞게: POSIX 는 `posixpath`([`crate::py::path`]), Windows 는 `ntpath`([`crate::py::ntpath`]).
//!
//! 판정 훅(workspace-gate 등)이 python 과 같은 경로 글을 내려면 python 이 그 OS 에서 쓰는 모듈을 따라야 한다.
//! [`crate::py::path`] 의 함수는 이름대로 늘 posixpath 다(pathlib, 설정 층처럼 POSIX 꼴을 바라는 곳이 쓴다).

#[cfg(windows)]
use crate::py::ntpath as imp;
#[cfg(not(windows))]
use crate::py::path as imp;

/// 구분자(python `os.sep`).
pub const SEP: char = if cfg!(windows) { '\\' } else { '/' };

/// python `os.path.normpath`.
pub fn normpath(path: &str) -> String {
    imp::normpath(path)
}

/// python `os.path.join(a, b)`.
pub fn join(a: &str, b: &str) -> String {
    imp::join(a, b)
}

/// python `os.path.dirname`.
pub fn dirname(path: &str) -> &str {
    imp::dirname(path)
}

/// python `os.path.basename`.
pub fn basename(path: &str) -> &str {
    imp::basename(path)
}

/// python `os.path.isabs`.
pub fn isabs(path: &str) -> bool {
    if cfg!(windows) {
        crate::py::ntpath::isabs(path)
    } else {
        path.starts_with('/')
    }
}

/// python `os.path.normcase`: POSIX 는 그대로, Windows 는 소문자와 `\`.
pub fn normcase(path: &str) -> String {
    if cfg!(windows) {
        crate::py::ntpath::normcase(path)
    } else {
        path.to_owned()
    }
}

/// python `os.path.abspath`. 현재 디렉터리를 읽지 못하면 `None`.
pub fn abspath(path: &str) -> Option<String> {
    crate::py::path::abspath(path)
}

/// python `os.path.relpath(path, start)`. python 이 ValueError, OSError 를 내는 자리(빈 경로, 다른 드라이브)는 `None`.
pub fn relpath(path: &str, start: &str) -> Option<String> {
    if cfg!(windows) {
        if path.is_empty() {
            return None;
        }
        crate::py::ntpath::relpath_abs(&abspath(path)?, &abspath(start)?)
    } else {
        crate::py::path::relpath(path, start)
    }
}

/// python `os.path.expanduser`.
pub fn expanduser(path: &str, env: &crate::Env) -> String {
    crate::py::path::expanduser(path, env)
}
