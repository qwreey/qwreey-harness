//! 한 번 실행하는 동안의 환경: 환경 변수, 플러그인 폴더, 임시 폴더, nonce.

use std::cell::OnceCell;
use std::path::PathBuf;

use harness_hook::nonce::{self, Unencodable};
use harness_hook::py::path::{abspath, normpath};
use harness_hook::py::surrogate::from_os;
use harness_hook::py::tempfile::gettempdir;
use harness_hook::py::value::Value;
use harness_hook::{Env, Nonce};

/// 실행 환경. 임시 폴더는 처음 쓸 때 한 번 찾는다(python `tempfile` 의 모듈 캐시 자리).
#[derive(Debug)]
pub struct Context {
    pub env: Env,
    /// 바이너리가 든 `native/`. 플러그인 옵션 층이 여기서 위로 plugin.json 을 찾는다(python 판은 `hooks/`).
    pub exe_dir: Option<PathBuf>,
    tempdir: OnceCell<Option<String>>,
}

impl Context {
    /// 지금 프로세스의 환경과 실행 파일 자리.
    pub fn from_process() -> Context {
        let exe_dir = std::env::current_exe()
            .ok()
            .and_then(|exe| exe.parent().map(PathBuf::from));
        Context::new(Env::from_process(), exe_dir)
    }

    /// 주어진 환경(시험용).
    pub fn new(env: Env, exe_dir: Option<PathBuf>) -> Context {
        Context {
            env,
            exe_dir,
            tempdir: OnceCell::new(),
        }
    }

    /// python `tempfile.gettempdir()`. 쓸 수 있는 곳이 없으면 `None`(python 은 FileNotFoundError).
    pub fn tempdir(&self) -> Option<&str> {
        self.tempdir
            .get_or_init(|| gettempdir(&self.env))
            .as_deref()
    }

    /// 플러그인 폴더: `${CLAUDE_PLUGIN_ROOT}`, 없으면 바이너리 자리(`native/` 의 부모).
    ///
    /// python 판은 스크립트 자리(`hooks/` 의 부모)다. Claude Code 는 그 둘이 같은 폴더인 `${CLAUDE_PLUGIN_ROOT}` 를 준다.
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

    /// 플러그인 옵션 층이 plugin.json 을 찾기 시작할 폴더: [`Context::plugin_root`], 없으면 바이너리 자리.
    ///
    /// python 판은 스크립트 자리(`hooks/`)에서 위로 찾는다. 시험은 바이너리를 `target/` 에서 돌리므로 플러그인 폴더를 먼저 본다.
    pub fn settings_dir(&self) -> Option<PathBuf> {
        match self.plugin_root() {
            Some(root) => harness_hook::py::surrogate::to_os(&root),
            None => self.exe_dir.clone(),
        }
    }

    /// python `harness_nonce.attr(session_id)`: ` nonce="N"` 또는 빈 글. python 이 예외를 내는 id 는 `Err`.
    pub fn nonce_attr(&self, session_id: Option<&Value>) -> Result<String, Unencodable> {
        Ok(nonce::attr(self.nonce(session_id)?.as_ref()))
    }

    /// python `harness_nonce.nonce(session_id)`: 거짓 값이면 없음, 아니면 `str(session_id)` 의 nonce.
    ///
    /// 목록이나 dict 인 id 는 python 이 repr 로 nonce 를 만든다. 옮기지 않아 `Err` 로 본다.
    pub fn nonce(&self, session_id: Option<&Value>) -> Result<Option<Nonce>, Unencodable> {
        let Some(value) = session_id.filter(|v| v.truthy()) else {
            return Ok(None);
        };
        let text = value.scalar_str().ok_or(Unencodable)?;
        Nonce::for_session(&self.env, Some(&text))
    }
}
