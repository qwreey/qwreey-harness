//! 이 플러그인만 읽는 설정: 끄기 스위치(python `reply_env.is_off`). 실행 환경은 [`HookEnv`] 다.

use harness_hook::HookEnv;
use harness_hook::py::surrogate::from_os;
use harness_hook::py::text::strip;
use harness_hook::settings::{self, LoadRequest};

/// 이 플러그인만 읽는 harness.env 키의 기본값(python `reply_env.ENV_DEFAULTS`). plugin.json userConfig 의 기본값과 같다.
pub const ENV_DEFAULTS: &[(&str, &str)] = &[("HARNESS_REPLY_LANGUAGE", "on")];

/// python `reply_env.is_off(name)`: 환경 변수가 이기고, 없으면 harness.env 층과 플러그인 옵션. 값이 off 면 참.
///
/// 층을 읽지 못하면(홈을 모름) 기본값(켜짐)이다.
pub fn is_off(ctx: &HookEnv, name: &str) -> bool {
    let value = match ctx.env.get_os(name) {
        Some(v) => from_os(v),
        None => {
            let settings_dir = ctx.settings_dir();
            let request = LoadRequest {
                defaults: ENV_DEFAULTS,
                plugin_dir: settings_dir.as_deref(),
                ..LoadRequest::default()
            };
            let layers = settings::load_layers(&ctx.env, &request).ok();
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
