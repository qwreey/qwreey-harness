//! `hook second-opinion-nudge`: 정해진 시점에 독립 검토를 권한다(python `hooks/second-opinion-nudge.py`). 막지 않는다
//! (ExitPlanMode 의 deny 설정 제외).
//!
//! 이벤트마다:
//! - PostToolUseFailure: 같은 실패 서명이 이번 회차에 두 번째면 stuck 검토 권고(서명마다 한 번).
//! - PreToolUse(Bash): `git commit` 이고 커밋될 diff 가 등급 임계 이상이며 최근 검토가 없으면 done 검토 권고.
//! - Stop: 커밋 안 된 diff 가 임계 이상이면 done 검토 권고(이어 가면 안 되는 턴은 뺀다).
//! - PreToolUse(ExitPlanMode): high 등급에서 계획 검토 권고 또는 요구.
//! - SubagentStop: 검토면 최근 검토 시각과 ledger 자동 행, 아니면 보고의 신호를 기록한다([`review_record`], [`handback`]).
//! - UserPromptSubmit, PostToolBatch(메인): 신호가 든 보고가 들어오면 info 한 줄.
//!
//! python 과 다른 점(출력은 같다): python 은 이벤트를 가리기 전에 git 으로 등급을 읽고 상태 폴더를 만든다. 여기서는 출력이
//! 없을 것이 확실한 입력(commit 이 아닌 Bash, 무시할 실패)에서 git 을 띄우지 않는다. 빠지는 것은 상태 폴더를 만드는 일뿐이다.

mod commit_scope;
mod diff;
mod handback;
mod ledger;
mod messages;
mod review_record;
mod settings;
mod signals;
mod state;
mod transcript;

use std::sync::LazyLock;

use harness_hook::nonce::now_secs;
use harness_hook::py::json::EnsureAscii;
use harness_hook::py::path::normpath;
use harness_hook::py::surrogate::from_os;
use harness_hook::py::text::{splitlines, strip};
use harness_hook::py::value::{Dict, Value};
use harness_hook::rx::Regex;

use crate::abort::{Abort, Result};
use crate::context::Context;
use crate::epoch;
use crate::hookio::{context_output, load_dict, specific, text, truthy};
use crate::outcome::Outcome;
use crate::pylib::text::take_chars;

use messages::wrap;
use settings::{Tier, Vals, tier_of};
use state::State;

/// 상태 폴더 이름(예전 `second-opinion` 이름 그대로, 기존 ledger 와 상태를 잇는다).
pub const NS: &str = "claude-second-opinion";
const PLUGIN: &str = "qwreey-advisor";
const ON: &[&str] = &["1", "on", "true", "yes"];

fn regex(pattern: &'static str) -> Regex {
    Regex::new(pattern)
}

static BENIGN: LazyLock<Regex> = LazyLock::new(|| {
    regex(r"^\s*(grep|rg|egrep|fgrep|test|\[|diff|cmp|pgrep|pidof|which|command)\b")
});
static COMMIT: LazyLock<Regex> = LazyLock::new(|| regex(r"\bgit\b(\s+-C\s+\S+)?\s+commit\b"));
static DIGITS: LazyLock<Regex> = LazyLock::new(|| regex(r"[0-9]+"));
static PLAN_MARK: LazyLock<Regex> = LazyLock::new(|| regex(r"qwreey-advisor:\s*(reviewed|skip)"));

/// 훅 한 번. python 의 예외는 모두 잡혀 0 으로 끝나므로 stdout 만 다르다.
pub fn run(ctx: &Context, raw: &[u8]) -> Outcome {
    let Some(data) = load_dict(raw) else {
        return Outcome::quiet();
    };
    match Hook::new(ctx, &data).and_then(|hook| hook.dispatch()) {
        Ok(Some(out)) => Outcome::printed(&out).unwrap_or_default(),
        Ok(None) => Outcome::quiet(),
        Err(Abort(why)) => Outcome {
            stderr: format!("second-opinion-nudge: {why}\n").into_bytes(),
            ..Outcome::default()
        },
    }
}

/// 한 입력의 공통 값.
struct Hook<'a> {
    ctx: &'a Context,
    data: &'a Dict,
    event: &'a str,
    /// python `data.get("session_id") or ""`.
    sid: &'a str,
}

impl<'a> Hook<'a> {
    fn new(ctx: &'a Context, data: &'a Dict) -> Result<Hook<'a>> {
        // python 은 글이 아닌 session_id 를 정규식에 넣다가 예외로 끝난다
        let sid = match truthy(data, "session_id") {
            None => "",
            Some(Value::Str(s)) => s.as_str(),
            Some(_) => return Err(Abort("session_id is not a string")),
        };
        let event = data
            .get("hook_event_name")
            .and_then(Value::as_str)
            .unwrap_or("");
        Ok(Hook {
            ctx,
            data,
            event,
            sid,
        })
    }

    fn tempdir(&self) -> Result<&str> {
        self.ctx.tempdir().ok_or(Abort("no usable temp dir"))
    }

    fn wrap(&self, body: &str, level: &str) -> Result<String> {
        let attr = self
            .ctx
            .nonce_attr(self.data.get("session_id").filter(|v| v.truthy()))
            .map_err(|_| Abort("session id has a lone surrogate"))?;
        Ok(wrap(body, level, &attr))
    }

    fn emit(&self, body: &str, level: &str) -> Result<Option<String>> {
        Ok(Some(context_output(
            self.event,
            &self.wrap(body, level)?,
            EnsureAscii::Yes,
        )))
    }

    // python data.get("cwd") or os.getcwd(): 글이 아닌 cwd 는 git 인자에서 예외로 끝난다
    fn cwd(&self) -> Result<String> {
        match truthy(self.data, "cwd") {
            Some(Value::Str(s)) => Ok(s.clone()),
            Some(_) => Err(Abort("cwd is not a string")),
            None => std::env::current_dir()
                .map(|d| from_os(d.as_os_str()))
                .map_err(|_| Abort("cannot read the current directory")),
        }
    }

    fn tool_name(&self) -> Option<&str> {
        self.data.get("tool_name").and_then(Value::as_str)
    }

    // python (data.get("tool_input") or {}): dict 가 아니면 .get 에서 예외
    fn tool_input(&self) -> Result<Option<&Dict>> {
        match truthy(self.data, "tool_input") {
            None => Ok(None),
            Some(Value::Dict(d)) => Ok(Some(d)),
            Some(_) => Err(Abort("tool_input has no get")),
        }
    }

    // python str(ti.get(key, "")): 목록과 dict 의 repr 은 옮기지 않았다
    fn tool_input_text(&self, key: &str) -> Result<String> {
        match self.tool_input()?.and_then(|ti| ti.get(key)) {
            None => Ok(String::new()),
            Some(v) => v
                .scalar_str()
                .ok_or(Abort("tool_input field is a list or dict")),
        }
    }

    fn dispatch(&self) -> Result<Option<String>> {
        // SubagentStop records in any agent; the rest only in the main session
        if self.event == "SubagentStop" {
            self.subagent_stop()?;
            return Ok(None);
        }
        if truthy(self.data, "agent_id").is_some() {
            return Ok(None);
        }
        match (self.event, self.tool_name()) {
            ("UserPromptSubmit" | "PostToolBatch", _) => self.handback(),
            ("PostToolUseFailure", _) => self.failure(),
            ("PreToolUse", Some("Bash")) => self.commit(),
            ("PreToolUse", Some("ExitPlanMode")) => self.exit_plan(),
            ("Stop", _) => self.stop(),
            // Every other event ends quietly
            _ => Ok(None),
        }
    }

    /// 등급, 임계, 상태(python 의 이벤트 공통 앞부분). 알릴 것이 없는 저장소면 `None`.
    fn repo_state(&self, cwd: &str, vals: &Vals) -> Result<Option<(Tier, i128, State)>> {
        let tier = tier_of(cwd, vals)?;
        if tier.is_silent() {
            return Ok(None);
        }
        let limit = vals.limit_of(&tier.tier)?;
        let path = epoch::state_path(self.tempdir()?, PLUGIN, NS, self.sid)?;
        Ok(Some((tier, limit, State::load(path)?)))
    }

    fn fresh_review(&self, vals: &Vals) -> Result<bool> {
        let t = review_record::last_review_time(self.tempdir()?, self.sid)?;
        if t == 0.0 {
            return Ok(false);
        }
        Ok(now_secs() - t < vals.fresh_seconds()?)
    }

    fn failure(&self) -> Result<Option<String>> {
        // Interrupts and benign probes are not failures
        if truthy(self.data, "is_interrupt").is_some() {
            return Ok(None);
        }
        if self.tool_name() == Some("Bash") {
            let command = self.tool_input()?.and_then(|ti| ti.get("command"));
            if let Some(Value::Str(cmd)) = command
                && BENIGN.match_start(cmd).is_some()
            {
                return Ok(None);
            }
        }

        let cwd = self.cwd()?;
        let vals = Vals::load(self.ctx, &cwd);
        let Some((tier, _, mut st)) = self.repo_state(&cwd, &vals)? else {
            return Ok(None);
        };

        // Signature: tool and first meaningful error line, digits folded
        let sig = failure_signature(self.data)?;
        let second = st.count_failure(&sig)?;
        st.save()?;
        if !second {
            return Ok(None);
        }
        self.emit(
            &messages::stuck_advice(take_chars(&sig, 200), &tier.tier),
            "warn",
        )
    }

    fn commit(&self) -> Result<Option<String>> {
        let cmd = self.tool_input_text("command")?;
        if !COMMIT.is_match(&cmd) {
            return Ok(None);
        }
        let cwd = self.cwd()?;
        let vals = Vals::load(self.ctx, &cwd);
        let Some((mut tier, mut limit, mut st)) = self.repo_state(&cwd, &vals)? else {
            return Ok(None);
        };
        if self.fresh_review(&vals)? {
            return Ok(None);
        }

        // Size of what this command commits
        let Some((dir, size)) = diff::commit_size(&cmd, &cwd, &self.ctx.env)? else {
            return Ok(None);
        };
        if normpath(&dir) != normpath(&cwd) {
            // A commit into another repo uses that repo's tier
            tier = tier_of(&dir, &vals)?;
            if tier.is_silent() {
                return Ok(None);
            }
            limit = vals.limit_of(&tier.tier)?;
        }

        // Once per diff, then rest for FRESH_MIN
        if limit <= 0
            || size.lines < limit
            || st.nudged_contains(&size.hash)?
            || st.cooling(now_secs(), vals.fresh_seconds()?)?
        {
            return Ok(None);
        }
        st.record_nudge(&size.hash, now_secs())?;
        st.save()?;
        let repo = tier.repo.as_deref().unwrap_or("");
        self.emit(
            &messages::done_advice(repo, &tier.tier, size.lines, "About to commit"),
            "warn",
        )
    }

    fn stop(&self) -> Result<Option<String>> {
        let cwd = self.cwd()?;
        let vals = Vals::load(self.ctx, &cwd);

        // Turns that must not be continued
        let switch = strip(vals.text("HARNESS_REVIEW_STOP")).to_lowercase();
        if !ON.contains(&switch.as_str())
            || truthy(self.data, "stop_hook_active").is_some()
            || messages::stop_passes(&last_message(self.data))
        {
            return Ok(None);
        }

        let Some((tier, limit, mut st)) = self.repo_state(&cwd, &vals)? else {
            return Ok(None);
        };
        if limit <= 0 || self.fresh_review(&vals)? {
            return Ok(None);
        }

        // Uncommitted size, once per diff
        let size = diff::diff_stat(&cwd, &["HEAD"])?;
        if size.lines < limit
            || st.nudged_contains(&size.hash)?
            || st.cooling(now_secs(), vals.fresh_seconds()?)?
        {
            return Ok(None);
        }
        st.record_nudge(&size.hash, now_secs())?;
        st.save()?;
        let repo = tier.repo.as_deref().unwrap_or("");
        let advice = messages::done_advice(
            repo,
            &tier.tier,
            size.lines,
            "Turn ending with uncommitted changes",
        );
        self.emit(&advice, "warn")
    }

    fn exit_plan(&self) -> Result<Option<String>> {
        let cwd = self.cwd()?;
        let vals = Vals::load(self.ctx, &cwd);
        let Some((tier, _, _)) = self.repo_state(&cwd, &vals)? else {
            return Ok(None);
        };

        let mode = vals.text("HARNESS_REVIEW_PLAN");
        let plan = self.tool_input_text("plan")?;
        if tier.tier != "high" || !matches!(mode, "deny" | "warn") || PLAN_MARK.is_match(&plan) {
            return Ok(None);
        }
        if mode == "warn" {
            return self.emit(messages::PLAN_WARN, "warn");
        }

        // deny: permissionDecisionReason carries the action tag
        let inner = Dict::from_pairs(vec![
            ("hookEventName".to_owned(), text(self.event)),
            ("permissionDecision".to_owned(), text("deny")),
            (
                "permissionDecisionReason".to_owned(),
                text(self.wrap(messages::PLAN_DENY, "action")?),
            ),
        ]);
        Ok(Some(specific(inner, EnsureAscii::Yes)))
    }

    fn handback(&self) -> Result<Option<String>> {
        let tempdir = self.tempdir()?;

        // Reports waiting from SubagentStop, or the report in this prompt
        let labels = if self.event == "PostToolBatch" {
            if !handback::has_state(tempdir, self.sid)? {
                return Ok(None);
            }
            let reviewed_at = review_record::last_review_time(tempdir, self.sid)?;
            handback::on_batch(tempdir, self.sid, self.data.get("tool_calls"), reviewed_at)?
        } else {
            let prompt = match truthy(self.data, "prompt") {
                None => String::new(),
                Some(v) => v.scalar_str().ok_or(Abort("prompt is a list or dict"))?,
            };
            if !prompt.contains("<task-notification>") && !prompt.contains("[Subagent hand-back]") {
                return Ok(None);
            }
            let reviewed_at = review_record::last_review_time(tempdir, self.sid)?;
            handback::on_prompt(tempdir, self.sid, &prompt, reviewed_at)?
        };
        if labels.is_empty() {
            return Ok(None);
        }

        // Switch and repo tier
        let cwd = self.cwd()?;
        let vals = Vals::load(self.ctx, &cwd);
        if vals.text("HARNESS_REVIEW_HANDBACK").to_lowercase() == "off" {
            return Ok(None);
        }
        let tier = tier_of(&cwd, &vals)?;
        if tier.repo.as_deref().is_some_and(|r| !r.is_empty()) && tier.tier == "off" {
            return Ok(None);
        }
        self.emit(&handback::message(&labels), "info")
    }

    fn subagent_stop(&self) -> Result<()> {
        let tempdir = self.tempdir()?;
        let tpath = match truthy(self.data, "agent_transcript_path") {
            None => String::new(),
            Some(Value::Str(s)) => s.clone(),
            Some(_) => return Err(Abort("agent_transcript_path is not a string")),
        };

        // Review record: last-review time and the ledger row
        let meta = transcript::read_meta(&tpath);
        let kind = review_record::review_kind(self.data.get("agent_type"), &tpath, &meta)?;
        if let Some(kind) = kind {
            let caller = review_record::caller_of(&meta, kind, &tpath)?;
            if caller == "main" {
                review_record::record_main_review(tempdir, self.sid, now_secs())?;
            }
            self.ledger_row(kind, caller, &meta);
        }

        // Hand-back classification; python swallows only OSError here
        let nested = review_record::nested(&meta)?;
        let Some(agent_id) = truthy(self.data, "agent_id") else {
            return Ok(());
        };
        let agent_id = agent_id
            .scalar_str()
            .ok_or(Abort("agent_id is a list or dict"))?;
        let last = match truthy(self.data, "last_assistant_message") {
            None => String::new(),
            Some(Value::Str(s)) => s.clone(),
            Some(_) => return Err(Abort("last_assistant_message is not a string")),
        };
        let handed = transcript::handback_message(&tpath)?;
        let text: Vec<&str> = [last.as_str(), handed.as_str()]
            .into_iter()
            .filter(|x| !x.is_empty())
            .collect();
        let text = text.join("\n");
        let report = handback::StopReport {
            agent_id: &agent_id,
            text: &text,
            meta: &meta,
            agent_type: self.data.get("agent_type"),
            review: kind.is_some(),
            nested,
        };
        handback::on_stop(tempdir, self.sid, &report)
    }

    // python ledger_auto: 어떤 실패든 행만 건너뛴다
    fn ledger_row(&self, kind: review_record::Kind, caller: &str, meta: &Dict) {
        let Some((ledger_kind, reviewer)) = review_record::ledger_fields(kind, meta) else {
            return;
        };
        let Some(root) = self.ctx.plugin_root() else {
            return;
        };
        let agent = match truthy(self.data, "agent_id") {
            None => Some(String::new()),
            Some(v) => v.scalar_str(),
        };
        let (Some(agent), Ok(repo_dir)) = (agent, self.cwd()) else {
            return;
        };
        let session = truthy(self.data, "session_id")
            .cloned()
            .unwrap_or_else(|| Value::Str(String::new()));
        let row = ledger::AutoRow {
            kind: &ledger_kind,
            reviewer: &reviewer,
            caller,
            reference: format!("agent-{agent}"),
            repo_dir: &repo_dir,
            session,
        };
        ledger::auto_add(&self.ctx.env, &root, &row);
    }
}

/// python 의 실패 서명: `<tool_name>|<첫 의미 있는 오류 줄, 숫자는 #>[:160]`.
fn failure_signature(data: &Dict) -> Result<String> {
    let err = match truthy(data, "error") {
        None => String::new(),
        Some(v) => v.scalar_str().ok_or(Abort("error is a list or dict"))?,
    };
    let first = splitlines(&err)
        .into_iter()
        .find(|l| !strip(l).is_empty() && !l.starts_with("Exit code"))
        .unwrap_or_else(|| take_chars(&err, 80));
    let folded = DIGITS.replace_all(strip(first), |_| "#".to_owned());
    let tool = match data.get("tool_name") {
        None => "None".to_owned(),
        Some(v) => v.scalar_str().ok_or(Abort("tool_name is a list or dict"))?,
    };
    Ok(format!("{tool}|{}", take_chars(&folded, 160)))
}

// python str(msg or ""): 글이 아닌 참 값의 repr 은 질문이나 오류 알림으로 읽히지 않는다(빈 답도 아니다)
fn last_message(data: &Dict) -> String {
    match truthy(data, "last_assistant_message") {
        None => String::new(),
        Some(Value::Str(s)) => s.clone(),
        Some(_) => "<non-text reply>".to_owned(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 이 모듈의 고정 정규식이 regex 판과 python 판(py::re)에서 같은 자리에 맞는다(만든 글 3000개).
    #[test]
    fn fixed_patterns_agree_with_python() {
        harness_hook::testkit::assert_agree(
            &[
                ("BENIGN", &*BENIGN),
                ("COMMIT", &*COMMIT),
                ("DIGITS", &*DIGITS),
                ("PLAN_MARK", &*PLAN_MARK),
            ],
            &[
                "git",
                " ",
                "-C",
                "commit",
                "x",
                "\t",
                "grep",
                "[",
                "a",
                "1",
                "qwreey-advisor:",
                "reviewed",
                "skip",
                "\n",
                "_",
                "é",
                "-",
                "\u{a0}",
                "\u{2460}",
                "test",
            ],
        );
    }
}
