//! git 을 하위 프로세스로(python `subprocess.run(["git", ...], input=..., capture_output=True, timeout=...)`).
//!
//! 띄우지 못하거나, 시간을 넘기거나(그때는 죽인다), 0 이 아닌 코드로 끝나면 `None` 이다. stderr 는 버린다.
//! stdin 은 따로 쓰는 스레드가, stdout 은 읽는 스레드가 맡는다: 둘 다 큰 `cat-file --batch` 에서 서로 막히지 않게 한다.
//! 한도는 python 처럼 호출 전체(stdout 끝까지 읽기와 종료 기다리기)에 건다.
//! 이 훅이 물려받은 fd(>2)는 git 에 넘기지 않는다(python `close_fds=True`).

use std::ffi::OsString;
use std::io::{Read, Write};
use std::process::{Child, Command, ExitStatus, Stdio};
use std::sync::mpsc;
use std::time::{Duration, Instant};

use harness_hook::py::surrogate::encode_os;

use crate::halt::{Halt, Result};

/// 끝났는지 다시 볼 때까지 쉬는 가장 긴 틈. stdout 이 닫힌 뒤 git 은 대개 곧 끝나므로 짧게 시작해 늘린다.
const POLL_MAX: Duration = Duration::from_millis(10);

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
///
/// `timeout` 은 띄운 때부터 git 이 끝날 때까지다. 넘기면 죽이고 `None`.
pub fn output(args: &[OsString], stdin: Option<Vec<u8>>, timeout: Duration) -> Option<Vec<u8>> {
    let mut git = Command::new("git");
    git.args(args);
    run(git, stdin, timeout)
}

// 프로그램 하나를 한도 안에서 돌려 0 으로 끝났을 때의 stdout(시험은 git 아닌 프로그램으로 부른다)
fn run(mut command: Command, stdin: Option<Vec<u8>>, timeout: Duration) -> Option<Vec<u8>> {
    let deadline = Instant::now() + timeout;
    keep_fds_from_children();
    let mut child = command
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
    let Ok(Ok(bytes)) = recv.recv_timeout(deadline.saturating_duration_since(Instant::now()))
    else {
        stop(&mut child);
        return None;
    };
    wait_until(&mut child, deadline)?.success().then_some(bytes)
}

// stdout 이 닫힌 뒤의 종료를 마감까지만 기다린다. 넘기면 죽이고 None
fn wait_until(child: &mut Child, deadline: Instant) -> Option<ExitStatus> {
    let mut pause = Duration::from_micros(100);
    loop {
        if let Some(status) = child.try_wait().ok()? {
            return Some(status);
        }
        let left = deadline.saturating_duration_since(Instant::now());
        if left.is_zero() {
            stop(child);
            return None;
        }
        std::thread::sleep(pause.min(left));
        pause = (pause * 2).min(POLL_MAX);
    }
}

fn stop(child: &mut Child) {
    let _ = child.kill();
    let _ = child.wait();
}

// 이 프로세스가 물려받은 fd(Claude Code 가 넘긴 파이프 등)를 띄우기 전마다 close-on-exec 로(python 도 띄울 때마다 닫는다)
#[cfg(unix)]
fn keep_fds_from_children() {
    close_fds::set_fds_cloexec(3, &[]);
}

#[cfg(not(unix))]
fn keep_fds_from_children() {}

#[cfg(test)]
mod tests {
    use super::*;

    /// 끝난 git 은 stdout 을 주고, 0 이 아닌 코드는 None 이다.
    #[test]
    fn output_and_exit_code() {
        let version = output(&["--version".into()], None, Duration::from_secs(5));
        assert!(version.is_some_and(|v| v.starts_with(b"git version")));
        let bad = output(&["no-such-subcommand".into()], None, Duration::from_secs(5));
        assert_eq!(bad, None);
    }

    /// stdout 을 닫고도 끝나지 않는 프로그램은 한도에서 죽인다(python 은 호출 전체에 timeout 을 건다).
    #[cfg(unix)]
    #[test]
    fn deadline_covers_the_exit_too() {
        // stdout reaches EOF at once, the process lives on
        let mut nap = Command::new("sh");
        nap.args(["-c", "exec >&-; sleep 3"]);
        let t0 = Instant::now();
        assert_eq!(run(nap, None, Duration::from_millis(300)), None);
        assert!(
            t0.elapsed() < Duration::from_secs(2),
            "waited past the deadline"
        );
    }

    /// 띄운 프로그램은 이 프로세스가 물려받은 fd 를 받지 않는다.
    #[cfg(target_os = "linux")]
    #[test]
    fn inherited_fds_stay_here() {
        use std::os::fd::AsRawFd;

        // An fd without close-on-exec, like one a parent passed down
        let file = std::fs::File::open("/dev/null").unwrap();
        let fd = file.as_raw_fd();
        let flags = rustix::io::fcntl_getfd(&file).unwrap();
        rustix::io::fcntl_setfd(&file, flags.difference(rustix::io::FdFlags::CLOEXEC)).unwrap();

        // The child shell looks for that fd number among its own
        let mut probe = Command::new("sh");
        probe.args([
            "-c",
            &format!("test -e /proc/self/fd/{fd} && echo open || echo closed"),
        ]);
        let out = run(probe, None, Duration::from_secs(5)).unwrap();
        assert_eq!(String::from_utf8_lossy(&out).trim(), "closed");
    }
}
