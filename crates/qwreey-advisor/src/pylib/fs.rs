//! python 의 파일 함수를 python str 꼴 경로로(UTF-8 이 아닌 바이트는 서로게이트 자리표, `harness_hook::py::surrogate`).
//!
//! python 은 OS 바이트로 바꾸지 못하는 경로(짝 없는 high 서로게이트)와 NUL 이 든 경로에서 ValueError 를 낸다.
//! 그 경우는 [`FsError::Value`] 다. 호출하는 곳마다 python 이 잡는 예외가 달라 갈래를 나눠 돌려준다.

use std::fs;
use std::path::PathBuf;

use harness_hook::py::surrogate::to_os;

use super::text::universal_newlines;

/// python 에서 나는 예외의 갈래.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum FsError {
    /// OSError(없음, 권한, 폴더 등).
    Os,
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

/// python `open(path, "rb").read()`.
pub fn read_bytes(path: &str) -> Result<Vec<u8>, FsError> {
    let os = os_path(path).ok_or(FsError::Value)?;
    fs::read(os).map_err(|_| FsError::Os)
}

/// python `open(path, encoding="utf-8").read()`: UTF-8(어긋나면 ValueError), 줄 끝 `\r\n`, `\r` 은 `\n` 으로.
pub fn read_text(path: &str) -> Result<String, FsError> {
    let bytes = read_bytes(path)?;
    let text = String::from_utf8(bytes).map_err(|_| FsError::Value)?;
    Ok(universal_newlines(&text))
}

/// python `os.path.isfile`.
pub fn is_file(path: &str) -> bool {
    os_path(path)
        .and_then(|p| fs::metadata(p).ok())
        .is_some_and(|m| m.is_file())
}

/// python `os.path.exists`.
pub fn exists(path: &str) -> bool {
    os_path(path).is_some_and(|p| fs::metadata(p).is_ok())
}

/// python `for line in open(path, encoding="utf-8")`: 줄마다(끝 `\n` 포함), 필요한 만큼만 읽는다.
///
/// python `TextIOWrapper` 처럼 8 KiB 씩 읽어 그 덩어리를 엄격히 UTF-8 로 풀고(덩어리 끝의 덜 끝난 글자는 다음으로 넘긴다),
/// 줄 끝 `\r\n`, `\r` 을 `\n` 으로 바꾼다(덩어리 끝의 `\r` 은 다음 덩어리를 볼 때까지 미룬다). 그래서 UTF-8 이 아닌 바이트는
/// 그것이 든 덩어리를 읽을 때 [`FsError::Value`] 가 되고, 그 앞 덩어리의 줄은 먼저 나온다.
pub struct TextLines {
    file: fs::File,
    /// 아직 풀지 못한 덜 끝난 UTF-8 바이트.
    pending: Vec<u8>,
    /// python IncrementalNewlineDecoder 의 pendingcr.
    pending_cr: bool,
    /// 풀었지만 아직 내지 않은 글.
    text: String,
    eof: bool,
}

/// python `TextIOWrapper._CHUNK_SIZE`.
const TEXT_CHUNK: usize = 8192;

impl TextLines {
    /// 파일을 연다. 열지 못하면 python 의 OSError, 바꿀 수 없는 경로면 ValueError.
    pub fn open(path: &str) -> Result<TextLines, FsError> {
        let os = os_path(path).ok_or(FsError::Value)?;
        let file = fs::File::open(os).map_err(|_| FsError::Os)?;
        Ok(TextLines {
            file,
            pending: Vec::new(),
            pending_cr: false,
            text: String::new(),
            eof: false,
        })
    }

    /// 다음 줄. 끝이면 `None`.
    pub fn next_line(&mut self) -> Option<Result<String, FsError>> {
        loop {
            if let Some(end) = self.text.find('\n') {
                let rest = self.text.split_off(end + 1);
                return Some(Ok(std::mem::replace(&mut self.text, rest)));
            }
            if self.eof {
                return (!self.text.is_empty()).then(|| Ok(std::mem::take(&mut self.text)));
            }
            if let Err(e) = self.read_chunk() {
                return Some(Err(e));
            }
        }
    }

    fn read_chunk(&mut self) -> Result<(), FsError> {
        use std::io::Read;

        // One chunk of bytes, plus what the last chunk left undecoded
        let mut buf = vec![0u8; TEXT_CHUNK];
        let n = loop {
            match self.file.read(&mut buf) {
                Ok(n) => break n,
                Err(e) if e.kind() == std::io::ErrorKind::Interrupted => continue,
                Err(_) => return Err(FsError::Os),
            }
        };
        let last = n == 0;
        self.eof = last;
        self.pending.extend_from_slice(&buf[..n]);

        // Strict UTF-8; an incomplete tail waits unless this is the end
        let valid = match std::str::from_utf8(&self.pending) {
            Ok(_) => self.pending.len(),
            Err(e) if e.error_len().is_none() && !last => e.valid_up_to(),
            Err(_) => return Err(FsError::Value),
        };
        let rest = self.pending.split_off(valid);
        let bytes = std::mem::replace(&mut self.pending, rest);
        let mut decoded = String::from_utf8(bytes).map_err(|_| FsError::Value)?;

        // Newline translation with a held-back trailing \r
        if self.pending_cr {
            decoded.insert(0, '\r');
            self.pending_cr = false;
        }
        if !last && decoded.ends_with('\r') {
            decoded.pop();
            self.pending_cr = true;
        }
        self.text
            .push_str(&super::text::universal_newlines(&decoded));
        Ok(())
    }
}

/// python `os.makedirs(path, exist_ok=True)`. 이미 있는 폴더는 성공, 파일이 그 자리에 있으면 실패다.
pub fn makedirs(path: &str) -> Result<(), FsError> {
    let os = os_path(path).ok_or(FsError::Value)?;
    fs::create_dir_all(os).map_err(|_| FsError::Os)
}

/// python `open(path, "w").write(text)`: 자르고 쓴다. `text` 는 UTF-8 로 쓸 수 있어야 한다(자리표가 없는 글).
pub fn write_text(path: &str, text: &str) -> Result<(), FsError> {
    let os = os_path(path).ok_or(FsError::Value)?;
    fs::write(os, text).map_err(|_| FsError::Os)
}
