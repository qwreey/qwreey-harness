//! session-log 훅의 도구마다, 사용자 말마다 뜨는 이벤트(python `scripts/hook.py` 의 같은 이벤트).
//!
//! - PostToolUse, UserPromptSubmit: 워커가 남긴 요약 완료 알림을 한 번 전하고, 트랜스크립트가 충분히 자랐고 쿨다운이
//!   지났으면 워커를 띄운다([`spawn`]). UserPromptSubmit 이 인계(handover, checkpoint)를 말하면 pending 알림을 붙인다.
//! - PreToolUse: `git commit` 앞, handover/checkpoint 스킬 앞에서 pending 알림.
//!
//! SessionStart, PreCompact, PostCompact, SessionEnd 는 python 판에 남는다. 상태 파일은 python 판과 같은 자리, 같은 꼴이라
//! 두 판이 번갈아 돌아도 된다([`state`], [`crate::store`]). 막지 않는다: python 에서 예외가 나는 자리는 그때까지의 출력만 남긴다.

pub mod spawn;
pub mod state;

use std::sync::LazyLock;

use harness_hook::py::re::Flags;
use harness_hook::py::surrogate::{from_os, unit_of};
use harness_hook::py::value::{Dict, Value};
use harness_hook::rx::Regex;
use harness_hook::tag::Level;
use harness_hook::{EnsureAscii, HookInput, HookOutput};

use crate::abort::{Abort, Result};
use crate::brief;
use crate::config::Key;
use crate::context::Context;
use crate::epoch;
use crate::fsx::{self, FsError};
use crate::messages::{self, Trigger};
use crate::paths::{project_root, safe_sid};
use crate::pyval::{self, Num, ZERO, greater, truthy_str};
use crate::store::{Store, read_json};
use spawn::Flush;
use state::HookState;

/// `git commit`(앞에 `-C <dir>` 가 붙어도). python `COMMIT_RX`.
static COMMIT_RX: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"(^|[;&|(\s])git(\s+-[Cc]\s+\S+)*\s+commit\b"));
/// 사용자 말의 인계 요청. python `HANDOVER_RX`(re.I).
static HANDOVER_RX: LazyLock<Regex> = LazyLock::new(|| {
    Regex::with_flags(
        r"^\s*/(?:qwreey-sessions:)?(handover|checkpoint)\b|\b(handover|핸드오버|인계)\b",
        Flags::IGNORECASE,
    )
});
/// 인계 스킬 이름(re.I).
static HANDOVER_SKILL_RX: LazyLock<Regex> =
    LazyLock::new(|| Regex::with_flags(r"handover|checkpoint", Flags::IGNORECASE));
/// 사용자 말은 앞 400자만 본다.
const PROMPT_SCAN_CHARS: usize = 400;

/// 옮긴 이벤트.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Event {
    PostToolUse,
    UserPromptSubmit,
    PreToolUse,
}

impl Event {
    /// 하위 명령 인자에서. 옮기지 않은 이벤트는 `None`.
    pub fn parse(name: &str) -> Option<Event> {
        match name {
            "PostToolUse" => Some(Event::PostToolUse),
            "UserPromptSubmit" => Some(Event::UserPromptSubmit),
            "PreToolUse" => Some(Event::PreToolUse),
            _ => None,
        }
    }

    /// 이벤트 이름(출력의 `hookEventName`).
    pub fn as_str(self) -> &'static str {
        match self {
            Event::PostToolUse => "PostToolUse",
            Event::UserPromptSubmit => "UserPromptSubmit",
            Event::PreToolUse => "PreToolUse",
        }
    }
}

/// 훅 한 번의 결과: stdout 에 쓸 글과, 그 뒤 python 이 예외로 끝났는지(오류 기록에 쓴다).
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct Run {
    pub stdout: Option<String>,
    pub error: Option<Abort>,
}

/// 훅 하나를 돌린다.
pub fn run(ctx: &Context, event: Event, input: &HookInput) -> Run {
    let mut run = Run::default();
    run.error = handle(ctx, event, input.raw(), &mut run.stdout).err();
    run
}

// python `data.get("session_id") or os.environ.get("CLAUDE_CODE_SESSION_ID") or ""` 가 상태 파일 이름에 쓸 수 있는 글일 때만
// (python `safe_sid`). 글이 아닌 id, `../x` 같은 id 는 python 도 조용히 끝낸다
fn session_id(ctx: &Context, data: &Dict) -> Option<String> {
    let sid = match data.get("session_id").filter(|v| v.truthy()) {
        Some(Value::Str(s)) => s.clone(),
        Some(_) => return None,
        None => from_os(ctx.hook.env.get_os_nonempty("CLAUDE_CODE_SESSION_ID")?),
    };
    safe_sid(&sid).then_some(sid)
}

/// `transcript_path` 의 python 판정(`transcript and os.path.isfile(transcript)`).
enum Transcript {
    /// 없음, 빈 글 등 거짓.
    Missing,
    Path(String),
    /// int, bool: python 은 파일 기술자로 보고 거의 늘 거짓이다. 여기서는 늘 거짓으로 본다.
    NotPath,
    /// float, 목록, 객체: python `os.stat` 의 TypeError.
    Invalid,
}

impl Transcript {
    fn of(value: Option<&Value>) -> Transcript {
        match value {
            None => Transcript::Missing,
            Some(v) if !v.truthy() => Transcript::Missing,
            Some(Value::Str(s)) => Transcript::Path(s.clone()),
            Some(Value::Bool(_) | Value::Int(_) | Value::BigInt(_)) => Transcript::NotPath,
            Some(_) => Transcript::Invalid,
        }
    }
}

// python `os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd()`
fn start_dir(ctx: &Context, data: &Dict) -> Result<String> {
    if let Some(dir) = ctx.hook.env.get_os_nonempty("CLAUDE_PROJECT_DIR") {
        return Ok(from_os(dir));
    }
    match data.get("cwd") {
        Some(Value::Str(cwd)) if !cwd.is_empty() => Ok(cwd.clone()),
        Some(v) if v.truthy() => Err(Abort("cwd is not a string")),
        _ => std::env::current_dir()
            .map(|d| from_os(d.as_os_str()))
            .map_err(|_| Abort("no current directory")),
    }
}

/// python `main()` 의 옮긴 이벤트. 출력은 `stdout` 에 두고, 그 뒤의 실패는 `Err`.
fn handle(ctx: &Context, event: Event, data: &Dict, stdout: &mut Option<String>) -> Result<()> {
    // 서브에이전트, 중첩 실행, 꺼짐
    if data.get("agent_id").is_some_and(Value::truthy) {
        return Ok(());
    }
    if ctx.hook.env.get_os_nonempty("SESSION_LOG_NESTED").is_some() {
        return Ok(());
    }
    let config = ctx.config();
    if config.disabled() || config.skip_noninteractive(&ctx.hook.env) {
        return Ok(());
    }

    // 세션, 저장소, 훅 상태
    let Some(sid) = session_id(ctx, data) else {
        return Ok(());
    };
    let transcript = Transcript::of(data.get("transcript_path"));
    let start = start_dir(ctx, data)?;
    let store = Store::new(project_root(&start)?, &config.home(&ctx.hook.env));
    let mut hs = HookState::load(&store, &sid)?;
    let mut session = Session {
        ctx,
        store: &store,
        sid: &sid,
        hs: &mut hs,
    };

    // 이벤트마다 알림
    let parts = match event {
        Event::PostToolUse => session.tick(&transcript)?,
        Event::UserPromptSubmit => {
            let mut parts = session.tick(&transcript)?;
            if asks_handover(data)? {
                parts.push(session.pending_once(Trigger::Handover)?);
            }
            parts
        }
        Event::PreToolUse => match pre_tool_trigger(data)? {
            Some(trigger) if store.exists() => vec![session.pending_once(trigger)?],
            _ => Vec::new(),
        },
    };

    // 내고, 상태가 바뀌었으면 쓴다
    let nonce_sid = truthy_str(data.get("session_id"), "session_id")?;
    *stdout = context_output(ctx, event, &parts, nonce_sid.as_deref())?;
    if hs.changed() {
        store.save_hstate(&sid, hs.value())?;
    }
    Ok(())
}

/// 한 번 실행에서 같이 쓰는 것.
struct Session<'a> {
    ctx: &'a Context,
    store: &'a Store,
    sid: &'a str,
    hs: &'a mut HookState,
}

impl Session<'_> {
    /// 요약 완료 알림 전하기와 주기 요약 띄우기(python `tick`).
    fn tick(&mut self, transcript: &Transcript) -> Result<Vec<(Level, String)>> {
        let mut out = Vec::new();

        // 아직 전하지 않은 요약 완료 알림
        let seq = self.store.notice_seq();
        let cursor = self.hs.get("notice_seq", &ZERO)?.clone();
        if greater(&Value::Int(seq), &cursor, "notice_seq is not a number")? {
            let notices = self.store.notices_after(&cursor)?;
            let line = brief::saved_line(self.store, &notices, &self.ctx.hook.env)?;
            self.hs.set("notice_seq", Value::Int(seq))?;
            if !line.is_empty() {
                out.push((Level::Info, line));
            }
        }

        // 트랜스크립트가 충분히 자랐고 쿨다운이 지났으면 워커
        let path = match transcript {
            Transcript::Path(p) if fsx::is_file(p) => p,
            Transcript::Invalid => return Err(Abort("transcript_path is not a path")),
            _ => return Ok(out),
        };
        if let Some(line_from) = self.maybe_spawn(path)? {
            out.push((Level::Info, messages::started("periodic", &line_from, None)));
        }
        Ok(out)
    }

    // 띄웠으면 다음 요약이 시작할 줄(python `ws.get("line", 0) + 1` 의 글)
    fn maybe_spawn(&mut self, transcript: &str) -> Result<Option<String>> {
        let config = self.ctx.config();
        let wstate_path = self.store.wstate_path(self.sid)?;
        let ws = if fsx::exists(&wstate_path) {
            read_json(&wstate_path)
        } else {
            Value::Dict(Default::default())
        };

        // 마지막 실행 뒤로 지난 시간, 지난 위치 뒤로 자란 바이트
        let now = now_secs();
        let last_run = Num::require(
            pyval::get(&ws, "last_run", &ZERO, "worker state")?,
            "last_run",
        )?;
        let last_spawn = Num::require(self.hs.get("last_spawn", &ZERO)?, "last_spawn")?;
        let last = python_max(last_run.as_f64(), last_spawn.as_f64());
        let size = match fsx::getsize(transcript) {
            Ok(size) => size,
            Err(FsError::Os(_) | FsError::Value) => return Err(Abort("transcript vanished")),
        };
        let offset = Num::require(pyval::get(&ws, "offset", &ZERO, "worker state")?, "offset")?;
        let grown = size as f64 - offset.as_f64();
        let due = now - last >= config.num(Key::CooldownMin) * 60.0
            && grown >= config.num(Key::GrowKb) * 1024.0;
        if !due {
            return Ok(None);
        }

        // 워커를 띄우고 띄운 때를 남긴다
        spawn::spawn(
            self.ctx,
            &Flush {
                session: self.sid,
                transcript,
                project: &self.store.root,
                trigger: "PostToolUse",
                force: false,
            },
        )?;
        self.hs.set("last_spawn", Value::Float(now))?;
        let line = Num::require(pyval::get(&ws, "line", &ZERO, "worker state")?, "line")?;
        Ok(Some(line.plus(Num::Int(1))?.text()))
    }

    /// pending 알림을 (세션, 회차, 트리거)마다 한 번(python `pending_once`).
    fn pending_once(&mut self, trigger: Trigger) -> Result<(Level, String)> {
        let (level, line) = brief::pending_line(self.store, self.ctx.config(), trigger)?;
        if line.is_empty() {
            return Ok((level, line));
        }
        let epoch = epoch::epoch(self.ctx.tempdir(), Some(self.sid));
        let key = format!("pending:{}@{epoch}", trigger.as_str());
        Ok(if self.hs.once(&key)? {
            (level, line)
        } else {
            (level, String::new())
        })
    }
}

// python max(a, b): 뒤가 더 클 때만 뒤(NaN 과의 비교는 거짓)
fn python_max(a: f64, b: f64) -> f64 {
    if b > a { b } else { a }
}

/// python `time.time()`.
pub fn now_secs() -> f64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map_or(0.0, |d| d.as_secs_f64())
}

// python `str(value)` 의 앞 n 글자. 목록, 객체는 python repr 을 옮기지 않아 Abort
fn scan_text(value: Option<&Value>, n: usize, what: &'static str) -> Result<String> {
    let text = match value {
        None => String::new(),
        Some(v) => v.scalar_str().ok_or(Abort(what))?,
    };
    Ok(text.chars().take(n).collect())
}

// UserPromptSubmit: 사용자 말이 인계를 말하나
fn asks_handover(data: &Dict) -> Result<bool> {
    let prompt = scan_text(
        data.get("prompt"),
        PROMPT_SCAN_CHARS,
        "prompt is a list or object",
    )?;
    Ok(HANDOVER_RX.is_match(&prompt))
}

// PreToolUse: git commit 앞이면 commit, 인계 스킬 앞이면 handover
fn pre_tool_trigger(data: &Dict) -> Result<Option<Trigger>> {
    let tool = data.get("tool_name").and_then(Value::as_str);
    if !matches!(tool, Some("Bash" | "Skill")) {
        return Ok(None);
    }

    // python `data.get("tool_input") or {}`: 참인 dict 가 아니면 .get 에서 AttributeError
    let empty = Dict::new();
    let input = match data.get("tool_input") {
        Some(Value::Dict(o)) => o,
        Some(v) if v.truthy() => return Err(Abort("tool_input is not an object")),
        _ => &empty,
    };
    if tool == Some("Bash") {
        let command = scan_text(
            input.get("command"),
            usize::MAX,
            "command is a list or object",
        )?;
        return Ok(COMMIT_RX.is_match(&command).then_some(Trigger::Commit));
    }
    let skill = scan_text(input.get("skill"), usize::MAX, "skill is a list or object")?;
    Ok(HANDOVER_SKILL_RX
        .is_match(&skill)
        .then_some(Trigger::Handover))
}

/// 알림을 출력 JSON 으로(python `emit_context`, 이 이벤트들에는 규칙 줄과 닻이 없다). 낼 것이 없으면 `None`.
///
/// python 은 `ensure_ascii=False` 글을 UTF-8 로 바꾸다 짝 없는 서로게이트에서 예외로 끝난다(아무것도 쓰기 전).
fn context_output(
    ctx: &Context,
    event: Event,
    parts: &[(Level, String)],
    nonce_sid: Option<&str>,
) -> Result<Option<String>> {
    let parts: Vec<(Level, String)> = parts
        .iter()
        .filter(|(_, t)| !harness_hook::py::text::strip(t).is_empty())
        .cloned()
        .collect();
    if parts.is_empty() {
        return Ok(None);
    }
    let text = messages::wrap_parts(&parts, ctx.nonce(nonce_sid)?.as_ref());
    if text.is_empty() {
        return Ok(None);
    }
    let payload = HookOutput::context(event.as_str(), text).render(EnsureAscii::No);
    if payload.chars().any(|c| unit_of(c).is_some()) {
        return Err(Abort("output has a lone surrogate"));
    }
    Ok(Some(payload))
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 이 파일의 고정 정규식이 두 regex crate 엔진과 py::re 에서 모두 만들어진다.
    #[test]
    fn fixed_patterns_build() {
        for re in [&*COMMIT_RX, &*HANDOVER_RX, &*HANDOVER_SKILL_RX] {
            re.check();
        }
    }

    /// 인계 요청과 git commit 을 python 판 패턴처럼 알아본다(ASCII 글, 한국어 글, 대소문자).
    #[test]
    fn triggers_like_python() {
        // The prompt asks for a handover
        assert!(HANDOVER_RX.is_match("/checkpoint now") && HANDOVER_RX.is_match("이제 인계 해줘"));
        assert!(HANDOVER_RX.is_match("Write a HANDOVER") && !HANDOVER_RX.is_match("handovers"));

        // A commit, with or without -C
        assert!(COMMIT_RX.is_match("cd x && git -C /r commit -m a"));
        assert!(!COMMIT_RX.is_match("git commits") && !COMMIT_RX.is_match("legit commit"));
    }
}
