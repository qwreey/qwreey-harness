//! `harness_hook::py::fs` 에 없는 python 파일 함수: 줄마다 읽기(`for line in open(path)`)와 `os.makedirs(exist_ok=True)`.
//!
//! 경로와 오류 갈래는 `harness_hook::py::fs` 와 같다(OSError 는 [`FsError::Os`], 바꿀 수 없는 경로와 UTF-8 이 아닌 내용은
//! [`FsError::Value`]).

use std::fs;

use harness_hook::py::fs::{FsError, os_path, universal_newlines};

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
        let file = fs::File::open(os).map_err(|e| FsError::Os(e.kind()))?;
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
                Err(e) => return Err(FsError::Os(e.kind())),
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
        self.text.push_str(&universal_newlines(&decoded));
        Ok(())
    }
}

/// python `os.makedirs(path, exist_ok=True)`. 이미 있는 폴더는 성공, 파일이 그 자리에 있으면 실패다.
pub fn makedirs(path: &str) -> Result<(), FsError> {
    let os = os_path(path).ok_or(FsError::Value)?;
    fs::create_dir_all(os).map_err(|e| FsError::Os(e.kind()))
}
