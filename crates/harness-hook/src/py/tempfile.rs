//! python `tempfile.gettempdir()`.
//!
//! why not `std::env::temp_dir`: python 은 후보(`$TMPDIR`, `$TEMP`, `$TMP`, OS 기본 폴더, 현재 디렉터리)마다 실제로 파일을 하나
//! 만들어 보고 처음 되는 곳을 쓴다. std 는 `$TMPDIR` 를 확인 없이 돌려주어, 그 폴더가 없거나 쓸 수 없을 때 다른 폴더가 된다.

use std::fs::{self, OpenOptions};
use std::io::{ErrorKind, Write};

use crate::env::Env;
use crate::py::path::{abspath, expanduser};

const NAME_CHARS: &[u8] = b"abcdefghijklmnopqrstuvwxyz0123456789_";
const TRIES: usize = 100;

/// python `tempfile.gettempdir()`. 쓸 수 있는 후보가 없으면 `None`(python 은 FileNotFoundError).
pub fn gettempdir(env: &Env) -> Option<String> {
    candidates(env).into_iter().find_map(|dir| {
        let dir = if dir == "." { dir } else { abspath(&dir)? };
        writable(&dir).then_some(dir)
    })
}

// python _candidate_tempdir_list 자리: 환경 변수, OS 기본 폴더, 현재 디렉터리 순서
fn candidates(env: &Env) -> Vec<String> {
    let mut out: Vec<String> = ["TMPDIR", "TEMP", "TMP"]
        .iter()
        .filter_map(|k| env.get_nonempty(k).map(str::to_owned))
        .collect();
    if cfg!(windows) {
        out.push(expanduser("~\\AppData\\Local\\Temp", env));
        out.push(match env.get("SYSTEMROOT") {
            Some(root) => format!("{root}\\Temp"),
            None => "%SYSTEMROOT%\\Temp".to_owned(),
        });
        out.extend(["c:\\temp", "c:\\tmp", "\\temp", "\\tmp"].map(str::to_owned));
    } else {
        out.extend(["/tmp", "/var/tmp", "/usr/tmp"].map(str::to_owned));
    }
    let cwd = std::env::current_dir()
        .ok()
        .and_then(|p| p.into_os_string().into_string().ok());
    out.push(cwd.unwrap_or_else(|| ".".to_owned()));
    out
}

// python _get_default_tempdir 의 시험: 이름이 겹치면 다른 이름으로, 그 밖의 오류는 이 폴더를 건너뛴다
fn writable(dir: &str) -> bool {
    for _ in 0..TRIES {
        let path = std::path::Path::new(dir).join(random_name());
        let mut options = OpenOptions::new();
        options.write(true).create_new(true);
        #[cfg(unix)]
        std::os::unix::fs::OpenOptionsExt::mode(&mut options, 0o600);

        match options.open(&path) {
            Ok(mut file) => {
                let _ = file.write_all(b"blat");
                drop(file);
                let _ = fs::remove_file(&path);
                return true;
            }
            Err(e) if e.kind() == ErrorKind::AlreadyExists => continue,
            // python 은 Windows 에서 쓸 수 있는 폴더의 PermissionError 는 다른 이름으로 다시 해 본다
            Err(e)
                if cfg!(windows)
                    && e.kind() == ErrorKind::PermissionDenied
                    && is_writable_dir(dir) =>
            {
                continue;
            }
            Err(_) => return false,
        }
    }
    false
}

fn is_writable_dir(dir: &str) -> bool {
    fs::metadata(dir).is_ok_and(|m| m.is_dir() && !m.permissions().readonly())
}

fn random_name() -> String {
    let mut raw = [0u8; 8];
    if getrandom::fill(&mut raw).is_err() {
        // 난수가 없으면 시각으로. 겹치면 다음 이름을 만든다
        let nanos = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map_or(0, |d| d.subsec_nanos());
        raw = u64::from(nanos ^ std::process::id()).to_le_bytes();
    }
    raw.iter()
        .map(|b| char::from(NAME_CHARS[usize::from(*b) % NAME_CHARS.len()]))
        .collect()
}

#[cfg(all(test, unix))]
mod tests {
    use super::*;

    #[test]
    fn skips_missing_and_normalizes() {
        let env = Env::from_pairs([("TMPDIR", "/no/such/dir"), ("TEMP", "/tmp/./")]);
        assert_eq!(gettempdir(&env).as_deref(), Some("/tmp"));
    }
}
