//! 원장 셈(python `subagent_ledger` 의 `log`, `live`, `by_family`, `account_main`, `account_agent`, `sweep`, `total_usd`).
//!
//! 원장 값은 python 이 쓴 그대로의 [`Dict`] 다. python 이 그 값으로 하는 일(`d[key]`, `d.get(key)`, 셈)이 예외로 끝나는 꼴이면
//! [`Stop::Raises`] 이고, 글이 아닌 키처럼 python 은 받지만 옮기지 않은 꼴은 [`Stop::Unported`] 다.

use harness_hook::py::fs::{FsError, getsize, read_bytes, stat};
use harness_hook::py::json_load::{self, Decode};
use harness_hook::py::path::{join, splitext};
use harness_hook::py::repr::str_value;
use harness_hook::py::value::{Dict, Value};

use super::config::Cfg;
use super::spend::{ORDER, Spend, scan, tail_model};
use crate::num::{Num, py_max, py_sum};
use crate::pyval::{now as clock, py_eq};
use crate::stop::{Result, Stop};

/// 원장에 둘 에이전트 기록의 수. 넘으면 오래된 것부터 [`AGENTS_DROP`] 개를 지운다(합계는 spent 에 남는다).
const AGENTS_KEEP: usize = 500;
const AGENTS_DROP: usize = 100;
/// SubagentStop 뒤에도 이만큼(초) 트랜스크립트를 이어서 읽는다(마지막 응답이 늦게 쓰인다).
const SWEEP_WINDOW: f64 = 600.0;

/// python `d[key]` 를 dict 로 쓰는 자리: 없으면 KeyError, dict 가 아니면 그 셈에서 TypeError.
pub fn dict_mut<'a>(d: &'a mut Dict, key: &str) -> Result<&'a mut Dict> {
    match d.get_mut(key) {
        Some(Value::Dict(inner)) => Ok(inner),
        Some(_) => Err(Stop::Raises("a ledger field that is not a dict")),
        None => Err(Stop::Raises("KeyError on a ledger field")),
    }
}

/// python `d.get(key, default)` 를 수로 쓰는 자리.
pub fn num_or(d: &Dict, key: &str, default: Num) -> Result<Num> {
    d.get(key).map_or(Ok(default), Num::need)
}

/// 원장 키로 쓰는 값. 글이 아닌 키는 python 이 쓸 때 글로 바꿔 다음에 다른 키가 되므로 옮기지 않았다.
pub fn key_of(value: &Value) -> Result<&str> {
    match value {
        Value::Str(s) => Ok(s),
        Value::List(_) | Value::Dict(_) => Err(Stop::Raises("an unhashable ledger key")),
        _ => Err(Stop::Unported("a ledger key that is not text")),
    }
}

/// python `log(st, event, **kw)`: 사건 줄 `{**kw, "t": round(time.time(), 1), "k": event}`.
pub fn log(st: &mut Dict, event: &str, fields: Vec<(&str, Value)>) -> Result<()> {
    let mut entry: Vec<(String, Value)> =
        fields.into_iter().map(|(k, v)| (k.to_owned(), v)).collect();
    entry.push(("t".to_owned(), Num::Float(clock()).round(1).value()));
    entry.push(("k".to_owned(), Value::Str(event.to_owned())));
    match st.get_mut("log") {
        Some(Value::List(lines)) => {
            lines.push(Value::Dict(Dict::from_pairs(entry)));
            Ok(())
        }
        _ => Err(Stop::Raises("log.append on a log that is not a list")),
    }
}

/// python `subagent_dir(st)`: 메인 트랜스크립트 옆의 `<sid>/subagents`, 트랜스크립트를 모르면 `None`.
pub fn subagent_dir(st: &Dict) -> Result<Option<String>> {
    match st.get("tp").filter(|v| v.truthy()) {
        None => Ok(None),
        Some(Value::Str(tp)) => Ok(Some(join(splitext(tp).0, "subagents"))),
        Some(_) => Err(Stop::Raises("os.path.splitext of a value that is not text")),
    }
}

/// python `_meta(st, agent_id)`: `agent-<id>.meta.json` 의 값. 읽지 못하면 `None`.
pub fn meta(st: &Dict, agent_id: &str) -> Result<Option<Value>> {
    let Some(dir) = subagent_dir(st)? else {
        return Ok(None);
    };
    let path = join(&dir, &format!("agent-{agent_id}.meta.json"));
    Ok(read_bytes(&path)
        .ok()
        .and_then(|bytes| json_load::from_bytes(&bytes, Decode::Strict).ok()))
}

/// python `meta.get(key)` 를 하는 자리(참인 값이 dict 가 아니면 AttributeError).
pub fn meta_get<'a>(meta: Option<&'a Value>, key: &str) -> Result<Option<&'a Value>> {
    match meta.filter(|v| v.truthy()) {
        None => Ok(None),
        Some(Value::Dict(d)) => Ok(d.get(key)),
        Some(_) => Err(Stop::Raises("meta.get on a value that is not a dict")),
    }
}

/// [`live`] 의 항목 하나: 실행 중이거나 예약된 에이전트(python `dict(r, id=k)`).
pub type Item = Dict;

/// python `live(st, cfg, now, background)`: 실행 중과 예약 목록을 정리해 돌려준다(복구 포함, 원장을 고친다).
///
/// 복구 근거(위에서부터): background_tasks(백그라운드만), meta.json 의 finished, 트랜스크립트가 STALE 분 넘게 멈춤, 예약 TTL.
pub fn live(st: &mut Dict, cfg: &Cfg, now: f64, background: Option<&[Value]>) -> Result<Vec<Item>> {
    let stale = cfg.float("HARNESS_SLOTS_STALE_MIN").times(Num::Int(60))?;
    let ttl = cfg.float("HARNESS_SLOTS_RESERVE_SEC");
    let now_n = Num::Float(now);

    // Expired reservations
    for (key, r) in entries(dict_mut(st, "reserved")?)? {
        if now_n.minus(num_or(&r, "t", Num::Int(0))?)?.gt(ttl) {
            dict_mut(st, "reserved")?.remove(&key);
            log(st, "reserve-expired", vec![("id", Value::Str(key))])?;
        }
    }

    // Running agents that have finished
    let bg_ids = match background {
        None => None,
        Some(tasks) => Some(subagent_ids(tasks)?),
    };
    let dir = subagent_dir(st)?;
    for (aid, r) in entries(dict_mut(st, "running")?)? {
        if let Some(why) = finished(
            st,
            &aid,
            &r,
            bg_ids.as_deref(),
            dir.as_deref(),
            now_n,
            stale,
        )? {
            dict_mut(st, "running")?.remove(&aid);
            log(
                st,
                "recovered",
                vec![("id", Value::Str(aid)), ("why", Value::Str(why.to_owned()))],
            )?;
        }
    }

    // Running first, then reserved
    let mut items = Vec::new();
    for (key, r) in entries(dict_mut(st, "running")?)? {
        items.push(with_id(r, key, false));
    }
    for (key, r) in entries(dict_mut(st, "reserved")?)? {
        items.push(with_id(r, key, true));
    }
    Ok(items)
}

// python list(d.items()) 의 사본. 값은 dict 여야 r.get 을 할 수 있다
fn entries(d: &Dict) -> Result<Vec<(String, Dict)>> {
    d.iter()
        .map(|(k, v)| match v {
            Value::Dict(r) => Ok((k.to_owned(), r.clone())),
            _ => Err(Stop::Raises("r.get on a ledger entry that is not a dict")),
        })
        .collect()
}

fn with_id(mut r: Dict, key: String, reserved: bool) -> Item {
    r.insert("id", Value::Str(key));
    if reserved {
        r.insert("reserved", Value::Bool(true));
    }
    r
}

// python {t.get("id") for t in background if t.get("type") == "subagent"}
fn subagent_ids(tasks: &[Value]) -> Result<Vec<Value>> {
    let mut ids = Vec::new();
    for task in tasks {
        let Value::Dict(task) = task else {
            return Err(Stop::Raises(
                "t.get on a background task that is not a dict",
            ));
        };
        if task.get("type").and_then(Value::as_str) != Some("subagent") {
            continue;
        }
        let id = task.get("id").cloned().unwrap_or(Value::Null);
        if matches!(id, Value::List(_) | Value::Dict(_)) {
            return Err(Stop::Raises("an unhashable background task id"));
        }
        ids.push(id);
    }
    Ok(ids)
}

// 실행 중 항목 하나가 끝났다고 볼 까닭
#[allow(clippy::too_many_arguments)]
fn finished(
    st: &Dict,
    aid: &str,
    r: &Dict,
    bg_ids: Option<&[Value]>,
    dir: Option<&str>,
    now: Num,
    stale: Num,
) -> Result<Option<&'static str>> {
    // Background agents missing from background_tasks
    let is_bg = r.get("bg").is_some_and(Value::truthy);
    let id = Value::Str(aid.to_owned());
    if let Some(ids) = bg_ids
        && is_bg
        && !ids.iter().any(|x| py_eq(x, &id))
    {
        return Ok(Some("not-in-background_tasks"));
    }

    // meta.json says finished
    let meta = meta(st, aid)?;
    if meta_get(meta.as_ref(), "finished")?.is_some_and(Value::truthy) {
        return Ok(Some("meta-finished"));
    }

    // Transcript quiet past the stale limit
    let started = num_or(r, "t", Num::Float(now.f64()))?;
    let last = match dir {
        None => started,
        Some(dir) => match stat(&join(dir, &format!("agent-{aid}.jsonl"))) {
            Ok(s) => Num::Float(mtime(s.mtime_ns)),
            Err(FsError::Os(_)) => started,
            Err(FsError::Value) => return Err(Stop::Raises("os.path.getmtime of a path with NUL")),
        },
    };
    let quiet = now.minus(py_max(last, num_or(r, "t", Num::Int(0))?))?;
    Ok(quiet.gt(stale).then_some("stale"))
}

/// python `st_mtime`(CPython `sec + nsec * 1e-9`).
pub fn mtime(mtime_ns: i128) -> f64 {
    let sec = mtime_ns.div_euclid(1_000_000_000);
    let nsec = mtime_ns.rem_euclid(1_000_000_000);
    sec as f64 + nsec as f64 * 1e-9
}

/// python `by_family(items)`: 계열별 수(비싼 순, 모르는 계열은 `?`, 그 밖의 값은 세지 않는다).
pub fn by_family(items: &[Item]) -> Result<Vec<(&'static str, usize)>> {
    let mut counts: Vec<(&'static str, usize)> =
        ORDER.iter().chain(&["?"]).map(|f| (*f, 0)).collect();
    for r in items {
        let fam = r.get("fam").filter(|v| v.truthy());
        let name = match fam {
            None => "?",
            Some(Value::Str(f)) => f,
            Some(Value::List(_) | Value::Dict(_)) => return Err(Stop::Raises("an unhashable fam")),
            Some(_) => continue,
        };
        if let Some(slot) = counts.iter_mut().find(|(f, _)| *f == name) {
            slot.1 += 1;
        }
    }
    Ok(counts.into_iter().filter(|(_, n)| *n > 0).collect())
}

/// python `fams_text(L, items)`: `opus 2, sonnet 1`, 없으면 `unknown models`.
pub fn fams_text(items: &[Item]) -> Result<String> {
    let parts: Vec<String> = by_family(items)?
        .into_iter()
        .map(|(f, n)| format!("{f} {n}"))
        .collect();
    Ok(if parts.is_empty() {
        "unknown models".to_owned()
    } else {
        parts.join(", ")
    })
}

/// python `add_spend(bucket, by_model)`.
fn add_spend(bucket: &mut Dict, by_model: &[(String, Spend)]) -> Result<()> {
    for (model, spend) in by_model {
        let fresh = Dict::from_pairs(vec![
            ("usd".to_owned(), Value::Float(0.0)),
            ("tok".to_owned(), Value::Int(0)),
        ]);
        let Value::Dict(entry) = bucket.setdefault(model, Value::Dict(fresh)) else {
            return Err(Stop::Raises("a spend entry that is not a dict"));
        };
        for (key, add) in [("usd", spend.usd), ("tok", spend.tok)] {
            let sum = Num::need(
                entry
                    .get(key)
                    .ok_or(Stop::Raises("KeyError on a spend entry"))?,
            )?
            .plus(add)?;
            entry.insert(key, sum.value());
        }
    }
    Ok(())
}

/// python `total_usd(st)`: 메인과 서브의 쓴 값 합(python `sum`, 시작 0).
pub fn total_usd(st: &Dict) -> Result<Num> {
    let empty = Dict::new();
    let spent = match st.get("spent") {
        None => &empty,
        Some(Value::Dict(d)) => d,
        Some(_) => return Err(Stop::Raises("spent.get on a non-dict")),
    };
    let mut values = Vec::new();
    for bucket in ["main", "sub"] {
        let entries = match spent.get(bucket) {
            None => continue,
            Some(Value::Dict(d)) => d,
            Some(_) => {
                return Err(Stop::Raises(
                    "values() of a spend bucket that is not a dict",
                ));
            }
        };
        for (_, entry) in entries.iter() {
            let Value::Dict(entry) = entry else {
                return Err(Stop::Raises(
                    "e[\"usd\"] on a spend entry that is not a dict",
                ));
            };
            values.push(Num::need(
                entry.get("usd").ok_or(Stop::Raises("KeyError on usd"))?,
            )?);
        }
    }
    py_sum(values)
}

/// python `account_main(st, transcript_path)`: 메인 트랜스크립트 사용량을 이어서 더한다. 처음 보면 끝에서 시작한다.
pub fn account_main(st: &mut Dict, transcript: Option<&Value>) -> Result<()> {
    let Some(tp) = transcript.filter(|v| v.truthy()) else {
        return Ok(());
    };
    st.insert("tp", tp.clone());
    let Value::Str(path) = tp else {
        return Err(Stop::Unported("a transcript path that is not text"));
    };
    let main = dict_mut(st, "main")?;

    // First sight: start at the end of the transcript
    if main.get("off").is_none() {
        let size = match getsize(path) {
            Ok(size) => i128::from(size),
            Err(FsError::Os(_)) => 0,
            Err(FsError::Value) => return Err(Stop::Raises("getsize of a path with NUL")),
        };
        main.insert("off", Value::Int(size));
        main.insert("since", Value::Float(clock()));
        main.insert("model", tail_model(path)?.map_or(Value::Null, Value::Str));
        return Ok(());
    }

    // Later: add what was written since
    let scanned = scan(
        path,
        main.get("off").unwrap_or(&Value::Null),
        main.get("recent"),
    )?;
    main.insert("off", scanned.offset);
    main.insert("recent", Value::List(scanned.recent));
    let spent = dict_mut(dict_mut(st, "spent")?, "main")?;
    add_spend(spent, &scanned.by_model)?;
    if let Some(model) = scanned.last_model {
        dict_mut(st, "main")?.insert("model", Value::Str(model));
    }
    Ok(())
}

/// [`account_agent`] 가 고친 에이전트 기록.
pub struct Accounted {
    /// 기록의 `usd` 값.
    pub usd: Value,
    /// 기록이 아직 원장에 있나(500 개를 넘어 지운 것이면 거짓이고, python 은 떼어진 dict 를 고친다).
    pub kept: bool,
}

/// python `account_agent(st, agent_id, path)`: 서브에이전트 트랜스크립트를 이어서 더한다(다시 멈춰도 두 번 세지 않는다).
pub fn account_agent(
    st: &mut Dict,
    agent_id: &str,
    path: Option<&Value>,
) -> Result<Option<Accounted>> {
    let path = match path.filter(|v| v.truthy()) {
        Some(p) => p.clone(),
        None => match subagent_dir(st)? {
            Some(dir) => Value::Str(join(&dir, &format!("agent-{agent_id}.jsonl"))),
            None => return Ok(None),
        },
    };
    let Value::Str(path_text) = &path else {
        return Err(Stop::Unported("an agent transcript path that is not text"));
    };

    // The agent record, then what was written since
    let fresh = Dict::from_pairs(vec![
        ("off".to_owned(), Value::Int(0)),
        ("usd".to_owned(), Value::Float(0.0)),
    ]);
    let Value::Dict(agent) = dict_mut(st, "agents")?.setdefault(agent_id, Value::Dict(fresh))
    else {
        return Err(Stop::Raises("a.get on an agent record that is not a dict"));
    };
    agent.insert("path", path.clone());
    let scanned = scan(
        path_text,
        agent.get("off").ok_or(Stop::Raises("KeyError on off"))?,
        agent.get("recent"),
    )?;
    agent.insert("off", scanned.offset);
    agent.insert("recent", Value::List(scanned.recent));
    add_spend(dict_mut(dict_mut(st, "spent")?, "sub")?, &scanned.by_model)?;

    // The agent's own total and model
    let Value::Dict(agent) = dict_mut(st, "agents")?
        .get_mut(agent_id)
        .expect("set above")
    else {
        unreachable!("set above as a dict");
    };
    let added = py_sum(scanned.by_model.iter().map(|(_, s)| s.usd))?;
    let usd = Num::need(agent.get("usd").ok_or(Stop::Raises("KeyError on usd"))?)?.plus(added)?;
    agent.insert("usd", usd.value());
    if let Some(model) = scanned.last_model {
        agent.insert("model", Value::Str(model));
    }
    let usd = agent.get("usd").cloned().unwrap_or(Value::Null);

    // Old records go first once there are too many
    let agents = dict_mut(st, "agents")?;
    if agents.len() > AGENTS_KEEP {
        let old: Vec<String> = agents
            .iter()
            .take(AGENTS_DROP)
            .map(|(k, _)| k.to_owned())
            .collect();
        for key in old {
            agents.remove(&key);
        }
    }
    let kept = agents.get(agent_id).is_some();
    Ok(Some(Accounted { usd, kept }))
}

/// python `sweep(st, now)`: 최근 [`SWEEP_WINDOW`] 초 안에 멈춘 에이전트의 트랜스크립트를 이어서 읽는다.
pub fn sweep(st: &mut Dict, now: f64) -> Result<()> {
    for (aid, a) in entries(dict_mut(st, "agents")?)? {
        let Some(stopped) = a.get("stopped").filter(|v| v.truthy()) else {
            continue;
        };
        let recent = Num::Float(now)
            .minus(Num::need(stopped)?)?
            .lt(Num::Float(SWEEP_WINDOW));
        let path = a.get("path").filter(|v| v.truthy());
        if recent && let Some(path) = path {
            account_agent(st, &aid, Some(path))?;
        }
    }
    Ok(())
}

/// python `f"{v}"` 를 원장 키 글에 쓰는 자리.
pub fn text(v: Option<&Value>) -> String {
    v.map_or_else(|| "None".to_owned(), str_value)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 계열 수는 비싼 순이고, 계열이 없으면 `?` 로 센다.
    #[test]
    fn families_in_price_order() {
        let item = |fam: Option<&str>| {
            let mut d = Dict::new();
            if let Some(f) = fam {
                d.insert("fam", Value::Str(f.into()));
            }
            d
        };
        let items = [
            item(Some("sonnet")),
            item(Some("opus")),
            item(None),
            item(Some("odd")),
        ];
        assert_eq!(fams_text(&items).unwrap(), "opus 1, sonnet 1, ? 1");
        assert_eq!(fams_text(&[]).unwrap(), "unknown models");
    }

    /// 쓴 값이 없으면 int 0, 있으면 float 보정 합이다.
    #[test]
    fn total_like_python_sum() {
        assert_eq!(
            total_usd(&super::super::store::blank()).unwrap(),
            Num::Int(0)
        );
        let st = harness_hook::py::json_load::loads(
            r#"{"spent": {"main": {"m": {"usd": 0.1, "tok": 1}}, "sub": {"a": {"usd": 0.2}, "b": {"usd": 0.3}}}}"#,
        )
        .unwrap();
        let total = total_usd(st.as_dict().unwrap()).unwrap();
        assert_eq!(total, Num::Float(0.6));
    }
}
