//! 한 번 실행하는 동안의 환경: [`HookEnv`](환경 변수, 실행 파일 자리, 임시 폴더, nonce)와 이 플러그인의 harness.env 층
//! (python `conv_env.py`).

use std::cell::OnceCell;
use std::path::{Path, PathBuf};

use harness_hook::py::fs;
use harness_hook::py::path::abspath;
use harness_hook::py::surrogate::from_os;
use harness_hook::py::text::strip;
use harness_hook::py::value::Value;
use harness_hook::settings::{self, LoadRequest, Project, Values};
use harness_hook::{Env, HookEnv};

use crate::halt::{Halt, Result};

/// 이 플러그인의 이름(태그 이름, compact 회차 폴더 `claude-qwreey-conventions-epoch`).
pub const PLUGIN: &str = "qwreey-conventions";

/// 이 플러그인만 읽는 harness.env 키의 기본값(python `conv_env.ENV_DEFAULTS`, plugin.json userConfig 의 default 와 같다).
pub const ENV_DEFAULTS: &[(&str, &str)] = &[
    ("HARNESS_READABLE_CODE", "on"),
    ("HARNESS_CONVENTIONS_RULES", "on"),
    ("CONVENTIONS_CHECK", "on"),
    ("STRUCTURE_REMINDER", "on"),
    ("MEMORY_PLACEMENT", "on"),
];

/// 실행 환경([`HookEnv`])과 이 플러그인의 harness.env 층. 층은 처음 쓸 때 한 번 읽는다(python 의 모듈 전역 캐시 자리).
#[derive(Debug)]
pub struct Context {
    /// 환경 변수, 임시 폴더, nonce, 바이너리가 든 `native/`(플러그인 옵션 층이 여기서 위로 plugin.json 을 찾는다,
    /// python 판은 `hooks/`).
    pub hook: HookEnv,
    layers: OnceCell<Values>,
}

impl Context {
    /// 지금 프로세스의 환경과 실행 파일 자리.
    ///
    /// 자리는 부른 경로(argv[0])의 폴더다. python 판의 `__file__` 처럼 링크를 풀지 않는다(bash-bypass-reminder 가
    /// rule 파일 경로를 모델에게 보인다). 경로 없이 이름으로 불렸으면 실행 파일의 실제 자리.
    pub fn from_process() -> Context {
        let invoked = std::env::args_os()
            .next()
            .filter(|p| PathBuf::from(p).components().count() > 1)
            .and_then(|p| abspath(&from_os(&p)))
            .and_then(|p| fs::os_path(&p));
        let exe = invoked.or_else(|| std::env::current_exe().ok());
        let exe_dir = exe.and_then(|exe| exe.parent().map(PathBuf::from));
        Context::new(Env::from_process(), exe_dir)
    }

    /// 주어진 환경(시험용).
    pub fn new(env: Env, exe_dir: Option<PathBuf>) -> Context {
        Context {
            hook: HookEnv::new(env, exe_dir),
            layers: OnceCell::new(),
        }
    }

    /// python `tempfile.gettempdir()`. 쓸 수 있는 곳이 없으면 python 은 예외로 끝난다.
    pub fn tempdir(&self) -> Result<&str> {
        self.hook
            .tempdir()
            .ok_or(Halt::PyError("no usable temporary directory"))
    }

    /// harness.env 층(python `harness_env.load_layers(defaults=..., user_only=...)`)을 읽는다. 읽지 못하면 빈 값.
    pub fn load_layers(&self, defaults: &[(&str, &str)], user_only: &[&str]) -> Values {
        let request = LoadRequest {
            project: Project::FromEnv,
            defaults,
            user_only,
            plugin_dir: self.hook.exe_dir.as_deref(),
            ..LoadRequest::default()
        };
        settings::load_layers(&self.hook.env, &request)
            .map(|layers| layers.values)
            .unwrap_or_default()
    }

    // python conv_env._layers: 처음 부를 때 한 번
    fn conv_layers(&self) -> &Values {
        self.layers
            .get_or_init(|| self.load_layers(ENV_DEFAULTS, &[]))
    }

    /// python `conv_env.env_value(name)`: 환경 변수, 없으면 층 값, 없으면 기본값. 앞뒤 공백은 뗀다.
    pub fn env_value(&self, name: &str) -> String {
        if let Some(v) = self.hook.env.get(name) {
            return strip(v).to_owned();
        }
        let fallback = ENV_DEFAULTS
            .iter()
            .find(|(k, _)| *k == name)
            .map_or("", |(_, v)| *v);
        let value = self
            .conv_layers()
            .get(name)
            .map_or(fallback, String::as_str);
        strip(value).to_owned()
    }

    /// python `conv_env.is_off(name)`: 값이 `off`(대소문자 무시)일 때만.
    pub fn is_off(&self, name: &str) -> bool {
        self.env_value(name).to_lowercase() == "off"
    }

    /// python `conv_env.is_on(name)`: 값이 `on`(대소문자 무시)일 때만.
    pub fn is_on(&self, name: &str) -> bool {
        self.env_value(name).to_lowercase() == "on"
    }

    /// 플러그인 옵션 층을 찾을 자리(시험이 바꾼다).
    pub fn plugin_dir(&self) -> Option<&Path> {
        self.hook.exe_dir.as_deref()
    }

    /// python `harness_nonce.attr(data.get("session_id"))`: ` nonce="N"` 또는 빈 글.
    ///
    /// id 가 python 에서 거짓이면 nonce 가 없다. 목록이나 dict 인 id 는 python 처럼 그 repr 글로 nonce 를 만든다.
    /// 짝 없는 서로게이트가 든 id 는 python 이 UnicodeEncodeError 로 끝나는 자리다.
    pub fn nonce_attr(&self, session_id: Option<&Value>) -> Result<String> {
        self.hook
            .nonce_attr(session_id)
            .map_err(|_| Halt::PyError("session id has a lone surrogate"))
    }
}
