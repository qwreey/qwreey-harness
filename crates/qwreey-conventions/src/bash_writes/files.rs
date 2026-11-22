//! 명령 전후로 파일을 읽는 법(python `bash_writes._read`, `_stat`, `_size`, `_Reader`).
//!
//! 경로에 NUL 이나 짝 없는 서로게이트가 있으면 python 의 `os.open`, `os.stat` 은 ValueError 를 낸다. 그 함수들은 OSError 만
//! 잡으므로 예외는 훅 끝까지 간다: 여기서는 [`Halt::PyError`] 로 돌려준다.

use std::io::{ErrorKind, Read};
use std::time::Instant;

use harness_hook::py::fs::{self, FsError};
use harness_hook::py::value::Value;

use crate::halt::{Halt, Result};

/// 한 파일에서 적어 둘 글의 한도(python `TEXT_MAX`).
pub const TEXT_MAX: u64 = 256 * 1024;
/// 명령이 이름을 댄 파일의 한도(python `CANDIDATE_MAX`, conventions-check 의 `MAX_BYTES` 와 같다).
pub const CANDIDATE_MAX: u64 = 1_000_000;
/// 모두 합친 글자 수 한도(python `TOTAL_MAX`).
pub const TOTAL_MAX: u64 = 4 * 1024 * 1024;
/// 명령 뒤에 읽는 파일 수 한도(python `READ_FILES_MAX`).
const READ_FILES_MAX: usize = 200;

/// 파일 하나를 읽은 결과(스냅숏 JSON 의 `null`, `false`, 글).
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Recorded {
    /// 없는 파일(python `None`).
    Missing,
    /// 한도를 넘거나, UTF-8 이 아니거나, 일반 파일이 아니다(python `False`).
    Unread,
    Text(String),
}

impl Recorded {
    /// 스냅숏 JSON 값.
    pub fn to_value(&self) -> Value {
        match self {
            Recorded::Missing => Value::Null,
            Recorded::Unread => Value::Bool(false),
            Recorded::Text(t) => Value::Str(t.clone()),
        }
    }

    /// 스냅숏 JSON 값에서. 이 셋 밖의 값이면 `None`.
    pub fn from_value(v: &Value) -> Option<Recorded> {
        match v {
            Value::Null => Some(Recorded::Missing),
            Value::Bool(false) => Some(Recorded::Unread),
            Value::Str(t) => Some(Recorded::Text(t.clone())),
            _ => None,
        }
    }

    /// 글이면 그 글.
    pub fn text(&self) -> Option<&str> {
        match self {
            Recorded::Text(t) => Some(t),
            _ => None,
        }
    }
}

/// (mtime_ns, 크기)(python `_stat` 의 `[st_mtime_ns, st_size]`).
pub type FileStat = (i128, u64);

/// python `_stat(path)`: 없거나 읽지 못하면 `None`.
pub fn stat(path: &str) -> Result<Option<FileStat>> {
    match fs::stat(path) {
        Ok(st) => Ok(Some((st.mtime_ns, st.size))),
        Err(FsError::Os(_)) => Ok(None),
        Err(FsError::Value) => Err(Halt::PyError("os.stat of an unusable path")),
    }
}

/// python `_size(path)`: 읽지 못하면 0.
fn size(path: &str) -> Result<u64> {
    Ok(stat(path)?.map_or(0, |(_, size)| size))
}

/// python `_read(path, cap)`: 일반 파일이고 `cap` 바이트 안이면 그 글(줄 끝은 python 글 모드처럼 `\n`).
///
/// 일반 파일만 연다([`fs::open_regular`]: FIFO 를 그냥 열면 쓰는 쪽이 올 때까지 멈춘다).
pub fn read(path: &str, cap: u64) -> Result<Recorded> {
    let mut file = match fs::open_regular(path) {
        Ok(file) => file,
        Err(FsError::Value) => return Err(Halt::PyError("os.open of an unusable path")),
        Err(FsError::Os(ErrorKind::NotFound)) => return Ok(Recorded::Missing),
        Err(FsError::Os(_)) => return Ok(Recorded::Unread),
    };

    // Within the cap, as UTF-8 text
    let small = file.metadata().is_ok_and(|m| m.len() <= cap);
    let mut bytes = Vec::new();
    if !small || file.read_to_end(&mut bytes).is_err() {
        return Ok(Recorded::Unread);
    }
    Ok(match String::from_utf8(bytes) {
        Ok(text) => Recorded::Text(fs::universal_newlines(&text)),
        Err(_) => Recorded::Unread,
    })
}

/// python 글자 수(`len(text)`).
pub fn char_len(text: &str) -> u64 {
    text.chars().count() as u64
}

/// 명령 뒤의 읽기(python `_Reader`): 마감 시각, 글자 수, 파일 수 한도 안에서만 읽는다.
///
/// 한도를 넘긴 경로는 [`Reader::skipped`] 에 적고 [`Recorded::Unread`] 를 준다.
pub struct Reader {
    deadline: Option<Instant>,
    left: u64,
    files: usize,
    pub skipped: Vec<String>,
}

impl Reader {
    /// `deadline` 까지 읽는 읽개.
    pub fn new(deadline: Option<Instant>) -> Reader {
        Reader {
            deadline,
            left: TOTAL_MAX,
            files: READ_FILES_MAX,
            skipped: Vec::new(),
        }
    }

    /// python `_Reader.__call__(path)`.
    pub fn read(&mut self, path: &str) -> Result<Recorded> {
        let size = size(path)?;
        let late = self.deadline.is_some_and(|d| Instant::now() > d);
        if self.files == 0 || size > self.left || late {
            self.skipped.push(path.to_owned());
            return Ok(Recorded::Unread);
        }
        self.files -= 1;
        let got = read(path, CANDIDATE_MAX.min(self.left))?;
        if let Recorded::Text(t) = &got {
            self.left = self.left.saturating_sub(char_len(t));
        }
        Ok(got)
    }
}
