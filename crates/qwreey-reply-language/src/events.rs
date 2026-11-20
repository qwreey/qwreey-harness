//! 이벤트마다의 판정(python `on_prompt`, `on_stop`, `on_batch`).
//!
//! - UserPromptSubmit: 언어를 알 수 없으면(세션당 한 번) 답 끝에 언어를 묻고 `set` 으로 저장하게 하는 info 알림.
//! - Stop: 마지막 답이 이탈이면 `decision: block` 으로 다시 쓰게 한다. 사용자가 이번 턴에 목표 문자로 거의 쓰지 않았으면 통과.
//! - PostToolBatch: 도구 호출 사이 글이 이탈이면 info(쿨다운), 한 프롬프트의 도구 호출이 10, 이후 15마다 info.

use harness_hook::py::json::{EnsureAscii, dumps_dict};
use harness_hook::py::path::join;
use harness_hook::py::surrogate::from_os;
use harness_hook::py::value::{Dict, Value};

use crate::context::Context;
use crate::drift::{PASTED, is_drift, strip_text};
use crate::language::{Script, data_dir, script_for, settings_language, stored_language};
use crate::pyval::{Abort, Num, Result, number, py_eq};
use crate::state;
use crate::transcript::{interim_texts, last_user_prompt, read_new_lines};

const FIRST_REMINDER: i128 = 10;
const EVERY: i128 = 15;
const INTERIM_COOLDOWN_CALLS: i128 = 5;
const PROMPT_MIN_TARGET: usize = 3;

/// 한 입력의 공통 값.
pub struct Event<'a> {
    pub ctx: &'a Context,
    pub data: &'a Dict,
    /// python `str(session_id or "nosession")` 의 글(상태와 로그 이름). 없으면 빈 글.
    pub sid: String,
}

fn truthy<'a>(d: &'a Dict, key: &str) -> Option<&'a Value> {
    d.get(key).filter(|v| v.truthy())
}

fn text(s: impl Into<String>) -> Value {
    Value::Str(s.into())
}

impl Event<'_> {
    /// `<harness-hook name="reply-language" level=...>` 태그(python `tag`).
    fn tag(&self, level: &str, body: &str) -> Result<String> {
        let attr = self
            .ctx
            .nonce_attr(self.data.get("session_id"))
            .map_err(|_| Abort("session id has a lone surrogate"))?;
        Ok(format!(
            "<harness-hook name=\"reply-language\" level=\"{level}\"{attr}>\n{body}\n</harness-hook>"
        ))
    }

    fn log(&self, kind: &str, ratio: Option<f64>, length: Option<Value>) {
        state::log(self.ctx, &self.sid, kind, ratio, length);
    }

    /// python `resolve_language(data)`: settings 의 language, 없으면 저장한 언어.
    fn language(&self) -> Result<Option<String>> {
        let root = match self.ctx.env.get_os_nonempty("CLAUDE_PROJECT_DIR") {
            Some(dir) => from_os(dir),
            None => match truthy(self.data, "cwd") {
                Some(Value::Str(cwd)) => cwd.clone(),
                Some(_) => return Err(Abort("cwd is not a string")),
                None => std::env::current_dir()
                    .map(|d| from_os(d.as_os_str()))
                    .map_err(|_| Abort("cannot read the current directory"))?,
            },
        };
        Ok(settings_language(self.ctx, &root).or_else(|| stored_language(self.ctx)))
    }

    /// python `on_prompt`.
    pub fn on_prompt(&self) -> Result<Option<String>> {
        if self.language()?.is_some() {
            return Ok(None);
        }

        // Ask once per session
        let mut st = state::load(self.ctx, &self.sid)?;
        if st.get("asked").is_some_and(Value::truthy) {
            return Ok(None);
        }
        st.insert("asked", Value::Bool(true));
        state::save(self.ctx, &self.sid, &st);
        self.log("ask_language", None, None);

        // The notice names the set command for this install
        let script = match self.ctx.plugin_root() {
            Some(root) => join(&join(&root, "hooks"), "reply_language.py"),
            None => return Err(Abort("plugin root unknown")),
        };
        let data = data_dir(self.ctx).unwrap_or_default();
        let data_arg = if data.is_empty() {
            String::new()
        } else {
            format!(" --data \"{data}\"")
        };
        let cmd = format!("python3 -I \"{script}\" set \"<language>\"{data_arg}");
        let body = format!(
            "No reply language is configured, so replies cannot be checked for language drift. Answer the user's request first, as usual. \
             Then, at the end of that reply, ask in one short question which language to reply in, and store the answer with this command: {cmd}\n\
             If the user's message already makes the language clear (they write in it or name it), store that instead of asking. \
             The `language` key in a Claude Code settings.json sets it too."
        );
        Ok(Some(context("UserPromptSubmit", &self.tag("info", &body)?)))
    }

    /// python `on_stop`.
    pub fn on_stop(&self) -> Result<Option<String>> {
        let lang = self.language()?;
        let msg = truthy(self.data, "last_assistant_message");
        let Some(lang) = lang else {
            return Ok(None);
        };
        let Some(script) = script_for(&lang) else {
            self.log("stop_latin_skip", None, Some(Value::Int(py_len(msg)?)));
            return Ok(None);
        };

        // Drift in the final reply
        let msg_text = match msg {
            None => "",
            Some(Value::Str(s)) => s.as_str(),
            Some(_) => return Err(Abort("last_assistant_message has no strip")),
        };
        let (drifted, ratio, _) = is_drift(msg_text, script);
        if !drifted {
            return Ok(None);
        }
        let length = Some(Value::Int(py_len(msg)?));
        if truthy(self.data, "stop_hook_active").is_some() {
            self.log("stop_still_drifted", Some(ratio), length);
            return Ok(None);
        }
        if self.user_wrote_other_script(script)? {
            self.log("stop_user_other_script", Some(ratio), length);
            return Ok(None);
        }

        // Block and ask for the same reply in the user's language
        self.log("stop_block", Some(ratio), length);
        let body = format!(
            "Your last reply looked not in {lang} (a script-ratio check; code or quoted output can trip it). If it is {lang} prose around code \
             or quotes, or the user explicitly asked in this turn for another language, add nothing. Otherwise output only the rewritten reply, \
             the same content in {lang}, with no line about rewriting, the earlier version, the language or this notice, and no apology."
        );
        let out = Dict::from_pairs(vec![
            ("decision".to_owned(), text("block")),
            ("reason".to_owned(), text(self.tag("action", &body)?)),
        ]);
        Ok(Some(dumps_dict(&out, EnsureAscii::No, None)))
    }

    /// python `user_wrote_other_script(path, script)`: 마지막 사용자 프롬프트에 목표 문자 글자가 3개 미만인가.
    fn user_wrote_other_script(&self, script: Script) -> Result<bool> {
        let path = match truthy(self.data, "transcript_path") {
            None => return Ok(false),
            Some(Value::Str(p)) => p.as_str(),
            Some(_) => return Err(Abort("transcript_path is not a string")),
        };
        let Some(prompt) = last_user_prompt(path)? else {
            return Ok(false);
        };
        let unpasted = PASTED.replace_all(&prompt, |_| " ".to_owned());
        Ok(script.count(&strip_text(&unpasted)) < PROMPT_MIN_TARGET)
    }

    /// python `on_batch`.
    pub fn on_batch(&self) -> Result<Option<String>> {
        let Some(lang) = self.language()? else {
            return Ok(None);
        };
        let Some(script) = script_for(&lang) else {
            return Ok(None);
        };

        // Tool calls counted per prompt
        let mut st = state::load(self.ctx, &self.sid)?;
        let pid = self.data.get("prompt_id").cloned().unwrap_or(Value::Null);
        let stored = st.get("prompt_id").cloned().unwrap_or(Value::Null);
        if !py_eq(&stored, &pid) {
            st.insert("prompt_id", pid);
            st.insert("count", Value::Int(0));
            st.insert("next", Value::Int(FIRST_REMINDER));
        }
        let prev = num_at(&st, "count")?.ok_or(Abort("count is missing"))?;
        let calls = py_len(truthy(self.data, "tool_calls"))?.max(1);
        let total = prev
            .checked_add(Num::Int(calls))
            .ok_or(Abort("count overflow"))?;
        st.insert("count", total.value());

        // Drift in text between tool calls, with a cooldown
        let mut out = Vec::new();
        if let Some(path) = truthy(self.data, "transcript_path") {
            let Value::Str(path) = path else {
                return Err(Abort("transcript_path is not a string"));
            };
            if let Some(notice) = self.interim_notice(&mut st, path, script, &lang, total)? {
                out.push(notice);
            }
        }

        // A reminder at 10 calls, then every 15
        let next = num_at(&st, "next")?.ok_or(Abort("next is missing"))?;
        if total.partial_cmp(next).is_some_and(|o| o.is_ge()) {
            let mut next = next;
            while next.partial_cmp(total).is_some_and(|o| o.is_le()) {
                next = next
                    .checked_add(Num::Int(EVERY))
                    .ok_or(Abort("next overflow"))?;
            }
            st.insert("next", next.value());
            self.log("long_turn_reminder", None, Some(total.value()));
            out.push(self.tag("info", &format!("Reply to the user in {lang}."))?);
        }

        state::save(self.ctx, &self.sid, &st);
        if out.is_empty() {
            return Ok(None);
        }
        Ok(Some(context("PostToolBatch", &out.join("\n"))))
    }

    fn interim_notice(
        &self,
        st: &mut Dict,
        path: &str,
        script: Script,
        lang: &str,
        total: Num,
    ) -> Result<Option<String>> {
        let read = read_new_lines(path, st.get("offset"))?;
        if let Some(offset) = read.offset {
            st.insert("offset", offset.value());
        }

        // The worst drifted text since the last read
        let mut worst: Option<(f64, usize)> = None;
        for t in interim_texts(&read.lines)? {
            let (drifted, ratio, _) = is_drift(&t, script);
            if drifted && worst.is_none_or(|(w, _)| ratio < w) {
                worst = Some((ratio, t.chars().count()));
            }
        }
        let Some((ratio, length)) = worst else {
            return Ok(None);
        };

        let last = num_at(st, "last_interim")?.unwrap_or(Num::Int(-99));
        let since = total.checked_sub(last).ok_or(Abort("count overflow"))?;
        if !since
            .partial_cmp(Num::Int(INTERIM_COOLDOWN_CALLS))
            .is_some_and(|o| o.is_ge())
        {
            return Ok(None);
        }
        st.insert("last_interim", total.value());
        self.log(
            "interim_drift",
            Some(ratio),
            Some(Value::Int(length as i128)),
        );
        let body = format!(
            "Some text between tool calls looked not in {lang}; progress notes count, quoted output and identifiers do not. \
             Do not mention this notice."
        );
        Ok(Some(self.tag("info", &body)?))
    }
}

// 상태의 수 칸. 없으면 None, 수가 아니면 python 산술의 TypeError
fn num_at(st: &Dict, key: &str) -> Result<Option<Num>> {
    match st.get(key) {
        None => Ok(None),
        Some(v) => number(v)
            .map(Some)
            .ok_or(Abort("state field is not a number")),
    }
}

/// python `len(value or "")`: 글은 글자 수, 목록과 dict 는 항목 수. 수 같은 참 값은 TypeError.
fn py_len(value: Option<&Value>) -> Result<i128> {
    let n = match value {
        None => 0,
        Some(Value::Str(s)) => s.chars().count(),
        Some(Value::List(l)) => l.len(),
        Some(Value::Dict(d)) => d.len(),
        Some(_) => return Err(Abort("object has no len")),
    };
    Ok(n as i128)
}

fn context(event: &str, body: &str) -> String {
    let inner = Dict::from_pairs(vec![
        ("hookEventName".to_owned(), text(event)),
        ("additionalContext".to_owned(), text(body)),
    ]);
    let outer = Dict::from_pairs(vec![("hookSpecificOutput".to_owned(), Value::Dict(inner))]);
    dumps_dict(&outer, EnsureAscii::No, None)
}
