//! 훅마다 둔 끄기 스위치(python 두 훅의 `is_off(cwd)`).

use harness_hook::HookEnv;
use harness_hook::py::text::strip;
use harness_hook::py::value::Value;
use harness_hook::settings::{self, LoadRequest};

use crate::stop::{Result, Stop};

/// 스위치를 끈 값(앞뒤 공백을 떼고 소문자로 견준다).
const OFF_VALUES: &[&str] = &["off", "0", "no"];

/// 스위치 `name` 이 꺼졌나. 환경 변수가 이기고, 없으면 harness.env 층(사용자 < 플러그인 옵션 < 저장소 < 저장소 local).
///
/// 층의 기본값은 `on` 이다. python 은 `Path(cwd)` 와 `Path.home()` 의 예외를 잡지 않아 훅이 아무것도 내지 않는다.
pub fn switched_off(hook: &HookEnv, name: &str, cwd: Option<&Value>) -> Result<bool> {
    if let Some(value) = hook.var(name) {
        return Ok(is_off_word(&value));
    }

    // Layers with this switch on by default
    let project = hook
        .project(cwd)
        .map_err(|_| Stop::Raises("Path(cwd) of a value that is not text"))?;
    let defaults = [(name, "on")];
    let request = LoadRequest {
        project,
        defaults: &defaults,
        plugin_dir: hook.exe_dir.as_deref(),
        ..LoadRequest::default()
    };
    let layers = settings::load_layers(&hook.env, &request)
        .map_err(|_| Stop::Raises("Path.home() without a home"))?;
    Ok(is_off_word(layers.get(name).unwrap_or("")))
}

fn is_off_word(value: &str) -> bool {
    OFF_VALUES.contains(&strip(value).to_lowercase().as_str())
}

#[cfg(test)]
mod tests {
    use super::*;
    use harness_hook::Env;

    /// 환경 변수의 off, 0, no 는 공백과 대소문자를 가리지 않고 끈 것이다.
    #[test]
    fn env_words_switch_off() {
        let off = |value: &str| {
            let hook = HookEnv::new(Env::from_pairs([("X_SWITCH", value)]), None);
            switched_off(&hook, "X_SWITCH", None).unwrap()
        };
        assert!(off(" OFF\n"));
        assert!(off("0"));
        assert!(off("No"));
        assert!(!off("false"));
        assert!(!off(""));
    }
}
