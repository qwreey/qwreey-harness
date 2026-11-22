//! PostToolUse(모든 도구): Agent, Task 의 결과로 원장을 고치고, away 중 메인이 혼자 일할 때 같은 안내를 한 번 준다
//! (python `post_tool`, `post_agent`, `main_notice`).

use harness_hook::py::value::{Dict, Value};
use harness_hook::tag::Level;

use super::away;
use super::call::{Call, Out};
use super::ledger::{account_agent, account_main, dict_mut, key_of, log, text};
use super::pre::note_set;
use super::spend::family;
use crate::num::Num;
use crate::stop::{Result, Stop};

/// 메인 단독 안내에서 트랜스크립트를 다시 읽는 간격(초).
const MAIN_EVAL_SEC: f64 = 15.0;

/// python `post_tool`: Agent, Task 는 먼저 원장을 고치고, 그다음 메인이면 away 안내를 본다.
pub fn tool(call: &Call, st: &mut Dict) -> Result<Option<Out>> {
    if matches!(
        call.get("tool_name").and_then(Value::as_str),
        Some("Agent" | "Task")
    ) {
        agent(call, st)?;
    }
    main_notice(call, st)
}

// python `post_agent`: 예약을 풀고, 백그라운드면 실행 중으로, 끝난 포그라운드면 사용량을 센다
fn agent(call: &Call, st: &mut Dict) -> Result<()> {
    let empty = Dict::new();
    let response = match call.get("tool_response") {
        Some(Value::Dict(d)) => d,
        _ => &empty,
    };
    let reserved = take_reserved(call, st)?;
    let Some(aid) = response.get("agentId").filter(|v| v.truthy()) else {
        return Ok(());
    };

    // The family: the resolved model, else the reservation's guess
    let reserved_get = |key: &str| -> Result<Option<Value>> {
        match reserved.as_ref().filter(|v| v.truthy()) {
            None => Ok(None),
            Some(Value::Dict(r)) => Ok(r.get(key).cloned()),
            Some(_) => Err(Stop::Raises("r.get on a reservation that is not a dict")),
        }
    };
    let resolved = response.get("resolvedModel").filter(|v| v.truthy());
    let fam = match resolved {
        Some(model) => Value::Str(family(Some(model)).to_owned()),
        None => reserved_get("fam")?.unwrap_or_else(|| Value::Str("?".to_owned())),
    };

    match response.get("status").and_then(Value::as_str) {
        Some("async_launched") => {
            let kind = match response.get("agentType").filter(|v| v.truthy()) {
                Some(kind) => kind.clone(),
                None => reserved_get("type")?.unwrap_or(Value::Null),
            };
            let aid = key_of(aid)?;
            let fresh = Dict::from_pairs(vec![("t".to_owned(), Value::Float(call.now))]);
            let Value::Dict(entry) = dict_mut(st, "running")?.setdefault(aid, Value::Dict(fresh))
            else {
                return Err(Stop::Raises(
                    "e.update on a running entry that is not a dict",
                ));
            };
            entry.insert("fam", fam);
            entry.insert("type", kind);
            entry.insert("bg", Value::Bool(true));
        }
        Some("completed") => {
            let aid = key_of(aid)?;
            dict_mut(st, "running")?.remove(aid);
            account_agent(st, aid, None)?;
        }
        _ => {}
    }
    Ok(())
}

// python `st["reserved"].pop(data.get("tool_use_id") or "", None) or {}` 의 꺼낸 값
fn take_reserved(call: &Call, st: &mut Dict) -> Result<Option<Value>> {
    let reserved = dict_mut(st, "reserved")?;
    match call.truthy("tool_use_id") {
        None => Ok(reserved.remove("")),
        Some(Value::Str(id)) => Ok(reserved.remove(id)),
        Some(Value::List(_) | Value::Dict(_)) => Err(Stop::Raises("an unhashable tool_use_id")),
        Some(_) => Ok(None),
    }
}

/// python `main_notice`: away 중 메인(agent_id 없음)에게 1단계 warn, 2단계 action 을 (회차, away 선언)마다 한 번.
///
/// 트랜스크립트는 [`MAIN_EVAL_SEC`] 초에 한 번만 다시 읽는다. pre 의 거절과 같은 notes 키를 써서 이미 받았으면 조용하다.
fn main_notice(call: &Call, st: &mut Dict) -> Result<Option<Out>> {
    if call.truthy("agent_id").is_some() || !away::is_on(st)? {
        return Ok(None);
    }
    let since_eval =
        Num::Float(call.now).minus(super::ledger::num_or(st, "main_eval", Num::Int(0))?)?;
    if since_eval.ge(Num::Float(MAIN_EVAL_SEC)) {
        st.insert("main_eval", Value::Float(call.now));
        account_main(st, call.get("transcript_path"))?;
    }

    // The budget verdict
    let Some(verdict) = away::check(st, call.cfg, call.limits().as_ref(), call.now)? else {
        return Ok(None);
    };
    if verdict.level < 1 {
        return Ok(None);
    }
    let away = dict_mut(st, "away")?;
    let key = format!("{}:{}", call.epoch(), text(away.get("since")));
    let over_slots = text(Some(away.get("over_slots").unwrap_or(&Value::Int(1))));
    let why = verdict.why.as_deref().unwrap_or("None");

    // Stage 2: write the state down and wait
    if verdict.level >= 2 {
        if dict_mut(st, "notes")?
            .get("stage2:main")
            .and_then(Value::as_str)
            == Some(key.as_str())
        {
            return Ok(None);
        }
        note_set(st, "stage2:main", &key)?;
        note_set(st, "over:main", &key)?;
        log(st, "stage2-main-notice", Vec::new())?;
        let body = format!(
            "halt: the away budget's stage 2 is reached ({why}). New subagents and workflows are refused until the user returns; \
             you are working on your own, so nothing else is stopped. Write the current state to the progress file (or the session notes) now: \
             what is done, what is running, what is next, and what needs the user's decision. Then wait for the user; \
             finish the small step in hand but start no new large work."
        );
        return Ok(Some(Out::PostContext(call.tag(Level::Action, &body)?)));
    }

    // Stage 1: reconsider the spend
    if !note_set(st, "over:main", &key)? {
        return Ok(None);
    }
    log(st, "over-main-notice", Vec::new())?;
    let body = format!(
        "Away budget reached ({why}). Nothing is stopped. If you spawn subagents they now run {over_slots} at a time. \
         Reconsider whether the remaining work is worth the spend, prefer small steps over large new work, and mention this in your next report to the user."
    );
    Ok(Some(Out::PostContext(call.tag(Level::Warn, &body)?)))
}
