//! python `subprocess.run(["git", "-C", cwd, *args], capture_output=True, text=True, timeout=5)`.
//!
//! 띄우는 일은 [`harness_hook::git`] 이 맡는다(한도는 호출 전체, 물려받은 fd 는 넘기지 않는다). python 과 같게 하는 것:
//! - stdout 은 UTF-8 로 엄격히 읽는다(UTF-8 모드의 `text=True`). 어긋나면 python 은 UnicodeDecodeError 를 내고 훅이 그
//!   자리에서 끝난다: [`GitError::Decode`]. 줄 끝은 `\r\n`, `\r` 을 `\n` 으로 바꾼다(universal newlines).
//! - 띄우지 못하거나 5초를 넘기면(python OSError, TimeoutExpired) 부르는 쪽이 빈 출력으로 본다: [`GitError::Failed`].
//! - 인자에 NUL 이나 바이트로 바꿀 수 없는 서로게이트가 있으면 python 은 ValueError, UnicodeEncodeError: [`GitError::BadArg`].
//! - 0 이 아닌 종료 코드는 실패가 아니다: 코드와 stdout 을 그대로 돌려준다.

use std::ffi::OsString;
use std::time::Duration;

use harness_hook::git;
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
    let done = git::run(&argv, None, TIMEOUT).ok_or(GitError::Failed)?;

    // Strict UTF-8 like text=True, then universal newlines
    let text = String::from_utf8(done.stdout).map_err(|_| GitError::Decode)?;
    Ok(GitOutput {
        code: done.code,
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
    git::os_arg(text).ok_or(GitError::BadArg)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 0 이 아닌 종료 코드도 결과이고, NUL 이 든 인자는 python 의 예외 자리다.
    #[test]
    fn codes_and_bad_args() {
        let bad = run("/", &["no-such-subcommand"]).unwrap();
        assert_ne!(bad.code, 0);
        assert_eq!(run("/", &["a\0b"]), Err(GitError::BadArg));
    }
}
