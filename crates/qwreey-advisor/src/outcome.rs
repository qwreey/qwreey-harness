//! 훅 한 번의 결과: 종료 코드, stdout, stderr 바이트.

use harness_hook::py::surrogate::encode_os;

use crate::pylib::text::stderr_bytes;

/// 훅이 낸 것. 하위 명령마다 이것을 돌려주고 `main` 이 쓴다.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct Outcome {
    pub code: u8,
    pub stdout: Vec<u8>,
    pub stderr: Vec<u8>,
}

impl Outcome {
    /// 아무것도 내지 않고 0.
    pub fn quiet() -> Outcome {
        Outcome::default()
    }

    /// python `print(text)`(UTF-8, surrogateescape) 의 stdout. 쓰지 못하는 글이면 `None`.
    ///
    /// 바이트로 되돌릴 수 없는 서로게이트가 있으면 python 은 UnicodeEncodeError 로 아무것도 쓰지 않는다.
    pub fn printed(text: &str) -> Option<Outcome> {
        let mut stdout = encode_os(text)?;
        stdout.push(b'\n');
        Some(Outcome {
            stdout,
            ..Outcome::default()
        })
    }

    /// python `print(text, file=sys.stderr)`(backslashreplace) 뒤 `sys.exit(code)`.
    pub fn stderr_line(code: u8, text: &str) -> Outcome {
        let mut stderr = stderr_bytes(text);
        stderr.push(b'\n');
        Outcome {
            code,
            stderr,
            ..Outcome::default()
        }
    }
}
