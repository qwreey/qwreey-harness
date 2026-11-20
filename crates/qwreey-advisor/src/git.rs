//! python `subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, timeout=5)`.
//!
//! python 과 같게 하는 것:
//! - stdout 은 UTF-8 로 엄격히 읽는다(UTF-8 모드의 `text=True`). 어긋나면 python 은 UnicodeDecodeError 를 내고 훅이 그
//!   자리에서 끝난다: [`GitError::Decode`]. 줄 끝은 `\r\n`, `\r` 을 `\n` 으로 바꾼다(universal newlines).
//! - 띄우지 못하거나 5초를 넘기면(python OSError, TimeoutExpired) 부르는 쪽이 빈 출력으로 본다: [`GitError::Failed`].
//! - 인자에 NUL 이나 바이트로 바꿀 수 없는 서로게이트가 있으면 python 은 ValueError, UnicodeEncodeError: [`GitError::BadArg`].
//! - 이 훅이 물려받은 fd(>2)를 넘기지 않는다(close_fds=True).

use std::ffi::OsString;
use std::io::Read;
use std::process::{Command, Stdio};
use std::sync::Once;
use std::sync::mpsc;
use std::time::Duration;

use harness_hook::py::surrogate::encode_os;

use harness_hook::py::fs::universal_newlines;

const TIMEOUT: Duration = Duration::from_secs(5);

/// git 한 번의 결과.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct GitOutput {
    /// python `returncode`: 신호로 끝나면 음수.
    pub code: i32,
    pub stdout: String,
}

/// git 을 돌리지 못한 이유.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum GitError {
    /// 띄우지 못함, 시간 초과(python 은 잡아서 빈 출력).
    Failed,
    /// stdout 이 UTF-8 이 아니다(python 은 잡지 않는다).
    Decode,
    /// 인자를 OS 문자열로 바꾸지 못함(python 은 잡지 않는다).
    BadArg,
}

/// `git -C <cwd> <args>` 를 돌린다.
pub fn run(cwd: &str, args: &[&str]) -> Result<GitOutput, GitError> {
    let mut argv: Vec<OsString> = vec![os_arg("-C")?, os_arg(cwd)?];
    for arg in args {
        argv.push(os_arg(arg)?);
    }
    let (code, stdout) = spawn_and_read(&argv)?;
    let text = String::from_utf8(stdout).map_err(|_| GitError::Decode)?;
    Ok(GitOutput {
        code,
        stdout: universal_newlines(&text),
    })
}

/// [`run`] 의 stdout, 실패면 빈 글(python 판 `git()` 의 `except (OSError, SubprocessError): return ""`).
pub fn stdout_or_empty(cwd: &str, args: &[&str]) -> Result<String, GitError> {
    match run(cwd, args) {
        Ok(out) => Ok(out.stdout),
        Err(GitError::Failed) => Ok(String::new()),
        Err(other) => Err(other),
    }
}

fn os_arg(text: &str) -> Result<OsString, GitError> {
    if text.contains('\0') {
        return Err(GitError::BadArg);
    }
    let bytes = encode_os(text).ok_or(GitError::BadArg)?;
    Ok(bytes_to_os(bytes))
}

#[cfg(unix)]
fn bytes_to_os(bytes: Vec<u8>) -> OsString {
    use std::os::unix::ffi::OsStringExt;
    OsString::from_vec(bytes)
}

#[cfg(not(unix))]
fn bytes_to_os(bytes: Vec<u8>) -> OsString {
    OsString::from(String::from_utf8_lossy(&bytes).into_owned())
}

static CLOEXEC: Once = Once::new();

fn spawn_and_read(argv: &[OsString]) -> Result<(i32, Vec<u8>), GitError> {
    // Do not leak inherited fds into git
    #[cfg(unix)]
    CLOEXEC.call_once(|| close_fds::set_fds_cloexec(3, &[]));
    #[cfg(not(unix))]
    CLOEXEC.call_once(|| {});

    let mut child = Command::new("git")
        .args(argv)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|_| GitError::Failed)?;
    let mut pipe = child.stdout.take().ok_or(GitError::Failed)?;

    // Read stdout on a thread so the wait can time out
    let (send, recv) = mpsc::channel();
    std::thread::spawn(move || {
        let mut buf = Vec::new();
        let read = pipe.read_to_end(&mut buf).map(|_| buf);
        let _ = send.send(read);
    });
    let stdout = match recv.recv_timeout(TIMEOUT) {
        Ok(Ok(buf)) => buf,
        Ok(Err(_)) | Err(_) => {
            let _ = child.kill();
            let _ = child.wait();
            return Err(GitError::Failed);
        }
    };

    // Exit status, negative for a signal like python
    let status = child.wait().map_err(|_| GitError::Failed)?;
    Ok((exit_code(status), stdout))
}

#[cfg(unix)]
fn exit_code(status: std::process::ExitStatus) -> i32 {
    use std::os::unix::process::ExitStatusExt;
    status
        .code()
        .unwrap_or_else(|| -status.signal().unwrap_or(1))
}

#[cfg(not(unix))]
fn exit_code(status: std::process::ExitStatus) -> i32 {
    status.code().unwrap_or(1)
}
