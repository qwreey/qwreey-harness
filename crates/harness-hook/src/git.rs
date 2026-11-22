//! git 을 하위 프로세스로(python `subprocess.run(["git", ...], input=..., capture_output=True, timeout=...)`).
//!
//! python 과 같게 하는 것:
//! - 한도는 호출 전체(stdout 끝까지 읽기와 종료 기다리기)에 건다. 넘기면 죽이고 실패다(python TimeoutExpired).
//! - 띄우지 못하면 실패다(python OSError). 0 이 아닌 종료 코드는 실패가 아니다: 코드를 돌려주고 부르는 쪽이 정한다.
//! - stderr 는 버린다. stdin 은 주어진 바이트, 없으면 빈 stdin 이다.
//! - 이 훅이 물려받은 fd(>2)는 git 에 넘기지 않는다(python `close_fds=True`): 띄우기 전마다 close-on-exec 로 둔다.
//!
//! stdin 은 따로 쓰는 스레드가, stdout 은 읽는 스레드가 맡는다: 둘 다 큰 `cat-file --batch` 에서 서로 막히지 않게 한다.

use std::ffi::OsString;
use std::io::{Read, Write};
use std::process::{Child, Command, ExitStatus, Stdio};
use std::sync::mpsc;
use std::time::{Duration, Instant};

use crate::py::surrogate::encode_os;

/// 끝났는지 다시 볼 때까지 쉬는 가장 긴 틈. stdout 이 닫힌 뒤 git 은 대개 곧 끝나므로 짧게 시작해 늘린다.
const POLL_MAX: Duration = Duration::from_millis(10);

/// 한도 안에 끝난 git.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Finished {
    /// python `returncode`: 신호로 끝나면 음수.
    pub code: i32,
    pub stdout: Vec<u8>,
}

impl Finished {
    /// 0 으로 끝났을 때만 stdout(python `if p.returncode == 0: return p.stdout`).
    pub fn success(self) -> Option<Vec<u8>> {
        (self.code == 0).then_some(self.stdout)
    }
}

/// python 글 인자를 OS 인자로(`os.fsencode`). NUL 이나 짝 없는 서로게이트가 든 글은 python 이 예외를 내는 자리라 `None`.
pub fn os_arg(text: &str) -> Option<OsString> {
    if text.contains('\0') {
        return None;
    }
    encode_os(text).map(bytes_to_os)
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

/// `git <args>` 를 돌린다. 띄우지 못하거나 `timeout` 을 넘기면(그때는 죽인다) `None`.
///
/// `timeout` 은 띄운 때부터 git 이 끝날 때까지다.
pub fn run(args: &[OsString], stdin: Option<Vec<u8>>, timeout: Duration) -> Option<Finished> {
    let mut git = Command::new("git");
    git.args(args);
    run_command(git, stdin, timeout)
}

// 프로그램 하나를 한도 안에서 돌린다(시험은 git 아닌 프로그램으로 부른다)
fn run_command(
    mut command: Command,
    stdin: Option<Vec<u8>>,
    timeout: Duration,
) -> Option<Finished> {
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
    let Ok(Ok(stdout)) = recv.recv_timeout(deadline.saturating_duration_since(Instant::now()))
    else {
        stop(&mut child);
        return None;
    };
    let status = wait_until(&mut child, deadline)?;
    Some(Finished {
        code: exit_code(status),
        stdout,
    })
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

// python returncode: 신호로 끝나면 그 신호 번호의 음수
#[cfg(unix)]
fn exit_code(status: ExitStatus) -> i32 {
    use std::os::unix::process::ExitStatusExt;
    status
        .code()
        .unwrap_or_else(|| -status.signal().unwrap_or(1))
}

#[cfg(not(unix))]
fn exit_code(status: ExitStatus) -> i32 {
    status.code().unwrap_or(1)
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

    /// 끝난 git 은 종료 코드와 stdout 을 주고, `success` 는 0 일 때만 stdout 이다.
    #[test]
    fn output_and_exit_code() {
        let version = run(&["--version".into()], None, Duration::from_secs(5)).unwrap();
        assert_eq!(version.code, 0);
        assert!(version.stdout.starts_with(b"git version"));

        // git exits 1 for an unknown subcommand
        let bad = run(&["no-such-subcommand".into()], None, Duration::from_secs(5)).unwrap();
        assert_ne!(bad.code, 0);
        assert_eq!(bad.success(), None);
    }

    /// 주어진 stdin 바이트는 프로그램에 그대로 간다.
    #[cfg(unix)]
    #[test]
    fn stdin_reaches_the_child() {
        let cat = Command::new("cat");
        let done = run_command(cat, Some(b"a\0b".to_vec()), Duration::from_secs(5)).unwrap();
        assert_eq!(done.stdout, b"a\0b");
    }

    /// 신호로 끝난 프로그램의 코드는 python 처럼 신호 번호의 음수다.
    #[cfg(unix)]
    #[test]
    fn signal_is_a_negative_code() {
        let mut die = Command::new("sh");
        die.args(["-c", "kill -9 $$"]);
        let done = run_command(die, None, Duration::from_secs(5)).unwrap();
        assert_eq!(done.code, -9);
    }

    /// stdout 을 닫고도 끝나지 않는 프로그램은 한도에서 죽인다(python 은 호출 전체에 timeout 을 건다).
    #[cfg(unix)]
    #[test]
    fn deadline_covers_the_exit_too() {
        // stdout reaches EOF at once, the process lives on
        let mut nap = Command::new("sh");
        nap.args(["-c", "exec >&-; sleep 3"]);
        let t0 = Instant::now();
        assert_eq!(run_command(nap, None, Duration::from_millis(300)), None);
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
        let out = run_command(probe, None, Duration::from_secs(5)).unwrap();
        assert_eq!(String::from_utf8_lossy(&out.stdout).trim(), "closed");
    }

    /// NUL 이 든 인자는 OS 인자로 바꾸지 않는다(python ValueError).
    #[test]
    fn os_arg_refuses_nul() {
        assert_eq!(os_arg("a\0b"), None);
        assert_eq!(os_arg("-C"), Some(OsString::from("-C")));
    }
}
