//! 훅 셋이 같이 쓰는 실행 환경: 환경 변수, 플러그인 폴더, 설정 층, nonce.

use std::path::PathBuf;

use harness_hook::py::num::float_repr;
use harness_hook::settings::{self, Layers, LoadRequest, Project};
use harness_hook::{Env, HookInput, Nonce};
use serde_json::Value;

/// 한 번 실행하는 동안의 환경.
#[derive(Clone, Debug)]
pub struct Context {
    pub env: Env,
    /// 플러그인 이름을 찾기 시작할 폴더(바이너리가 든 `native/`). python 판의 `hooks/` 자리다.
    pub plugin_dir: Option<PathBuf>,
}

impl Context {
    /// 지금 프로세스의 환경과 실행 파일 자리.
    pub fn from_process() -> Context {
        let plugin_dir = std::env::current_exe()
            .ok()
            .and_then(|exe| exe.parent().map(PathBuf::from));
        Context {
            env: Env::from_process(),
            plugin_dir,
        }
    }

    /// harness.env 층(python `harness_env.load_layers`). 읽다 실패하면(홈을 모름) 빈 값, python 훅의 `except: return {}` 자리.
    pub fn layers(
        &self,
        project: Project,
        defaults: &[(&str, &str)],
        user_only: &[&str],
    ) -> Layers {
        let req = LoadRequest {
            project,
            defaults,
            user_only,
            plugin_dir: self.plugin_dir.as_deref(),
            ..LoadRequest::default()
        };
        settings::load_layers(&self.env, &req).unwrap_or_default()
    }

    /// 이 세션의 nonce(python `harness_nonce.attr(data.get("session_id"))`).
    pub fn nonce(&self, input: &HookInput) -> Option<Nonce> {
        let sid = py_str(input.raw().get("session_id")?)?;
        Nonce::for_session(&self.env, Some(&sid))
    }
}

/// 저장소 층의 루트(python `harness_env.project_dir(data.get("cwd"))`). `None` 이면 python 에서 예외가 나는 입력이다.
///
/// `$CLAUDE_PROJECT_DIR` 가 비었고 `cwd` 가 문자열이 아닌 참 값(수, 목록)이면 python 은 `Path(cwd)` 에서 TypeError 를 내고
/// 훅은 설정 전체를 `{}` 로 본다.
pub fn project_for(env: &Env, cwd: Option<&Value>) -> Option<Project> {
    match cwd {
        Some(Value::String(s)) => Some(settings::project_dir(env, Some(s))),
        Some(v) if truthy(v) && env.get_nonempty("CLAUDE_PROJECT_DIR").is_none() => None,
        _ => Some(settings::project_dir(env, None)),
    }
}

/// python 의 참거짓(`bool(v)`).
pub fn truthy(v: &Value) -> bool {
    match v {
        Value::Null => false,
        Value::Bool(b) => *b,
        Value::Number(n) => n.as_f64().is_some_and(|f| f != 0.0),
        Value::String(s) => !s.is_empty(),
        Value::Array(a) => !a.is_empty(),
        Value::Object(o) => !o.is_empty(),
    }
}

/// 참인 값의 python `str(v)`. 거짓이면 `None`. 목록과 객체는 옮기지 않아 `None` 이다(Claude Code 는 문자열만 준다).
pub fn py_str(v: &Value) -> Option<String> {
    if !truthy(v) {
        return None;
    }
    match v {
        Value::String(s) => Some(s.clone()),
        Value::Bool(_) => Some("True".to_owned()),
        Value::Number(n) if n.is_f64() => n.as_f64().map(float_repr),
        Value::Number(n) => Some(n.to_string()),
        _ => None,
    }
}
