//! `hook ambient UserPromptSubmit`: 플러그인 상시 규약(ambient)의 보충 주입(python `hooks/ambient.py` 의 UserPromptSubmit 갈래).
//!
//! 셈은 q 플러그인과 같이 쓰는 [`harness_hook::ambient`] 에 있다. SessionStart, SubagentStart, PreCompact 갈래는 python 그대로다.

use harness_hook::HookEnv;
use harness_hook::ambient::prompt_supplement;

use crate::context::Context;
use crate::outcome::Outcome;

/// 훅 한 번. 어떤 실패든 아무것도 내지 않고 0 으로 끝난다.
pub fn run(ctx: &Context, raw: &[u8]) -> Outcome {
    let hook = HookEnv::new(ctx.env.clone(), ctx.exe_dir.clone());
    match prompt_supplement(&hook, raw) {
        Some(stdout) => Outcome {
            stdout,
            ..Outcome::default()
        },
        None => Outcome::quiet(),
    }
}
