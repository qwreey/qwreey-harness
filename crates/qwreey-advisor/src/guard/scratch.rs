//! 리뷰어 스크래치 폴더(python `SCRATCH_BASE`, `in_scratch`).
//!
//! 가드는 리뷰어의 run 폴더를 모른다. 그래서 `<base>/<아무 이름>/...` 을 허용하고 base 자체와 그 밖은 거부한다.

use harness_hook::Env;
use harness_hook::py::path::{expanduser, join, normpath};

use crate::pylib::pathx::relpath;

use super::Cwd;

/// 스크래치 base 와 `~` 를 풀 환경.
pub struct Scratch {
    base: String,
    env: Env,
}

impl Scratch {
    /// `base` 는 `CLAUDE_AUDIT_SCRATCH`, 없으면 `/tmp/claude-audit`.
    pub fn new(base: String, env: &Env) -> Scratch {
        Scratch {
            base,
            env: env.clone(),
        }
    }

    /// 거절 사유에 쓰는 base 글.
    pub fn base(&self) -> &str {
        &self.base
    }

    /// python `in_scratch(path, cwd)`: base 아래 한 단계 이상 안쪽인가. python 이 예외로 끝나는 입력은 `Err`.
    pub fn contains(&self, path: &str, cwd: &Cwd) -> Result<bool, &'static str> {
        if path.is_empty() {
            return Ok(false);
        }
        let Cwd::Text(cwd) = cwd else {
            return Err("cwd is not a string");
        };
        if has_nul_user(path) {
            return Err("embedded null character in the user name");
        }

        // Resolve against cwd, then relative to the base
        let full = normpath(&join(cwd, &expanduser(path, &self.env)));
        let rel =
            relpath(&full, &normpath(&self.base)).ok_or("cannot read the current directory")?;
        Ok(rel != "." && rel != ".." && !rel.starts_with("../") && !rel.starts_with('/'))
    }
}

// python pwd.getpwnam 은 NUL 이 든 이름에 ValueError 를 낸다(`~na<NUL>me/x`)
fn has_nul_user(path: &str) -> bool {
    let Some(rest) = path.strip_prefix('~') else {
        return false;
    };
    let user = rest.split('/').next().unwrap_or("");
    user.contains('\0')
}

#[cfg(test)]
mod tests {
    use super::*;

    fn scratch() -> Scratch {
        Scratch::new(
            "/tmp/claude-audit".to_owned(),
            &Env::from_pairs([("HOME", "/h")]),
        )
    }

    fn inside(path: &str) -> bool {
        scratch()
            .contains(path, &Cwd::Text("/code/x".to_owned()))
            .expect("text cwd")
    }

    /// base 아래 run 폴더 안만 허용하고 base 자체, 위로 나가는 경로, 상대 경로는 막는다.
    #[test]
    fn only_paths_below_the_base() {
        // Inside a run folder
        assert!(inside("/tmp/claude-audit/S1/probe.luau"));
        assert!(
            inside("/tmp/claude-audit/S1"),
            "a run folder itself is below the base"
        );

        // The base and escapes from it
        assert!(!inside("/tmp/claude-audit"));
        assert!(!inside("/tmp/claude-audit/../x"));
        assert!(!inside("/tmp/claude-audit/S1/../../x"));
        assert!(!inside(""), "an empty path is never inside");

        // Relative paths resolve against cwd
        assert!(!inside("probe.luau"));
        assert!(!inside("~/x"), "~ expands to HOME");
    }
}
