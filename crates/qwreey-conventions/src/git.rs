//! git 을 하위 프로세스로(python `subprocess.run(["git", ...], input=..., capture_output=True, timeout=...)`).
//!
//! 띄우지 못하거나, 시간을 넘기거나(그때는 죽인다), 0 이 아닌 코드로 끝나면 `None` 이다. stderr 는 버린다.
//! stdin 은 따로 쓰는 스레드가, stdout 은 읽는 스레드가 맡는다: 둘 다 큰 `cat-file --batch` 에서 서로 막히지 않게 한다.

use std::ffi::OsString;
use std::io::{Read, Write};
use std::process::{Command, Stdio};
use std::sync::mpsc;
use std::time::Duration;

use harness_hook::py::surrogate::encode_os;

use crate::halt::{Halt, Result};

/// python 글 인자를 OS 인자로(`os.fsencode`). NUL 이나 짝 없는 서로게이트가 든 글은 python 이 예외로 끝나는 자리다.
pub fn os_arg(text: &str) -> Result<OsString> {
    if text.contains('\0') {
        return Err(Halt::PyError("a NUL in a subprocess argument"));
    }
    let bytes = encode_os(text).ok_or(Halt::PyError("an argument python cannot encode"))?;
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

/// `git <args>` 의 stdout. `stdin` 이 있으면 그 바이트를 넣고, 없으면 빈 stdin 이다.
pub fn output(args: &[OsString], stdin: Option<Vec<u8>>, timeout: Duration) -> Option<Vec<u8>> {
    let mut child = Command::new("git")
        .args(args)
        .stdin(if stdin.is_some() {
            Stdio::piped()
        } else {
            Stdio::null()
        })
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .ok()?;

    // Feed stdin and drain stdout on their own threads
    if let (Some(input), Some(mut pipe)) = (stdin, child.stdin.take()) {
        std::thread::spawn(move || {
            let _ = pipe.write_all(&input);
        });
    }
    let mut out = child.stdout.take()?;
    let (send, recv) = mpsc::channel();
    std::thread::spawn(move || {
        let mut buf = Vec::new();
        let read = out.read_to_end(&mut buf).map(|_| buf);
        let _ = send.send(read);
    });

    // Past the deadline the child is killed
    let Ok(Ok(bytes)) = recv.recv_timeout(timeout) else {
        let _ = child.kill();
        let _ = child.wait();
        return None;
    };
    child.wait().ok()?.success().then_some(bytes)
}
