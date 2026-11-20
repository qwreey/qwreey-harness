//! qwreey-reply-language 플러그인의 훅을 한 바이너리로(`plugins/qwreey-reply-language/hooks/reply_language.py` 의 Rust 판).
//!
//! `hook reply-language`: UserPromptSubmit, Stop, PostToolBatch 모두. 종료 코드(늘 0)와 stdout 은 python 판과 바이트로 같다.
//! 사람이 부르는 `reply_language.py set <language>` 는 python 그대로다. 두 판은 같은 상태 파일과 로그를 같은 꼴로 쓴다.

pub mod context;
pub mod drift;
pub mod events;
pub mod language;
pub mod pyval;
pub mod scan;
pub mod state;
pub mod transcript;

use harness_hook::py::json_load::{self, Decode};
use harness_hook::py::surrogate::encode_os;

use context::Context;
use events::Event;
use pyval::{Abort, Result};

/// 훅 한 번의 stdout 바이트(python `json.dump(out, sys.stdout, ensure_ascii=False)`, 끝 줄바꿈 없음). 낼 것이 없으면 빈 바이트.
///
/// python 은 어떤 예외든 삼키고 0 으로 끝난다. 그래서 여기서도 [`Abort`] 는 빈 출력이다.
pub fn run(ctx: &Context, raw: &[u8]) -> Vec<u8> {
    if ctx.is_off("HARNESS_REPLY_LANGUAGE") {
        return Vec::new();
    }
    match dispatch(ctx, raw) {
        // python 은 쓸 수 없는 서로게이트에서 앞부분만 쓰고 멈춘다. 여기서는 아무것도 쓰지 않는다
        Ok(Some(out)) => encode_os(&out).unwrap_or_default(),
        Ok(None) | Err(Abort(_)) => Vec::new(),
    }
}

fn dispatch(ctx: &Context, raw: &[u8]) -> Result<Option<String>> {
    let data = json_load::from_bytes(raw, Decode::SurrogateEscape)
        .map_err(|_| Abort("hook input is not JSON"))?
        .into_dict()
        .map_err(|_| Abort("hook input is not an object"))?;
    if data.get("agent_id").is_some_and(|v| v.truthy()) {
        return Ok(None);
    }

    let sid = match data.get("session_id").filter(|v| v.truthy()) {
        None => String::new(),
        Some(v) => v
            .scalar_str()
            .ok_or(Abort("session_id is a list or dict"))?,
    };
    let event = Event {
        ctx,
        data: &data,
        sid,
    };
    match data.get("hook_event_name").and_then(|v| v.as_str()) {
        Some("UserPromptSubmit") => event.on_prompt(),
        Some("Stop") => event.on_stop(),
        Some("PostToolBatch") => event.on_batch(),
        _ => Ok(None),
    }
}
