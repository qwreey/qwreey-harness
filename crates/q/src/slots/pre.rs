//! PreToolUse(Agent, Task, Workflow): 큰 팬아웃 고지, away 슬롯과 예산(python `pre_agent`, `pre_workflow`, `stage2_deny`).
//!
//! - attended(기본): 막지 않는다. 동시 N 개 이상, opus 이상 M 개 이상, Workflow 면 warn 을 팬아웃 묶음과 회차마다 한 번.
//! - away: 실행 중 수가 슬롯 이상이면 deny(`queue: ...`). 예산을 넘기면 슬롯을 줄이고 재고 알림을 한 번, 2배를 넘기면 새
//!   Agent, Workflow 를 모두 deny(`halt: ...`). 세션은 멈추지 않는다.

use harness_hook::py::repr::str_value;
use harness_hook::py::text::strip;
use harness_hook::py::value::{Dict, Value};
use harness_hook::tag::Level;

use super::agents::spawn_family;
use super::away::{self, Verdict};
use super::call::{Call, Out};
use super::ledger::{Item, dict_mut, fams_text, live, log, num_or, text};
use super::spend::BIG;
use crate::num::Num;
use crate::stop::{Result, Stop};

/// python `pre_agent`: 에이전트 하나를 예약하고 고지나 거절을 정한다.
pub fn agent(call: &Call, st: &mut Dict) -> Result<Option<Out>> {
    let empty = Dict::new();
    let tool_input = match call.truthy("tool_input") {
        None => &empty,
        Some(Value::Dict(d)) => d,
        Some(_) => return Err(Stop::Raises("ti.get on a tool_input that is not a dict")),
    };
    let fam = spawn_family(tool_input, st, call.get("cwd"), call.home)?;

    // A new burst starts when nothing runs
    let items = live(st, call.cfg, call.now, None)?;
    if items.is_empty() {
        let burst = num_or(st, "burst", Num::Int(0))?.plus(Num::Int(1))?;
        st.insert("burst", burst.value());
    }

    let out = if away::is_on(st)? {
        match away_agent(call, st, &items, fam)? {
            Decision::Refuse(out) => return Ok(Some(out)),
            Decision::Allow(out) => out,
        }
    } else {
        fanout_notice(call, st, &items, fam)?
    };

    // Reserve until SubagentStart
    let kind = tool_input
        .get("subagent_type")
        .filter(|v| v.truthy())
        .cloned()
        .unwrap_or_else(|| Value::Str("general-purpose".to_owned()));
    let background = tool_input
        .get("run_in_background")
        .is_none_or(Value::truthy);
    let entry = Dict::from_pairs(vec![
        ("t".to_owned(), Value::Float(call.now)),
        ("fam".to_owned(), Value::Str(fam.to_owned())),
        ("type".to_owned(), kind),
        ("bg".to_owned(), Value::Bool(background)),
        ("kind".to_owned(), Value::Str("agent".to_owned())),
    ]);
    reserve(call, st, entry)?;
    let spawned = num_or(st, "spawned", Num::Int(0))?.plus(Num::Int(1))?;
    st.insert("spawned", spawned.value());
    let subagent_type = tool_input
        .get("subagent_type")
        .cloned()
        .unwrap_or(Value::Null);
    log(
        st,
        "spawn",
        vec![("fam", Value::Str(fam.to_owned())), ("type", subagent_type)],
    )?;
    Ok(out)
}

/// away 중의 결정: 거절(예약하지 않는다) 또는 허락(알림이 있을 수 있다).
enum Decision {
    Refuse(Out),
    Allow(Option<Out>),
}

// away 중 에이전트 하나: 2단계면 거절, 슬롯이 찼으면 줄 세우기, 예산을 넘겼으면 재고 알림 한 번
fn away_agent(call: &Call, st: &mut Dict, items: &[Item], fam: &str) -> Result<Decision> {
    let verdict =
        away::check(st, call.cfg, call.limits().as_ref(), call.now)?.unwrap_or(NO_VERDICT);
    if verdict.level >= 2 {
        return stage2_deny(call, st, &verdict, "agent").map(Decision::Refuse);
    }

    // Slot limit: fewer slots once the budget is used up
    let over = verdict.why.clone();
    let limit = {
        let away = away_dict(st)?;
        match &over {
            Some(_) => away.get("over_slots").cloned().unwrap_or(Value::Int(1)),
            None => away.get("slots").cloned().unwrap_or(Value::Int(2)),
        }
    };
    if Num::Int(items.len() as i128).ge(Num::need(&limit)?) {
        return queue_refusal(call, st, items, fam, &limit, over.as_deref()).map(Decision::Refuse);
    }

    // Over budget: one reminder per (caller, epoch, away)
    let Some(over) = over else {
        return Ok(Decision::Allow(None));
    };
    let key = format!("{}:{}", call.epoch(), text(away_dict(st)?.get("since")));
    if !note_set(st, &format!("over:{}", call.who()), &key)? {
        return Ok(Decision::Allow(None));
    }
    let body = format!(
        "Away budget reached ({over}). Subagents are now serialized ({} at a time); nothing is stopped. \
         Before each further spawn, consider: can an agent you already have be resumed (SendMessage) instead of a new one; \
         can a lighter model do it where a mistake is cheap; is the remaining work worth the spend. \
         Mention this in your next report to the user.",
        str_value(&limit)
    );
    Ok(Decision::Allow(Some(Out::PreContext(
        call.tag(Level::Warn, &body)?,
    ))))
}

// 슬롯이 찼다: 줄 세우고 막는다(예약하지 않는다)
fn queue_refusal(
    call: &Call,
    st: &mut Dict,
    items: &[Item],
    fam: &str,
    limit: &Value,
    over: Option<&str>,
) -> Result<Out> {
    let n = items.len();
    bump_queued(st)?;
    let fields = vec![
        ("n", Value::Int(n as i128)),
        ("limit", limit.clone()),
        ("fam", Value::Str(fam.to_owned())),
    ];
    log(st, "queued", fields)?;

    let limit = str_value(limit);
    let why = match over {
        Some(over) => {
            format!(" The away budget is used up ({over}), so subagents now run {limit} at a time.")
        }
        None => String::new(),
    };
    let body = format!(
        "queue: wait for a running agent to finish, then spawn the next. Away mode is on (the user declared /q:away): \
         {n} subagents running ({}), slot limit {limit}.{why} This call did not run; the session is not stopped. \
         Do not retry until a completion notification arrives; meanwhile do non-agent work or end the turn. \
         Before respawning, check whether a smaller model (sonnet) or a smaller pass would do.",
        fams_text(items)?
    );
    Ok(Out::Deny(call.tag(Level::Action, &body)?))
}

const NO_VERDICT: Verdict = Verdict {
    level: 0,
    why: None,
};

// attended: 이 호출로 동시 실행이나 opus 이상이 문턱을 넘으면 묶음과 회차마다 warn 한 번
fn fanout_notice(call: &Call, st: &mut Dict, items: &[Item], fam: &str) -> Result<Option<Out>> {
    let after = items.len() as i128 + 1;
    let is_big = |f: Option<&Value>| f.and_then(Value::as_str).is_some_and(|f| BIG.contains(&f));
    let big = items.iter().filter(|r| is_big(r.get("fam"))).count() as i128
        + i128::from(BIG.contains(&fam));
    let over_count = Num::Int(after).ge(call.cfg.int("HARNESS_FANOUT_WARN_CONCURRENT"));
    let over_big = Num::Int(big).ge(call.cfg.int("HARNESS_FANOUT_WARN_BIG"));
    let key = format!(
        "{}:{}",
        call.epoch(),
        text(Some(
            st.get("burst").ok_or(Stop::Raises("KeyError on burst"))?
        ))
    );
    if !(over_count || over_big) || !note_set(st, &format!("fanout:{}", call.who()), &key)? {
        return Ok(None);
    }

    log(
        st,
        "fanout-warn",
        vec![("n", Value::Int(after)), ("big", Value::Int(big))],
    )?;
    let mut with_this = items.to_vec();
    with_this.push(Dict::from_pairs(vec![(
        "fam".to_owned(),
        Value::Str(fam.to_owned()),
    )]));
    let body = format!(
        "Several subagents at once: with this call {after} run ({}; opus-or-above: {big}). Not blocked. \
         If you have not yet, tell the user in one line: how many, which models, why, and the expected size. \
         Independent parts in parallel are fine. If several of them cover the same code or question, consider one \
         agent working in small steps instead, reviewed between steps and resumed with SendMessage: it keeps what \
         it has read (its cache lasts about an hour) and corrects itself from concrete counter-evidence, \
         until its context grows large (past about 200k tokens), when a fresh agent with a short brief is cheaper.",
        fams_text(&with_this)?
    );
    Ok(Some(Out::PreContext(call.tag(Level::Warn, &body)?)))
}

/// python `pre_workflow`: Workflow 하나를 예약하고 고지나 거절을 정한다.
pub fn workflow(call: &Call, st: &mut Dict) -> Result<Option<Out>> {
    let items = live(st, call.cfg, call.now, None)?;
    let n = items.len();

    let out = if away::is_on(st)? {
        match away_workflow(call, st, n)? {
            Decision::Refuse(out) => return Ok(Some(out)),
            Decision::Allow(out) => out,
        }
    } else if !matches!(
        call.cfg
            .get("HARNESS_FANOUT_WARN_WORKFLOW", "on")
            .to_lowercase()
            .as_str(),
        "off" | "0" | "no"
    ) {
        let body = "Workflow requested: a workflow spawns many subagents (up to 16 at once by default). Not blocked. \
                    Tell the user in one line now: the phases, agent count, models, why a workflow rather than a few \
                    sequential agents, and the expected size.";
        Some(Out::PreContext(call.tag(Level::Warn, body)?))
    } else {
        None
    };

    // Reserve until the workflow's agents start
    let entry = Dict::from_pairs(vec![
        ("t".to_owned(), Value::Float(call.now)),
        ("fam".to_owned(), Value::Str("?".to_owned())),
        ("type".to_owned(), Value::Str("workflow".to_owned())),
        ("bg".to_owned(), Value::Bool(true)),
        ("kind".to_owned(), Value::Str("workflow".to_owned())),
    ]);
    reserve(call, st, entry)?;
    log(st, "workflow", Vec::new())?;
    Ok(out)
}

// away 중 Workflow: 2단계, 정책(deny, idle, allow), 슬롯
fn away_workflow(call: &Call, st: &mut Dict, n: usize) -> Result<Decision> {
    let verdict =
        away::check(st, call.cfg, call.limits().as_ref(), call.now)?.unwrap_or(NO_VERDICT);
    if verdict.level >= 2 {
        return stage2_deny(call, st, &verdict, "workflow").map(Decision::Refuse);
    }

    // Policy: deny always, or idle (only when nothing runs), or allow
    let policy = strip(call.cfg.get("HARNESS_AWAY_WORKFLOW", "idle")).to_lowercase();
    if policy == "deny" {
        bump_queued(st)?;
        log(
            st,
            "queued",
            vec![("kind", Value::Str("workflow".to_owned()))],
        )?;
        let body = "Away mode is on and workflows are disabled while away (HARNESS_AWAY_WORKFLOW=deny). \
                    Run the stages as sequential Agent calls instead; the session is not stopped.";
        return Ok(Decision::Refuse(Out::Deny(call.tag(Level::Action, body)?)));
    }
    if policy != "allow" && n > 0 {
        bump_queued(st)?;
        log(
            st,
            "queued",
            vec![
                ("kind", Value::Str("workflow".to_owned())),
                ("n", Value::Int(n as i128)),
            ],
        )?;
        let slots = text(away_dict(st)?.get("slots"));
        let body = format!(
            "queue: wait for a running agent to finish, then spawn the next. Away mode is on: a workflow fans out beyond \
             the slot limit ({slots}), so it may start only when no subagent is running ({n} running now). \
             This call did not run; the session is not stopped. Consider sequential Agent calls instead."
        );
        return Ok(Decision::Refuse(Out::Deny(call.tag(Level::Action, &body)?)));
    }

    let body = "Away mode: this workflow's internal concurrency is not governed by the slot limit \
                (the runtime allows up to 16 agents at once by default). Keep it small (few agents, sequential stages) \
                and match each stage's model to its size.";
    Ok(Decision::Allow(Some(Out::PreContext(
        call.tag(Level::Warn, body)?,
    ))))
}

/// python `stage2_deny`: 2단계. 전체 지시는 (호출한 쪽, 회차, away 선언)마다 한 번, 이후는 짧게.
fn stage2_deny(call: &Call, st: &mut Dict, verdict: &Verdict, kind: &str) -> Result<Out> {
    bump_queued(st)?;
    log(
        st,
        "stage2-deny",
        vec![("kind", Value::Str(kind.to_owned()))],
    )?;
    let key = format!("{}:{}", call.epoch(), text(away_dict(st)?.get("since")));
    let why = verdict.why.as_deref().unwrap_or("None");

    // The full instruction once, then a short reminder
    let body = if note_set(st, &format!("stage2:{}", call.who()), &key)? {
        format!(
            "halt: the away budget's stage 2 is reached ({why}); new subagents and workflows are refused until the user returns. \
             This call did not run. Do not retry or work around it. Write the current state to the progress file \
             (or the session notes): what is done, what is running, what is next, and what needs the user's decision. \
             Then wait for the user; the session itself is not stopped, so you may finish the small step in hand but start no new large work."
        )
    } else {
        "halt: away budget stage 2 still in effect; no new subagents or workflows. \
         Keep the progress file current and wait for the user."
            .to_owned()
    };
    Ok(Out::Deny(call.tag(Level::Action, &body)?))
}

fn away_dict(st: &mut Dict) -> Result<&mut Dict> {
    dict_mut(st, "away")
}

// away["queued"] = away.get("queued", 0) + 1
fn bump_queued(st: &mut Dict) -> Result<()> {
    let away = away_dict(st)?;
    let queued = num_or(away, "queued", Num::Int(0))?.plus(Num::Int(1))?;
    away.insert("queued", queued.value());
    Ok(())
}

/// python `if st["notes"].get(name) != key: st["notes"][name] = key`: 새로 적었으면 참.
pub fn note_set(st: &mut Dict, name: &str, key: &str) -> Result<bool> {
    let notes = dict_mut(st, "notes")?;
    if notes.get(name).and_then(Value::as_str) == Some(key) {
        return Ok(false);
    }
    notes.insert(name, Value::Str(key.to_owned()));
    Ok(true)
}

// st["reserved"][tool_use_id or f"anon-{now}"] = entry
fn reserve(call: &Call, st: &mut Dict, entry: Dict) -> Result<()> {
    let key = match call.truthy("tool_use_id") {
        None => format!("anon-{}", Num::Float(call.now).text()),
        Some(Value::Str(id)) => id.clone(),
        Some(Value::List(_) | Value::Dict(_)) => {
            return Err(Stop::Raises("an unhashable tool_use_id"));
        }
        Some(_) => return Err(Stop::Unported("a tool_use_id that is not text")),
    };
    dict_mut(st, "reserved")?.insert(key, Value::Dict(entry));
    Ok(())
}
