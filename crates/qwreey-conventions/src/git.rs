//! git 을 하위 프로세스로(python `subprocess.run(["git", ...], input=..., capture_output=True, timeout=...)`).
//!
//! 띄우는 일은 [`harness_hook::git`] 이 맡는다(한도는 호출 전체, 물려받은 fd 는 넘기지 않는다). 이 플러그인의 python 판은
//! 0 으로 끝난 stdout 만 쓰므로, 띄우지 못함, 시간 넘김, 0 이 아닌 코드가 모두 `None` 이다.

use std::ffi::OsString;
use std::time::Duration;

use harness_hook::git;

use crate::halt::{Halt, Result};

/// python 글 인자를 OS 인자로(`os.fsencode`). NUL 이나 짝 없는 서로게이트가 든 글은 python 이 예외로 끝나는 자리다.
pub fn os_arg(text: &str) -> Result<OsString> {
    if text.contains('\0') {
        return Err(Halt::PyError("a NUL in a subprocess argument"));
    }
    git::os_arg(text).ok_or(Halt::PyError("an argument python cannot encode"))
}

/// `git <args>` 가 0 으로 끝났을 때의 stdout. `stdin` 이 있으면 그 바이트를 넣고, 없으면 빈 stdin 이다.
///
/// `timeout` 은 띄운 때부터 git 이 끝날 때까지다. 넘기면 죽이고 `None`.
pub fn output(args: &[OsString], stdin: Option<Vec<u8>>, timeout: Duration) -> Option<Vec<u8>> {
    git::run(args, stdin, timeout)?.success()
}

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

    /// NUL 이 든 인자는 python 의 예외 자리다.
    #[test]
    fn nul_arg_halts() {
        assert!(os_arg("a\0b").is_err());
        assert!(os_arg("-C").is_ok());
    }
}
