//! 한 번 실행하는 동안의 환경: [`HookEnv`](환경 변수, 플러그인 폴더, 임시 폴더)와 이 플러그인의 설정.

use std::cell::OnceCell;
use std::path::PathBuf;

use harness_hook::py::path::join;
use harness_hook::settings::{self, LoadRequest, Project};
use harness_hook::{Env, HookEnv, Nonce};

use crate::abort::{Abort, Result};
use crate::config::{Config, USER_ONLY};

/// 실행 환경([`HookEnv`])과 이 플러그인의 설정. 설정은 처음 쓸 때 한 번 읽는다(python 의 모듈 캐시 자리).
#[derive(Debug)]
pub struct Context {
    /// 환경 변수, 바이너리 자리(`native/`, python 판은 `scripts/`), 임시 폴더, 플러그인 폴더.
    pub hook: HookEnv,
    config: OnceCell<Config>,
}

impl Context {
    /// 지금 프로세스의 환경과 실행 파일 자리.
    pub fn from_process() -> Context {
        Context::from_hook(HookEnv::from_process())
    }

    /// 주어진 환경(시험용).
    pub fn new(env: Env, exe_dir: Option<PathBuf>) -> Context {
        Context::from_hook(HookEnv::new(env, exe_dir))
    }

    fn from_hook(hook: HookEnv) -> Context {
        Context {
            hook,
            config: OnceCell::new(),
        }
    }

    /// 설정(python `config.load()`). harness.env 층을 읽지 못하면(홈을 모름) 기본값과 환경 변수만.
    pub fn config(&self) -> &Config {
        self.config.get_or_init(|| {
            let request = LoadRequest {
                project: Project::FromEnv,
                user_only: USER_ONLY,
                plugin_dir: self.hook.exe_dir.as_deref(),
                ..LoadRequest::default()
            };
            let layers = settings::load_layers(&self.hook.env, &request).unwrap_or_default();
            Config::from_layers(&layers.values, &self.hook.env)
        })
    }

    /// python `tempfile.gettempdir()`. 쓸 수 있는 곳이 없으면 `None`.
    pub fn tempdir(&self) -> Option<&str> {
        self.hook.tempdir()
    }

    /// 플러그인 폴더(python 판 스크립트의 `scripts/` 의 부모).
    ///
    /// python 은 `os.path.abspath(__file__)` 라 hooks.json 이 준 `${CLAUDE_PLUGIN_ROOT}` 글 그대로다. 그래서 그 값을 먼저 쓰고,
    /// 없으면 바이너리 자리(`native/` 의 부모)를 쓴다([`HookEnv::plugin_root`]).
    pub fn plugin_root(&self) -> Option<String> {
        self.hook.plugin_root()
    }

    /// 요약 워커(`scripts/cli.py`) 경로.
    pub fn worker_script(&self) -> Option<String> {
        Some(join(&join(&self.plugin_root()?, "scripts"), "cli.py"))
    }

    /// 세션 id 글(python `str(sid)`)의 nonce. id 가 없거나 salt 가 없으면 `None`.
    ///
    /// 짝 없는 서로게이트가 든 id 는 python 이 예외를 내는 자리라 [`Abort`]([`Nonce::for_session`]).
    pub fn nonce(&self, session_id: Option<&str>) -> Result<Option<Nonce>> {
        Nonce::for_session(&self.hook.env, session_id)
            .map_err(|_| Abort("session id has a lone surrogate"))
    }
}
