//! 훅 한 번이 도는 동안의 환경: 환경 변수, 실행 파일 자리, 플러그인 폴더, 임시 폴더, python 처럼 읽는 nonce 와 저장소 폴더.
//!
//! 플러그인 crate 마다 같은 것을 짜던 자리(python 훅의 `os.environ`, `tempfile.gettempdir()`, `harness_nonce.attr(sid)`,
//! `harness_env.project_dir(cwd)`)를 모았다. 훅 입력 값은 python 처럼 어떤 JSON 값이든 `str()` 로 읽는다.

use std::cell::OnceCell;
use std::path::PathBuf;

use crate::env::Env;
use crate::nonce::{self, Nonce, Unencodable};
use crate::py::path::{abspath, normpath};
use crate::py::repr::str_value;
use crate::py::surrogate::{from_os, to_os};
use crate::py::tempfile::gettempdir;
use crate::py::value::Value;
use crate::settings::Project;

/// 실행 환경. 임시 폴더는 처음 쓸 때 한 번 찾는다(python `tempfile` 의 모듈 캐시 자리).
#[derive(Debug)]
pub struct HookEnv {
    pub env: Env,
    /// 바이너리가 든 폴더(`native/`). python 판의 스크립트 폴더(`hooks/`, `scripts/`) 자리다.
    pub exe_dir: Option<PathBuf>,
    tempdir: OnceCell<Option<String>>,
}

/// 저장소 폴더 자리에 글이 아닌 참 값이 왔다. python `Path(cwd)` 가 TypeError 를 내는 자리다.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct NotText;

impl HookEnv {
    /// 지금 프로세스의 환경과 실행 파일 자리.
    pub fn from_process() -> HookEnv {
        let exe_dir = std::env::current_exe()
            .ok()
            .and_then(|exe| exe.parent().map(PathBuf::from));
        HookEnv::new(Env::from_process(), exe_dir)
    }

    /// 주어진 환경과 실행 파일 자리(시험용).
    pub fn new(env: Env, exe_dir: Option<PathBuf>) -> HookEnv {
        HookEnv {
            env,
            exe_dir,
            tempdir: OnceCell::new(),
        }
    }

    /// python `os.environ.get(key)`: UTF-8 이 아닌 값도 python 처럼 서로게이트 자리표로 읽는다.
    pub fn var(&self, key: &str) -> Option<String> {
        self.env.get_os(key).map(from_os)
    }

    /// python `tempfile.gettempdir()`. 쓸 수 있는 곳이 없으면 `None`(python 은 FileNotFoundError).
    pub fn tempdir(&self) -> Option<&str> {
        self.tempdir
            .get_or_init(|| gettempdir(&self.env))
            .as_deref()
    }

    /// 플러그인 폴더: `${CLAUDE_PLUGIN_ROOT}`, 없으면 바이너리 자리(`native/`)의 부모.
    ///
    /// python 판은 스크립트 자리의 부모다. Claude Code 는 그 둘이 같은 폴더인 `${CLAUDE_PLUGIN_ROOT}` 를 준다.
    pub fn plugin_root(&self) -> Option<String> {
        if let Some(root) = self.env.get_os_nonempty("CLAUDE_PLUGIN_ROOT") {
            let root = from_os(root);
            return if root.starts_with('/') {
                Some(normpath(&root))
            } else {
                abspath(&root)
            };
        }
        let parent = self.exe_dir.as_ref()?.parent()?;
        Some(from_os(parent.as_os_str()))
    }

    /// 플러그인 옵션 층이 plugin.json 을 찾기 시작할 폴더: [`HookEnv::plugin_root`], 없으면 바이너리 자리.
    ///
    /// python 판은 스크립트 자리에서 위로 찾는다. 시험은 바이너리를 `target/` 에서 돌리므로 플러그인 폴더를 먼저 본다.
    pub fn settings_dir(&self) -> Option<PathBuf> {
        match self.plugin_root() {
            Some(root) => to_os(&root),
            None => self.exe_dir.clone(),
        }
    }

    /// python `harness_nonce.nonce(session_id)`: 거짓 값이면 없음, 아니면 `str(session_id)` 의 nonce.
    ///
    /// 짝 없는 서로게이트가 든 id 는 python 이 UnicodeEncodeError 를 내는 자리라 `Err` 다.
    pub fn nonce(&self, session_id: Option<&Value>) -> Result<Option<Nonce>, Unencodable> {
        let sid = session_id.filter(|v| v.truthy()).map(str_value);
        Nonce::for_session(&self.env, sid.as_deref())
    }

    /// python `harness_nonce.attr(session_id)`: ` nonce="N"` 또는 빈 글.
    pub fn nonce_attr(&self, session_id: Option<&Value>) -> Result<String, Unencodable> {
        Ok(nonce::attr(self.nonce(session_id)?.as_ref()))
    }

    /// python `harness_env.project_dir(cwd)`: 저장소 층의 루트.
    ///
    /// `$CLAUDE_PROJECT_DIR`, 없으면 `cwd`, 둘 다 없으면 [`Project::FromEnv`]. `cwd` 는 훅 입력 값 그대로다. 글이 아닌 참 값이면 python `Path(cwd)` 가 TypeError 를 낸다: [`NotText`].
    pub fn project(&self, cwd: Option<&Value>) -> Result<Project, NotText> {
        if let Some(dir) = self.env.get_nonempty("CLAUDE_PROJECT_DIR") {
            return Ok(Project::Dir(dir.to_owned()));
        }
        match cwd.filter(|v| v.truthy()) {
            None => Ok(Project::FromEnv),
            Some(Value::Str(dir)) => Ok(Project::Dir(dir.clone())),
            Some(_) => Err(NotText),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 글이 아닌 cwd 는 `$CLAUDE_PROJECT_DIR` 가 없을 때만 오류이고, 거짓 값은 없는 것과 같다.
    #[test]
    fn project_reads_cwd_like_python() {
        let bare = HookEnv::new(Env::from_pairs::<&str, &str, _>([]), None);
        assert_eq!(bare.project(Some(&Value::Int(3))), Err(NotText));
        assert_eq!(bare.project(Some(&Value::Int(0))), Ok(Project::FromEnv));
        assert_eq!(
            bare.project(Some(&Value::Str("/r".into()))),
            Ok(Project::Dir("/r".into()))
        );

        let with_dir = HookEnv::new(Env::from_pairs([("CLAUDE_PROJECT_DIR", "/p")]), None);
        assert_eq!(
            with_dir.project(Some(&Value::Int(3))),
            Ok(Project::Dir("/p".into()))
        );
    }

    /// 목록인 session_id 도 python 처럼 `str()` 한 글로 nonce 를 만든다.
    #[test]
    fn nonce_uses_python_str() {
        let dir = std::env::temp_dir().join(format!("hh-hookenv-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let salt = dir.join("salt");
        std::fs::write(&salt, "00".repeat(32)).unwrap();
        let env = Env::from_pairs([("QWREEY_HARNESS_SALT_FILE", salt.as_os_str())]);
        let hook = HookEnv::new(env, None);

        let list = Value::List(vec![Value::Str("a".into())]);
        let want = Nonce::from_salt(&"00".repeat(32), "['a']");
        assert_eq!(hook.nonce(Some(&list)), Ok(Some(want)));
        assert_eq!(hook.nonce(Some(&Value::Str(String::new()))), Ok(None));
        std::fs::remove_dir_all(&dir).unwrap();
    }
}
