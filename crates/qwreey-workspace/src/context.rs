//! 한 번 실행하는 동안의 환경: [`HookEnv`](환경 변수, 실행 파일 자리, 임시 폴더, nonce)와 harness.env 층(python `wslib.load_env`).

use std::path::PathBuf;

use harness_hook::py::value::Value;
use harness_hook::settings::{self, LoadRequest, Values};
use harness_hook::{Env, HookEnv, known_repos};

use crate::pyval::truthy_text;
use crate::stop::{Result, Stop};

/// 이 플러그인의 이름(compact 회차 폴더 `claude-qwreey-workspace-epoch`).
pub const PLUGIN: &str = "qwreey-workspace";

/// 이 플러그인만 읽는 harness.env 키의 기본값(python `wslib.ENV_DEFAULTS`, plugin.json userConfig 의 default 와 같다).
pub const ENV_DEFAULTS: &[(&str, &str)] = &[
    ("HARNESS_WORKSPACE_GATE", "on"),
    ("HARNESS_WORKSPACE_STALE_WORKTREES", "on"),
    ("HARNESS_WORKSPACE_STALE_WORKTREE_DAYS", "14"),
    ("HARNESS_WORKSPACE_SIBLING_NOTICE", "on"),
];

/// 저장소 층이 바꾸지 못하는 키(python `wslib.ENV_USER_ONLY`): 게이트를 끄거나 비켜 가게 하는 키.
pub const ENV_USER_ONLY: &[&str] = &[
    "HARNESS_WORKSPACE_GATE",
    "HARNESS_WORKSPACE_EXTRA",
    "HARNESS_WORKSPACE_EXCLUDE",
];

/// 실행 환경([`HookEnv`])에 이 플러그인의 설정 층과 상태 파일 자리를 더한 것.
#[derive(Debug)]
pub struct Context {
    /// 환경 변수, 바이너리 자리(`native/`, python 판은 `scripts/`), 임시 폴더, nonce.
    pub hook: HookEnv,
}

impl Context {
    /// 지금 프로세스의 환경과 실행 파일 자리.
    pub fn from_process() -> Context {
        Context {
            hook: HookEnv::from_process(),
        }
    }

    /// 주어진 환경(시험용).
    pub fn new(env: Env, exe_dir: Option<PathBuf>) -> Context {
        Context {
            hook: HookEnv::new(env, exe_dir),
        }
    }

    /// python `os.environ.get(key)`: UTF-8 이 아닌 값도 python 처럼 서로게이트 자리표로 읽는다.
    pub fn env_var(&self, key: &str) -> Option<String> {
        self.hook.var(key)
    }

    /// python `tempfile.gettempdir()`. 쓸 수 있는 곳이 없으면 python 은 예외로 끝난다.
    pub fn tempdir(&self) -> Result<&str> {
        self.hook
            .tempdir()
            .ok_or(Stop::Raises("no usable temporary directory"))
    }

    /// python `wslib.load_env(cwd)`: harness.env 층(사용자 < 옵션 < 저장소 < 저장소 local < 환경 변수). 읽지 못하면 빈 값.
    ///
    /// `cwd` 는 훅 입력의 `cwd` 값이다. `$CLAUDE_PROJECT_DIR` 가 비었고 `cwd` 가 문자열이 아닌 참 값이면 python 은
    /// `Path(cwd)` 에서 TypeError 를 내고 `{}` 로 본다.
    pub fn load_env(&self, cwd: Option<&Value>) -> Values {
        let Ok(project) = self.hook.project(cwd) else {
            return Values::new();
        };

        // 이 플러그인 키와 known_repos 의 키를 함께 기본값으로
        let defaults: Vec<(&str, &str)> = known_repos::DEFAULTS
            .iter()
            .chain(ENV_DEFAULTS)
            .copied()
            .collect();
        let request = LoadRequest {
            project,
            defaults: &defaults,
            user_only: ENV_USER_ONLY,
            plugin_dir: self.hook.exe_dir.as_deref(),
            ..LoadRequest::default()
        };
        settings::load_layers(&self.hook.env, &request)
            .map(|layers| layers.values)
            .unwrap_or_default()
    }

    /// python `wslib.is_off(key, vals)`: 환경 변수, 없으면 층 값이 `off`, `0`, `no`, `false`(앞뒤 공백, 대소문자 무시)인가.
    pub fn is_off(&self, key: &str, vals: &Values) -> bool {
        let value = match self.env_var(key) {
            Some(v) => v,
            None => vals.get(key).cloned().unwrap_or_default(),
        };
        let word = harness_hook::py::text::strip(&value).to_lowercase();
        matches!(word.as_str(), "off" | "0" | "no" | "false")
    }

    /// python `harness_nonce.attr(session_id)`: ` nonce="N"` 또는 빈 글.
    ///
    /// 짝 없는 서로게이트가 든 id 는 python 이 UnicodeEncodeError 로 끝나는 자리다.
    pub fn nonce_attr(&self, session_id: Option<&Value>) -> Result<String> {
        self.hook
            .nonce_attr(session_id)
            .map_err(|_| Stop::Raises("session id has a lone surrogate"))
    }

    /// 이 회차의 dedup 상태 파일 경로. 폴더를 만든다.
    ///
    /// python `compact_epoch.state_path(PLUGIN, namespace, sid, agent_id)` 자리다.
    pub fn state_path(
        &self,
        namespace: &str,
        session_id: Option<&Value>,
        agent_id: Option<&Value>,
    ) -> Result<String> {
        let sid = truthy_text(session_id);
        let agent = truthy_text(agent_id);
        let agent = (!agent.is_empty()).then_some(agent.as_str());
        harness_hook::epoch::state_path(self.tempdir()?, PLUGIN, namespace, &sid, agent)
            .map_err(|_| Stop::Raises("cannot make the state folder"))
    }
}
