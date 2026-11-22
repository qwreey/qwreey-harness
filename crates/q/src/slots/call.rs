//! 훅 한 번의 입력과 환경, 그리고 낼 출력(python `tag`, `context`, `deny`, `post_context`).

use harness_hook::HookEnv;
use harness_hook::epoch;
use harness_hook::output::HookOutput;
use harness_hook::py::json::EnsureAscii;
use harness_hook::py::repr::{str_value, truthy_str};
use harness_hook::py::value::{Dict, Value};
use harness_hook::tag::Level;

use super::config::Cfg;
use super::store;
use crate::stop::{Result, Stop};

/// 원장을 고치는 훅 한 번의 재료.
pub struct Call<'a> {
    pub hook: &'a HookEnv,
    pub input: &'a Dict,
    pub cfg: &'a Cfg,
    /// python `tempfile.gettempdir()`.
    pub tempdir: &'a str,
    /// 사용자 설정 폴더(python `HOME`, 사용자 정의 에이전트의 `agents/`).
    pub home: &'a str,
    /// 이 훅이 시작한 시각(python `now = time.time()`).
    pub now: f64,
}

impl Call<'_> {
    /// 입력 값 하나(python `data.get(key)`).
    pub fn get(&self, key: &str) -> Option<&Value> {
        self.input.get(key)
    }

    /// 입력 값이 참이면 그 값.
    pub fn truthy(&self, key: &str) -> Option<&Value> {
        self.input.get(key).filter(|v| v.truthy())
    }

    /// 알림 dedup 의 호출한 쪽: agent_id, 없으면 `main`.
    pub fn who(&self) -> String {
        self.truthy("agent_id")
            .map_or_else(|| "main".to_owned(), str_value)
    }

    /// python `L.epoch(sid)`: q 의 compact 회차.
    pub fn epoch(&self) -> i128 {
        epoch::epoch(self.tempdir, "q", &truthy_str(self.get("session_id")))
    }

    /// python `L.read_limits(sid)`.
    pub fn limits(&self) -> Option<Dict> {
        store::read_limits(self.tempdir, self.get("session_id"))
    }

    /// python `tag(level, body)`: 이 세션의 nonce 를 단 `subagent-slots` 태그.
    pub fn tag(&self, level: Level, body: &str) -> Result<String> {
        let attr = self
            .hook
            .nonce_attr(self.get("session_id"))
            .map_err(|_| Stop::Raises("session id has a lone surrogate"))?;
        Ok(format!(
            "<harness-hook name=\"subagent-slots\" level=\"{}\"{attr}>\n{body}\n</harness-hook>",
            level.as_str()
        ))
    }
}

/// 훅이 낼 것.
#[derive(Clone, Debug, PartialEq, Eq)]
pub enum Out {
    /// PreToolUse 의 additionalContext.
    PreContext(String),
    /// PostToolUse 의 additionalContext.
    PostContext(String),
    /// PreToolUse 에서 막는다(사유는 action 태그).
    Deny(String),
}

impl Out {
    /// python `json.dump(out, sys.stdout, ensure_ascii=False)`.
    pub fn render(&self) -> String {
        let out = match self {
            Out::PreContext(text) => HookOutput::context("PreToolUse", text.as_str()),
            Out::PostContext(text) => HookOutput::context("PostToolUse", text.as_str()),
            Out::Deny(text) => HookOutput::deny(text.as_str()),
        };
        out.render(EnsureAscii::No)
    }
}
