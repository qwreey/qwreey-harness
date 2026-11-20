//! 한 번 실행하는 동안의 환경: 환경 변수, 플러그인 폴더, 임시 폴더, nonce, 설정 층.

use std::cell::OnceCell;
use std::path::PathBuf;

use harness_hook::nonce::{self, Unencodable};
use harness_hook::py::path::{abspath, normpath};
use harness_hook::py::surrogate::{from_os, to_os};
use harness_hook::py::tempfile::gettempdir;
use harness_hook::py::text::strip;
use harness_hook::py::value::Value;
use harness_hook::settings::{self, LoadRequest};
use harness_hook::{Env, Nonce};

/// 이 플러그인만 읽는 harness.env 키의 기본값(python `reply_env.ENV_DEFAULTS`). plugin.json userConfig 의 기본값과 같다.
pub const ENV_DEFAULTS: &[(&str, &str)] = &[("HARNESS_REPLY_LANGUAGE", "on")];

/// 실행 환경. 임시 폴더는 처음 쓸 때 한 번 찾는다.
#[derive(Debug)]
pub struct Context {
    pub env: Env,
    /// 바이너리가 든 `native/`.
    pub exe_dir: Option<PathBuf>,
    tempdir: OnceCell<Option<String>>,
}

impl Context {
    /// 지금 프로세스의 환경과 실행 파일 자리.
    pub fn from_process() -> Context {
        let exe_dir = std::env::current_exe()
            .ok()
            .and_then(|exe| exe.parent().map(PathBuf::from));
        Context {
            env: Env::from_process(),
            exe_dir,
            tempdir: OnceCell::new(),
        }
    }

    /// python `tempfile.gettempdir()`. 쓸 수 있는 곳이 없으면 `None`.
    pub fn tempdir(&self) -> Option<&str> {
        self.tempdir
            .get_or_init(|| gettempdir(&self.env))
            .as_deref()
    }

    /// 플러그인 폴더: `${CLAUDE_PLUGIN_ROOT}`, 없으면 바이너리 자리(`native/` 의 부모).
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

    /// python `reply_env.is_off(name)`: 환경 변수가 이기고, 없으면 harness.env 층과 플러그인 옵션. 값이 off 면 참.
    ///
    /// 층을 읽지 못하면(홈을 모름) 기본값(켜짐)이다.
    pub fn is_off(&self, name: &str) -> bool {
        let value = match self.env.get_os(name) {
            Some(v) => from_os(v),
            None => {
                let settings_dir = match self.plugin_root() {
                    Some(root) => to_os(&root),
                    None => self.exe_dir.clone(),
                };
                let request = LoadRequest {
                    defaults: ENV_DEFAULTS,
                    plugin_dir: settings_dir.as_deref(),
                    ..LoadRequest::default()
                };
                let layers = settings::load_layers(&self.env, &request).ok();
                let default = ENV_DEFAULTS
                    .iter()
                    .find(|(k, _)| *k == name)
                    .map_or("", |(_, v)| *v);
                layers
                    .as_ref()
                    .and_then(|l| l.get(name).map(str::to_owned))
                    .unwrap_or_else(|| default.to_owned())
            }
        };
        strip(&value).to_lowercase() == "off"
    }

    /// python `harness_nonce.attr(session_id)`: ` nonce="N"` 또는 빈 글. python 이 예외를 내는 id 는 `Err`.
    ///
    /// 목록이나 dict 인 id 는 python 이 repr 로 nonce 를 만든다. 옮기지 않아 `Err` 로 본다.
    pub fn nonce_attr(&self, session_id: Option<&Value>) -> Result<String, Unencodable> {
        let Some(value) = session_id.filter(|v| v.truthy()) else {
            return Ok(String::new());
        };
        let text = value.scalar_str().ok_or(Unencodable)?;
        let found: Option<Nonce> = Nonce::for_session(&self.env, Some(&text))?;
        Ok(nonce::attr(found.as_ref()))
    }
}
