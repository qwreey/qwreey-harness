//! python 의 파일 함수(`os.path.isdir`, `os.stat`, `open(...).read()` 등)를 python str 꼴 경로로.
//!
//! 경로는 python 이 쓰는 글 그대로 다룬다: UTF-8 이 아닌 바이트는 서로게이트 자리표다([`crate::py::surrogate`]).
//! python 은 OS 바이트로 바꾸지 못하는 경로(짝 없는 high 서로게이트)와 NUL 이 든 경로에서 ValueError 를 낸다. 판정 함수
//! (`isdir`, `exists`)는 그것을 거짓으로 보고, 읽기 함수는 [`FsError::Value`] 로 돌려준다(호출하는 곳마다 잡는 예외가 다르다).

use std::fs;
use std::io::ErrorKind;
use std::path::PathBuf;

use crate::py::surrogate::{from_os, to_os};

/// python 에서 나는 예외의 갈래. 호출하는 곳이 python 처럼 잡거나 자기 오류로 넘긴다.
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
    stat(path).map(|s| s.size)
}

/// `os.stat` 결과 가운데 훅이 보는 것.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Stat {
    /// `st_mtime_ns`.
    pub mtime_ns: i128,
    /// `st_size`.
    pub size: u64,
}

/// python `os.stat(path)`(링크를 따라간다).
pub fn stat(path: &str) -> Result<Stat, FsError> {
    let os = os_path(path).ok_or(FsError::Value)?;
    let meta = fs::metadata(os).map_err(|e| FsError::Os(e.kind()))?;
    Ok(Stat {
        mtime_ns: mtime_ns(&meta),
        size: meta.len(),
    })
}

#[cfg(unix)]
fn mtime_ns(meta: &fs::Metadata) -> i128 {
    use std::os::unix::fs::MetadataExt;
    i128::from(meta.mtime()) * 1_000_000_000 + i128::from(meta.mtime_nsec())
}

#[cfg(not(unix))]
fn mtime_ns(meta: &fs::Metadata) -> i128 {
    // python 도 Windows 에서는 FILETIME(100 ns 단위)을 1970 기준 ns 로 바꾼다
    meta.modified()
        .ok()
        .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
        .map_or(0, |d| d.as_nanos() as i128)
}

/// python `os.listdir(path)`: 이름들, 디렉터리가 주는 순서 그대로(정렬하지 않는다).
pub fn listdir(path: &str) -> Result<Vec<String>, FsError> {
    let os = os_path(path).ok_or(FsError::Value)?;
    let entries = fs::read_dir(os).map_err(|e| FsError::Os(e.kind()))?;
    let mut out = Vec::new();
    for entry in entries {
        let entry = entry.map_err(|e| FsError::Os(e.kind()))?;
        out.push(from_os(&entry.file_name()));
    }
    Ok(out)
}

/// python `open(path, "rb").read()`.
pub fn read_bytes(path: &str) -> Result<Vec<u8>, FsError> {
    let os = os_path(path).ok_or(FsError::Value)?;
    fs::read(os).map_err(|e| FsError::Os(e.kind()))
}

/// 일반 파일만 연다(python `os.open(path, O_RDONLY | O_NONBLOCK)` 뒤 `fstat` 로 종류 보기).
///
/// FIFO 를 그냥 열면 쓰는 쪽이 올 때까지 멈춘다. 일반 파일이 아니면(FIFO, 장치, 폴더) `FsError::Os(InvalidInput)`.
#[cfg(unix)]
pub fn open_regular(path: &str) -> Result<fs::File, FsError> {
    use rustix::fs::{FileType, Mode, OFlags, fstat, open};

    let os = os_path(path).ok_or(FsError::Value)?;
    let flags = OFlags::RDONLY | OFlags::NONBLOCK | OFlags::CLOEXEC;
    let fd =
        open(&os, flags, Mode::empty()).map_err(|e| FsError::Os(std::io::Error::from(e).kind()))?;
    let st = fstat(&fd).map_err(|e| FsError::Os(std::io::Error::from(e).kind()))?;
    if FileType::from_raw_mode(st.st_mode) != FileType::RegularFile {
        return Err(FsError::Os(ErrorKind::InvalidInput));
    }
    Ok(fs::File::from(fd))
}

/// 일반 파일만 연다. 이 OS 에서는 열린 파일의 종류를 본다(FIFO 가 없다).
#[cfg(not(unix))]
pub fn open_regular(path: &str) -> Result<fs::File, FsError> {
    let os = os_path(path).ok_or(FsError::Value)?;
    let file = fs::File::open(os).map_err(|e| FsError::Os(e.kind()))?;
    match file.metadata() {
        Ok(m) if m.is_file() => Ok(file),
        Ok(_) => Err(FsError::Os(ErrorKind::InvalidInput)),
        Err(e) => Err(FsError::Os(e.kind())),
    }
}

/// [`open_regular`] 로 연 파일의 바이트(python `open_regular(path, "rb").read()`).
pub fn read_regular_bytes(path: &str) -> Result<Vec<u8>, FsError> {
    use std::io::Read;

    let mut bytes = Vec::new();
    open_regular(path)?
        .read_to_end(&mut bytes)
        .map_err(|e| FsError::Os(e.kind()))?;
    Ok(bytes)
}

/// [`open_regular`] 로 연 파일의 글: [`read_text`] 와 같이 UTF-8 로 읽고 줄 끝을 바꾼다.
pub fn read_regular_text(path: &str) -> Result<String, FsError> {
    let text = String::from_utf8(read_regular_bytes(path)?).map_err(|_| FsError::Value)?;
    Ok(universal_newlines(&text))
}

/// python `open(path, encoding="utf-8").read()`: UTF-8(어긋나면 ValueError), 줄 끝 `\r\n`, `\r` 은 `\n` 으로.
pub fn read_text(path: &str) -> Result<String, FsError> {
    let bytes = read_bytes(path)?;
    let text = String::from_utf8(bytes).map_err(|_| FsError::Value)?;
    Ok(universal_newlines(&text))
}

/// python `Path.read_text(errors="replace")`: 어긋난 UTF-8 은 U+FFFD, 줄 끝은 [`universal_newlines`].
///
/// python 의 replace 와 Rust 의 `from_utf8_lossy` 는 모두 가장 긴 잘못된 조각마다 U+FFFD 하나를 쓴다.
pub fn read_text_replace(path: &str) -> Result<String, FsError> {
    let bytes = read_bytes(path)?;
    Ok(universal_newlines(&String::from_utf8_lossy(&bytes)))
}

/// python `open(path, "w").write(text)`: 자르고 쓴다(UTF-8).
pub fn write_text(path: &str, text: &str) -> Result<(), FsError> {
    let os = os_path(path).ok_or(FsError::Value)?;
    fs::write(os, text.as_bytes()).map_err(|e| FsError::Os(e.kind()))
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

    /// 줄 끝을 python 글 모드처럼 바꾸고, NUL 이 든 경로는 ValueError 갈래로 돌려준다.
    #[test]
    fn newlines_and_bad_paths() {
        assert_eq!(universal_newlines("a\r\nb\rc\n"), "a\nb\nc\n");
        assert!(!is_dir("/\0"));
        assert_eq!(getsize("/a\0b"), Err(FsError::Value));
        assert!(is_dir("/"));
        assert!(listdir("/").is_ok_and(|names| !names.is_empty()));
    }

    /// 일반 파일만 읽고, FIFO 는 쓰는 쪽을 기다리지 않고 OSError 갈래로 돌려준다.
    #[cfg(unix)]
    #[test]
    fn regular_files_only() {
        let dir = std::env::temp_dir().join(format!("hh-regular-{}", std::process::id()));
        fs::create_dir_all(&dir).unwrap();
        let file = dir.join("a.md");
        let fifo = dir.join("p.md");
        fs::write(&file, "x\r\ny").unwrap();
        let made = std::process::Command::new("mkfifo").arg(&fifo).status();
        assert!(made.is_ok_and(|s| s.success()), "mkfifo");

        // Text like read_text, nothing from a FIFO or a folder
        let path = |p: &std::path::Path| p.to_str().unwrap().to_owned();
        assert_eq!(read_regular_text(&path(&file)).as_deref(), Ok("x\ny"));
        assert_eq!(
            read_regular_bytes(&path(&fifo)),
            Err(FsError::Os(ErrorKind::InvalidInput))
        );
        assert_eq!(
            read_regular_bytes(&path(&dir)),
            Err(FsError::Os(ErrorKind::InvalidInput))
        );
        assert_eq!(
            read_regular_bytes(&path(&dir.join("none"))),
            Err(FsError::Os(ErrorKind::NotFound))
        );
        fs::remove_dir_all(&dir).unwrap();
    }
}
