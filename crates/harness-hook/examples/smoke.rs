//! 공통 crate 만 쓰는 작은 훅. 릴리스 크기와 한 번 띄우는 CPU 를 재는 데 쓴다(워크스페이스 Cargo.toml 의 opt-level 근거).
//!
//! heavy-proc-guard 가 매번 거치는 길과 같은 일을 한다: stdin 읽기, 설정 층(저장소 층, 옵션 층 포함), PATH 에서 choom 찾기.
//! 명령에 `smoke-deny` 가 있으면 nonce 를 단 deny 를 낸다.
//!
//! ```text
//! cargo build --release --example smoke
//! echo '{"session_id":"s","cwd":".","tool_input":{"command":"smoke-deny"}}' | target/release/examples/smoke
//! ```

use std::process::ExitCode;

use harness_hook::output::emit;
use harness_hook::settings::{self, LoadRequest};
use harness_hook::tag::{self, Level};
use harness_hook::{EnsureAscii, Env, HookInput, HookOutput, Nonce};

fn main() -> ExitCode {
    let env = Env::from_process();
    let Ok(input) = HookInput::read(std::io::stdin().lock()) else {
        return ExitCode::SUCCESS;
    };

    // 설정 층과 래퍼
    let exe_dir = std::env::current_exe()
        .ok()
        .and_then(|p| p.parent().map(|d| d.to_path_buf()));
    let req = LoadRequest {
        project: settings::project_dir(&env, input.cwd()),
        plugin_dir: exe_dir.as_deref(),
        ..LoadRequest::default()
    };
    let layers = settings::load_layers(&env, &req).unwrap_or_default();
    let wrap = settings::heavy_wrap(&layers, &env);

    // 막을 명령이면 deny
    if !input.command().is_some_and(|c| c.contains("smoke-deny")) {
        return ExitCode::SUCCESS;
    }
    let nonce = Nonce::for_session(&env, input.session_id()).unwrap_or(None);
    let body = format!("smoke deny; wrap is `{}`.", wrap.join(" "));
    let reason = tag::harness_hook("smoke", Level::Action, nonce.as_ref(), &body);
    emit(&HookOutput::deny(reason).render(EnsureAscii::Yes));
    ExitCode::SUCCESS
}
