//! 검토가 아닌 서브에이전트의 보고에 권고, 선택지, 열린 질문이 있으면 메인에게 info 한 줄(python `hooks/handback_notice.py`).
//!
//! SubagentStop 이 보고를 분류해 세션 상태 파일에 남기고, 메인의 UserPromptSubmit(보고가 새 턴으로 들어옴)이나
//! PostToolBatch(일하는 중에 붙음)가 알린다. 에이전트마다 한 번이다. 상태 파일은 python 판과 같은 꼴로 잠그고 바꿔 쓴다.

use std::fs::File;
use std::sync::LazyLock;

use harness_hook::nonce::now_secs;
use harness_hook::py::json::{EnsureAscii, dumps_dict};
use harness_hook::py::path::join;
use harness_hook::py::re::Regex;
use harness_hook::py::text::strip;
use harness_hook::py::value::{Dict, Value};

use crate::abort::{Abort, Result};
use crate::epoch::sanitize;
use crate::hookio::parse_object;
use crate::pylib::fs::{exists, makedirs, os_path, read_bytes, write_text};
use crate::pylib::sha1;
use crate::pylib::text::{dedent, encode_replace, take_chars};

use super::NS;
use super::signals::carries_decisions;
use super::state::number;

/// 상태 파일에 남겨 둘 기간.
const KEEP_SECONDS: f64 = 3.0 * 24.0 * 3600.0;
/// SubagentHandback 을 쓴 에이전트의 task-notification 은 본문 대신 이 안내만 싣는다.
const STUB: &str = "report was delivered to you as a message";
const INHERIT_TAG: &str = "[qwreey-advisor:inherit]";
const REVIEWERS: &[&str] = &["qwreey-advisor:reviewer", "qwreey-advisor-reviewer"];

fn regex(pattern: &str) -> Regex {
    Regex::new(pattern).expect("built-in pattern")
}

static HANDBACK: LazyLock<Regex> =
    LazyLock::new(|| regex(r#"<agent-message from="([^"]+)">\s*\[Subagent hand-back\]"#));
static TASK: LazyLock<Regex> =
    LazyLock::new(|| regex(r"<task-notification>\s*<task-id>([^<]+)</task-id>"));
static SUMMARY: LazyLock<Regex> = LazyLock::new(|| regex(r#"<summary>Agent "(.*?)" "#));
static REVIEW_TEXT: LazyLock<Regex> = LazyLock::new(|| {
    regex(r"\[qwreey-advisor run: |\[second opinion: |\[qwreey-advisor:inherit\]")
});
// qwreey-debate 스킬이 토론자 설명을 `debate:` 로 시작하게 한다
static DEBATE: LazyLock<Regex> = LazyLock::new(|| regex(r"(?i)^\s*(debate|토론)"));
static LABEL_DROP: LazyLock<Regex> = LazyLock::new(|| regex("[`<>\"\n\r]"));

/// python `state_path(sid)`: `<임시 폴더>/claude-second-opinion/<sid>.handbacks.json`. 폴더를 만든다.
pub fn state_path(tempdir: &str, sid: &str) -> Result<String> {
    let dir = join(tempdir, NS);
    makedirs(&dir).map_err(|_| Abort("cannot create the state folder"))?;
    Ok(join(&dir, &format!("{}.handbacks.json", sanitize(sid))))
}

/// python `has_state(sid)`.
pub fn has_state(tempdir: &str, sid: &str) -> Result<bool> {
    Ok(exists(&state_path(tempdir, sid)?))
}

/// python `digest(text)`: 앞뒤 공백을 뗀 글의 sha1 앞 12자.
pub fn digest(text: &str) -> String {
    sha1::hex_prefix(&encode_replace(strip(text)), 12)
}

// python re.sub(r"[`<>\"\n\r]", "", raw)[:60]
fn clean_label(raw: &str) -> String {
    take_chars(&LABEL_DROP.replace_all(raw, |_| String::new()), 60).to_owned()
}

/// 세션의 에이전트별 기록 `{agent_id: {t, label, hit, pending, done, ...}}`. 살아 있는 동안 잠근다(python `State`).
pub struct Handbacks {
    path: String,
    agents: Dict,
    dirty: bool,
    _lock: File,
}

impl Handbacks {
    /// python `State.__enter__`: 잠금 파일을 잡고 상태를 읽는다. 객체가 아닌 기록은 python 이 쓰다가 예외로 끝난다.
    pub fn open(tempdir: &str, sid: &str) -> Result<Handbacks> {
        let path = state_path(tempdir, sid)?;
        let lock_path =
            os_path(&format!("{path}.lock")).ok_or(Abort("lock path cannot be encoded"))?;
        let lock = std::fs::OpenOptions::new()
            .create(true)
            .append(true)
            .open(lock_path)
            .map_err(|_| Abort("cannot open the lock file"))?;
        lock_exclusive(&lock)?;

        // python: json.load(open(path)).get("agents", {}), unreadable -> {}
        let top = read_bytes(&path)
            .ok()
            .and_then(|bytes| parse_object(&bytes).ok())
            .unwrap_or_default();
        let agents = match top.get("agents") {
            None => Dict::new(),
            Some(Value::Dict(agents)) => agents.clone(),
            Some(_) => return Err(Abort("agents is not an object")),
        };
        if agents.iter().any(|(_, e)| !matches!(e, Value::Dict(_))) {
            return Err(Abort("an agent entry is not an object"));
        }
        Ok(Handbacks {
            path,
            agents,
            dirty: false,
            _lock: lock,
        })
    }

    fn entry(&self, aid: &str) -> Option<&Dict> {
        self.agents.get(aid).and_then(Value::as_dict)
    }

    /// python `put(aid, **kw)`: 있던 기록에 `fields` 를 덮는다(있던 키는 제자리, 새 키는 뒤에).
    fn put(&mut self, aid: &str, fields: Dict) {
        let mut merged = self.entry(aid).cloned().unwrap_or_default();
        for (k, v) in fields.iter() {
            merged.insert(k, v.clone());
        }
        self.agents.insert(aid, Value::Dict(merged));
        self.dirty = true;
    }

    /// python `State.__exit__`: 바뀌었으면 오래된 기록을 버리고 임시 파일에 써서 바꿔 놓는다.
    pub fn close(self) -> Result<()> {
        if !self.dirty {
            return Ok(());
        }
        let now = now_secs();
        let mut keep = Dict::new();
        for (aid, entry) in self.agents.iter() {
            let t = match entry.as_dict().and_then(|e| e.get("t")) {
                None => now,
                Some(v) => number(v).ok_or(Abort("t is not a number"))?,
            };
            if now - t < KEEP_SECONDS {
                keep.insert(aid, entry.clone());
            }
        }
        let top = Dict::from_pairs(vec![("agents".to_owned(), Value::Dict(keep))]);
        let tmp = format!("{}.tmp", self.path);
        write_text(&tmp, &dumps_dict(&top, EnsureAscii::Yes, None))
            .map_err(|_| Abort("cannot write the handback state"))?;
        let (from, to) = (os_path(&tmp), os_path(&self.path));
        match (from, to) {
            (Some(from), Some(to)) => {
                std::fs::rename(from, to).map_err(|_| Abort("cannot replace the handback state"))
            }
            _ => Err(Abort("state path cannot be encoded")),
        }
    }
}

#[cfg(unix)]
fn lock_exclusive(file: &File) -> Result<()> {
    rustix::fs::flock(file, rustix::fs::FlockOperation::LockExclusive)
        .map_err(|_| Abort("cannot lock the handback state"))
}

// python 판도 Windows 에서는 잠그지 않는다
#[cfg(not(unix))]
fn lock_exclusive(_file: &File) -> Result<()> {
    Ok(())
}

fn flag(entry: &Dict, key: &str) -> bool {
    entry.get(key).is_some_and(Value::truthy)
}

fn fields(pairs: Vec<(&str, Value)>) -> Dict {
    Dict::from_pairs(pairs.into_iter().map(|(k, v)| (k.to_owned(), v)).collect())
}

/// python `due(entry, reviewed_at)`: 알릴 차례인가(신호가 있고, 아직 알리지 않았고, 그 뒤로 검토가 없었다).
fn due(entry: &Dict, reviewed_at: f64) -> Result<bool> {
    if !flag(entry, "hit") || flag(entry, "done") || flag(entry, "review") {
        return Ok(false);
    }
    let t = match entry.get("t") {
        None => 0.0,
        Some(v) => number(v).ok_or(Abort("t is not a number"))?,
    };
    Ok(reviewed_at < t)
}

// python e.get("label") or "subagent"
fn label_text(entry: &Dict) -> Result<String> {
    match entry.get("label").filter(|v| v.truthy()) {
        None => Ok("subagent".to_owned()),
        Some(v) => v.scalar_str().ok_or(Abort("label is a list or dict")),
    }
}

/// SubagentStop 이 넘기는 것(python `on_stop` 의 인자).
pub struct StopReport<'a> {
    pub agent_id: &'a str,
    /// last_assistant_message 와 SubagentHandback message 를 이은 글.
    pub text: &'a str,
    /// transcript 옆 meta(라벨의 description).
    pub meta: &'a Dict,
    /// 입력의 agent_type(meta 에 description 이 없을 때의 라벨).
    pub agent_type: Option<&'a Value>,
    pub review: bool,
    /// 서브에이전트가 띄운 것이면 `Some(true)`, 메인이면 `Some(false)`, meta 가 없으면 `None`.
    pub nested: Option<bool>,
}

/// python `on_stop`: 보고를 분류해 남긴다.
pub fn on_stop(tempdir: &str, sid: &str, report: &StopReport<'_>) -> Result<()> {
    let h = digest(report.text);
    let mut st = Handbacks::open(tempdir, sid)?;
    let aid = report.agent_id;

    // The same report only once; a resumed agent with a new report is seen again
    if let Some(old) = st.entry(aid)
        && flag(old, "done")
        && (flag(old, "review") || old.get("h").and_then(Value::as_str) == Some(h.as_str()))
    {
        return st.close();
    }

    // A review is recorded as done
    if report.review {
        st.put(
            aid,
            fields(vec![
                ("t", Value::Float(now_secs())),
                ("review", Value::Bool(true)),
                ("done", Value::Bool(true)),
            ]),
        );
        return st.close();
    }

    // Only reports from agents the main session started wait for a notice
    if report.nested != Some(false) {
        return st.close();
    }
    let label = clean_label(&raw_label(report.meta, report.agent_type)?);
    let hit = carries_decisions(report.text) && !DEBATE.is_match(&label);
    let entry = fields(vec![
        ("t", Value::Float(now_secs())),
        ("label", Value::Str(label)),
        ("h", Value::Str(h)),
        ("pending", Value::Bool(true)),
        ("hit", Value::Bool(hit)),
    ]);
    st.agents.insert(aid, Value::Dict(entry));
    st.dirty = true;
    st.close()
}

/// python `parse_prompt(prompt)`: (agent_id, 보고 본문, 설명). 서브에이전트 보고가 아니면 `None`.
fn parse_prompt(prompt: &str) -> Option<(String, String, String)> {
    if let Some(m) = HANDBACK.search(prompt) {
        let body = &prompt[m.end()..];
        let body = body
            .split_once("The report follows:")
            .map_or(body, |(_, rest)| rest);
        let aid = m.text(prompt, 1).unwrap_or("").to_owned();
        return Some((aid, dedent(body.trim_start_matches('\n')), String::new()));
    }
    let m = TASK.search(prompt)?;
    if !prompt.contains("<result>") {
        return None;
    }
    let desc = SUMMARY
        .search(prompt)
        .and_then(|s| s.text(prompt, 1))
        .unwrap_or("")
        .to_owned();
    let after = prompt.split_once("<result>").map_or("", |(_, rest)| rest);
    let body = after
        .rsplit_once("</result>")
        .map_or(after, |(head, _)| head);
    let body = if body.contains(STUB) { "" } else { body };
    let aid = strip(m.text(prompt, 1).unwrap_or("")).to_owned();
    Some((aid, body.to_owned(), desc))
}

/// python `on_prompt`: 이 prompt 가 서브에이전트 보고면 그 에이전트의 알림 이름(알릴 것이 없으면 빈 목록).
pub fn on_prompt(tempdir: &str, sid: &str, prompt: &str, reviewed_at: f64) -> Result<Vec<String>> {
    let Some((aid, body, desc)) = parse_prompt(prompt) else {
        return Ok(Vec::new());
    };
    let mut st = Handbacks::open(tempdir, sid)?;
    let hb = if body.is_empty() {
        String::new()
    } else {
        digest(&body)
    };

    // A resumed agent's new report replaces the old entry
    let mut entry = st.entry(&aid).cloned();
    if let Some(e) = &entry
        && !body.is_empty()
        && flag(e, "done")
        && !flag(e, "review")
        && flag(e, "hb")
        && e.get("hb").and_then(Value::as_str) != Some(hb.as_str())
    {
        entry = None;
    }

    // An unknown agent is classified from the prompt itself
    let mut entry = match entry {
        Some(e) => e,
        None => {
            if body.is_empty() {
                st.close()?;
                return Ok(Vec::new());
            }
            let label = match clean_label(&desc) {
                l if l.is_empty() => "subagent".to_owned(),
                l => l,
            };
            let hit = carries_decisions(&body)
                && !REVIEW_TEXT.is_match(&body)
                && !DEBATE.is_match(&label);
            fields(vec![
                ("t", Value::Float(now_secs())),
                ("label", Value::Str(label)),
                ("hit", Value::Bool(hit)),
            ])
        }
    };
    if !hb.is_empty() {
        entry.insert("hb", Value::Str(hb));
    }

    // Mark it done; notify only when due
    let is_due = due(&entry, reviewed_at)?;
    let label = if is_due {
        Some(label_text(&entry)?)
    } else {
        None
    };
    let mark_done =
        is_due || (!flag(&entry, "done") && (!body.is_empty() || flag(&entry, "review")));
    if mark_done {
        entry.insert("done", Value::Bool(true));
        st.put(&aid, entry);
    }
    st.close()?;
    Ok(label.into_iter().collect())
}

/// PostToolBatch 의 한 도구 호출이 검토를 띄우는가(python `starts_review`).
fn starts_review(call: &Dict) -> Result<bool> {
    let ti = match call.get("tool_input").filter(|v| v.truthy()) {
        None => return Ok(false),
        Some(Value::Dict(ti)) => ti,
        Some(_) => return Err(Abort("tool_input has no get")),
    };
    let kind = ti.get("subagent_type").and_then(Value::as_str);
    if kind.is_some_and(|k| REVIEWERS.contains(&k)) {
        return Ok(true);
    }
    let prompt = ti.get("prompt").and_then(Value::as_str).unwrap_or("");
    Ok(kind == Some("fork") && prompt.starts_with(INHERIT_TAG))
}

/// python `on_batch`: 일하는 중에 붙은 보고 가운데 아직 알리지 않은 것의 이름.
pub fn on_batch(
    tempdir: &str,
    sid: &str,
    tool_calls: Option<&Value>,
    reviewed_at: f64,
) -> Result<Vec<String>> {
    // Is this batch already starting a review
    let calls: &[Value] = match tool_calls.filter(|v| v.truthy()) {
        None => &[],
        Some(Value::List(calls)) => calls,
        Some(Value::Str(_) | Value::Dict(_)) => &[],
        Some(_) => return Err(Abort("tool_calls is not iterable")),
    };
    let mut reviewing = false;
    for call in calls {
        if let Value::Dict(call) = call
            && starts_review(call)?
        {
            reviewing = true;
            break;
        }
    }

    // Pending reports: notify the due ones, mark all done
    let mut st = Handbacks::open(tempdir, sid)?;
    let walked = mark_pending(&mut st, reviewing, reviewed_at);
    // python 의 with 는 예외가 나도 그때까지 바꾼 것을 쓴다
    st.close()?;
    walked
}

fn mark_pending(st: &mut Handbacks, reviewing: bool, reviewed_at: f64) -> Result<Vec<String>> {
    let mut out = Vec::new();
    let ids: Vec<String> = st.agents.iter().map(|(k, _)| k.to_owned()).collect();
    for aid in ids {
        let Some(entry) = st.entry(&aid).cloned() else {
            continue;
        };
        if flag(&entry, "done") || !flag(&entry, "pending") {
            continue;
        }
        if due(&entry, reviewed_at)? && !reviewing {
            out.push(label_text(&entry)?);
        }
        st.put(&aid, fields(vec![("done", Value::Bool(true))]));
    }
    Ok(out)
}

/// python `message(labels)`: 메인에게 낼 info 글.
pub fn message(labels: &[String]) -> String {
    let names: Vec<String> = labels.iter().map(|x| format!("\"{x}\"")).collect();
    let names = names.join(", ");
    let subject = if labels.len() == 1 {
        format!("The report from subagent {names} carries")
    } else {
        format!("The reports from subagents {names} carry")
    };
    format!(
        "{subject} recommendations, options or open questions. If you will pass them to the user to decide, they rest on that \
         agent's check alone; `qwreey-advisor:inherit-advisor` (tests your reasoning) or `qwreey-advisor:fresh-advisor` \
         (tests the framing) can look first. Skip this for facts you verified yourself or questions you only relay."
    )
}

/// SubagentStop 의 라벨 원문(python `label_of` 의 `str(raw)`): meta 의 description, agent_type, subagent 순서.
fn raw_label(meta: &Dict, agent_type: Option<&Value>) -> Result<String> {
    let raw = meta
        .get("description")
        .filter(|v| v.truthy())
        .or(agent_type.filter(|v| v.truthy()));
    match raw {
        None => Ok("subagent".to_owned()),
        Some(v) => v.scalar_str().ok_or(Abort("label is a list or dict")),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 보고 prompt 두 꼴(hand-back 메시지, task-notification)에서 id, 본문, 설명을 꺼낸다.
    #[test]
    fn parses_both_report_shapes() {
        // agent-message hand-back: body after "The report follows:", dedented
        let p = "<agent-message from=\"a1\">\n[Subagent hand-back] The report follows:\n  x\n  y";
        assert_eq!(
            parse_prompt(p),
            Some(("a1".to_owned(), "x\ny".to_owned(), String::new()))
        );

        // task-notification with a result and a summary
        let p = "<task-notification>\n<task-id> t9 </task-id><summary>Agent \"fix\" done</summary><result>R</result>";
        assert_eq!(
            parse_prompt(p),
            Some(("t9".to_owned(), "R".to_owned(), "fix".to_owned()))
        );

        // The stub result of a SubagentHandback agent has no body
        let p = format!("<task-notification><task-id>t</task-id><result>{STUB}</result>");
        assert_eq!(
            parse_prompt(&p).map(|(_, body, _)| body),
            Some(String::new())
        );
        assert_eq!(parse_prompt("hello"), None);
    }

    /// 알림 글은 이름이 하나면 단수, 여럿이면 복수다.
    #[test]
    fn message_number() {
        assert!(message(&["a".to_owned()]).starts_with("The report from subagent \"a\" carries"));
        assert!(
            message(&["a".to_owned(), "b".to_owned()])
                .starts_with("The reports from subagents \"a\", \"b\" carry")
        );
    }
}
