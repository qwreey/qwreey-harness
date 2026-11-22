//! SubagentStart, SubagentStop, Stop: 예약을 실행 중으로 옮기고, 끝난 에이전트의 사용량을 세고, 어긋난 셈을 바로잡는다
//! (python `subagent_start`, `subagent_stop`, `stop`, `reconcile`).

use std::cmp::Ordering;

use harness_hook::py::value::{Dict, Value};

use super::away;
use super::call::Call;
use super::ledger::{account_agent, dict_mut, key_of, live, log, meta, meta_get, num_or};
use super::spend::family;
use crate::num::Num;
use crate::stop::{Result, Stop};

/// 이보다(초) 최근에 띄운 실행 중 항목은 background_tasks 에 아직 없을 수 있어 복구에서 지키고 다시 넣는다.
const GRACE_SEC: f64 = 10.0;

/// python `subagent_start`: 예약 하나를 이 에이전트의 실행 중 항목으로 옮긴다.
///
/// 예약은 meta.json 의 toolUseId 로 찾고, 없으면 같은 형식(Workflow 안의 에이전트는 Workflow 예약)의 가장 오래된 것,
/// 그것도 없으면 아무 Agent 예약의 가장 오래된 것이다.
pub fn start(call: &Call, st: &mut Dict) -> Result<()> {
    let Some(aid) = call.truthy("agent_id") else {
        return Ok(());
    };
    let kind = call
        .truthy("agent_type")
        .cloned()
        .unwrap_or_else(|| Value::Str(String::new()));
    let aid = key_of(aid)?;

    // Already running: refresh its time
    if let Some(entry) = dict_mut(st, "running")?.get_mut(aid) {
        let Value::Dict(entry) = entry else {
            return Err(Stop::Raises(
                "assigning into a running entry that is not a dict",
            ));
        };
        entry.insert("t", Value::Float(call.now));
        return Ok(());
    }

    // The reservation this agent came from, and its family
    let meta = meta(st, aid)?;
    let reservation = take_reservation(st, meta.as_ref(), &kind)?;
    let from_reservation = |key: &str| -> Result<Option<Value>> {
        match reservation.as_ref().filter(|v| v.truthy()) {
            None => Ok(None),
            Some(Value::Dict(r)) => Ok(r.get(key).cloned()),
            Some(_) => Err(Stop::Raises("r.get on a reservation that is not a dict")),
        }
    };
    let fam = match from_reservation("fam")?.filter(|v| v.truthy()) {
        Some(fam) => fam,
        None => match meta_get(meta.as_ref(), "model")?.filter(|v| v.truthy()) {
            Some(model) => Value::Str(family(Some(model)).to_owned()),
            None => Value::Str("?".to_owned()),
        },
    };
    let background = from_reservation("bg")?.is_some_and(|v| v.truthy());

    let entry = Dict::from_pairs(vec![
        ("t".to_owned(), Value::Float(call.now)),
        ("fam".to_owned(), fam),
        ("type".to_owned(), kind),
        ("bg".to_owned(), Value::Bool(background)),
    ]);
    dict_mut(st, "running")?.insert(aid, Value::Dict(entry));
    Ok(())
}

// meta.json 의 toolUseId 예약, 없으면 같은 형식의 가장 오래된 예약을 꺼낸다
fn take_reservation(st: &mut Dict, meta: Option<&Value>, kind: &Value) -> Result<Option<Value>> {
    let tool_use_id = meta_get(meta, "toolUseId")?;
    let reserved = dict_mut(st, "reserved")?;
    match tool_use_id {
        Some(Value::Str(id)) if reserved.get(id).is_some() => return Ok(reserved.remove(id)),
        Some(Value::List(_) | Value::Dict(_)) => {
            return Err(Stop::Raises("an unhashable toolUseId"));
        }
        _ => {}
    }

    // Same kind first; any Agent reservation when none matches
    let workflow = kind.as_str() == Some("workflow-subagent");
    let mut candidates = Vec::new();
    for (key, r) in reserved.iter() {
        let Value::Dict(r) = r else {
            return Err(Stop::Raises("v.get on a reservation that is not a dict"));
        };
        let is_workflow = r.get("kind").and_then(Value::as_str) == Some("workflow");
        let same_type = r.get("type").is_some_and(|t| crate::pyval::py_eq(t, kind));
        if is_workflow == workflow && (workflow || same_type) {
            candidates.push((reserved_time(r)?, key.to_owned()));
        }
    }
    let mut by_key = false;
    if candidates.is_empty() && !workflow {
        for (key, r) in reserved.iter() {
            let Value::Dict(r) = r else {
                return Err(Stop::Raises("v.get on a reservation that is not a dict"));
            };
            if r.get("kind").and_then(Value::as_str) == Some("agent") {
                candidates.push((reserved_time(r)?, key.to_owned()));
            }
        }
        by_key = true;
    }

    // The oldest: python sorts by time (stable), the fallback by (time, key)
    let Some(oldest) = oldest(candidates, by_key)? else {
        return Ok(None);
    };
    Ok(reserved.remove(&oldest))
}

// python v["t"]
fn reserved_time(r: &Dict) -> Result<Value> {
    r.get("t")
        .cloned()
        .ok_or(Stop::Raises("KeyError on a reservation's t"))
}

// python sorted(...)[0][1]. 둘 이상이면 시각을 견준다(수만 옮겼다: python 은 글끼리도 견주고, 섞이면 TypeError)
fn oldest(candidates: Vec<(Value, String)>, by_key: bool) -> Result<Option<String>> {
    if candidates.len() < 2 {
        return Ok(candidates.into_iter().next().map(|(_, key)| key));
    }

    // Times as numbers, without NaN
    let mut timed = Vec::with_capacity(candidates.len());
    for (t, key) in candidates {
        let t = Num::of(&t).ok_or(Stop::Unported(
            "sorting reservation times that are not numbers",
        ))?;
        if t.compare(t).is_none() {
            return Err(Stop::Unported("sorting reservations with a NaN time"));
        }
        timed.push((t, key));
    }

    // Stable sort by time; the fallback breaks ties by key
    timed.sort_by(|(a, ka), (b, kb)| {
        let by_time = a.compare(*b).unwrap_or(Ordering::Equal);
        if by_key {
            by_time.then_with(|| ka.cmp(kb))
        } else {
            by_time
        }
    });
    Ok(timed.into_iter().next().map(|(_, key)| key))
}

/// python `subagent_stop`: 실행 중 항목을 지우고 트랜스크립트 사용량을 센 뒤, 어긋난 셈을 바로잡는다.
pub fn stop(call: &Call, st: &mut Dict) -> Result<()> {
    if let Some(aid) = call.truthy("agent_id") {
        let aid = key_of(aid)?;
        let running = dict_mut(st, "running")?.remove(aid);
        let fam = match running.as_ref().filter(|v| v.truthy()) {
            None => Value::Null,
            Some(Value::Dict(r)) => r.get("fam").cloned().unwrap_or(Value::Null),
            Some(_) => return Err(Stop::Raises("r.get on a running entry that is not a dict")),
        };

        // Count the transcript, mark the stop time, log it
        let accounted = account_agent(st, aid, call.get("agent_transcript_path"))?;
        let usd = match &accounted {
            Some(a) => {
                if a.kept {
                    mark_stopped(st, aid, call.now)?;
                }
                Num::need(&a.usd)?.round(4).value()
            }
            None => Value::Int(0),
        };
        let fields = vec![
            ("id", Value::Str(aid.to_owned())),
            ("fam", fam),
            ("usd", usd),
        ];
        log(st, "stop", fields)?;
    }
    reconcile(call, st)
}

fn mark_stopped(st: &mut Dict, aid: &str, now: f64) -> Result<()> {
    match dict_mut(st, "agents")?.get_mut(aid) {
        Some(Value::Dict(agent)) => {
            agent.insert("stopped", Value::Float(now));
            Ok(())
        }
        _ => Err(Stop::Raises("an agent record that is not a dict")),
    }
}

/// python `stop` 와 `reconcile`: background_tasks 로 실행 중 셈을 고치고(막 띄운 것은 지킨다), 예산 도달 시각을 남긴다.
pub fn reconcile(call: &Call, st: &mut Dict) -> Result<()> {
    match call.get("background_tasks") {
        Some(Value::List(tasks)) => {
            // Agents spawned just now may not be listed yet
            let mut grace = Vec::new();
            for (key, r) in dict_mut(st, "running")?.iter() {
                let Value::Dict(entry) = r else {
                    return Err(Stop::Raises("v.get on a running entry that is not a dict"));
                };
                if Num::Float(call.now)
                    .minus(num_or(entry, "t", Num::Int(0))?)?
                    .lt(Num::Float(GRACE_SEC))
                {
                    grace.push((key.to_owned(), r.clone()));
                }
            }

            live(st, call.cfg, call.now, Some(tasks))?;
            let running = dict_mut(st, "running")?;
            for (key, r) in grace {
                running.insert(key, r);
            }
        }
        _ => {
            live(st, call.cfg, call.now, None)?;
        }
    }

    // Stage times stay exact
    away::check(st, call.cfg, call.limits().as_ref(), call.now)?;
    Ok(())
}
