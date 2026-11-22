//! Stop, SubagentStop 에서 방치된 백그라운드 작업을 판정해 알림을 쌓는다(python `evaluate`).
//!
//! 나이는 이 훅이 처음 본 때부터 센다(입력에 시작 시각이 없다). 판정(분, 환경 변수로 바꾼다):
//! - 멈춤(stalled): 진척 없이 `HARNESS_Q_STALE_IDLE_MIN`(15) 이상이고 나이가 `HARNESS_Q_STALE_AGE_MIN`(30) 이상.
//! - 오래 실행(long): 멈춤이 아니고 나이가 `HARNESS_Q_STALE_LONG_MIN`(120) 이상.
//!
//! (세션, 작업, 상태)마다 한 번. 모델 문구는 `st["model"]`, 사용자 줄은 `st["user"]` 에 쌓는다.

use harness_hook::HookEnv;
use harness_hook::py::num::{floor_div, parse_float};
use harness_hook::py::repr::{str_value, truthy_str};
use harness_hook::py::value::{Dict, Value};

use super::signal::{Signal, signal};
use crate::num::Num;
use crate::pyval::py_eq;
use crate::stop::{Result, Stop};

const FINISHED_HINT: &str = "If it belongs to work that already finished or loops waiting on a condition, look at its command and output \
                             and stop it (TaskStop) or tell the user";

/// 문턱(초).
struct Limits {
    idle: Num,
    age: Num,
    long: Num,
}

/// 작업 하나에 새로 낼 알림.
enum State {
    Stalled,
    Long,
}

impl State {
    fn name(&self) -> &'static str {
        match self {
            State::Stalled => "stalled",
            State::Long => "long",
        }
    }
}

/// python `evaluate(st, data, now)`: 상태를 고치고 새 알림(모델 문구, 사용자 줄)을 쌓는다.
pub fn evaluate(
    hook: &HookEnv,
    st: &mut Dict,
    input: &Dict,
    now: f64,
    tempdir: &str,
) -> Result<()> {
    let Some(Value::List(background)) = input.get("background_tasks") else {
        return Ok(());
    };
    let limits = Limits {
        idle: minutes_env(hook, "HARNESS_Q_STALE_IDLE_MIN", 15),
        age: minutes_env(hook, "HARNESS_Q_STALE_AGE_MIN", 30),
        long: minutes_env(hook, "HARNESS_Q_STALE_LONG_MIN", 120),
    };

    // Running tasks other than this agent itself
    let live = running(background, input.get("agent_id"));
    let ids: Vec<&str> = live
        .iter()
        .map(|t| t.get("id").and_then(Value::as_str))
        .collect::<Option<_>>()
        .ok_or(Stop::Unported("a task id that is not text"))?;

    // Forget tasks that are gone, then judge each live one
    let mut model = Vec::new();
    let mut user = Vec::new();
    let tasks = tasks_of(st, live.is_empty())?;
    let Some(tasks) = tasks else {
        return Ok(());
    };
    let gone: Vec<String> = tasks
        .iter()
        .map(|(k, _)| k.to_owned())
        .filter(|k| !ids.contains(&k.as_str()))
        .collect();
    for key in gone {
        tasks.remove(&key);
    }
    for (task, id) in live.iter().zip(&ids) {
        judge(
            hook, tasks, task, id, input, now, tempdir, &limits, &mut model, &mut user,
        )?;
    }

    // The queues
    push_all(st, "model", model)?;
    push_all(st, "user", user)
}

/// python 의 live 목록: dict 이고 running 이며 monitor 가 아니고, id 가 참이며 자기 agent_id 가 아닌 작업.
fn running<'a>(background: &'a [Value], me: Option<&Value>) -> Vec<&'a Dict> {
    let null = Value::Null;
    let me = me.unwrap_or(&null);
    background
        .iter()
        .filter_map(Value::as_dict)
        .filter(|t| t.get("status").and_then(Value::as_str) == Some("running"))
        .filter(|t| t.get("type").and_then(Value::as_str) != Some("monitor"))
        .filter(|t| t.get("id").is_some_and(|id| id.truthy() && !py_eq(id, me)))
        .collect()
}

// st.setdefault("tasks", {}). dict 가 아닌 값은 비어 있고 할 일이 없을 때만 python 이 지나간다(`None` 이면 할 일 없음)
fn tasks_of(st: &mut Dict, no_live: bool) -> Result<Option<&mut Dict>> {
    let tasks = st.setdefault("tasks", Value::Dict(Dict::new()));
    match tasks {
        Value::Dict(d) => Ok(Some(d)),
        Value::List(l) if l.is_empty() && no_live => Ok(None),
        Value::Str(s) if s.is_empty() && no_live => Ok(None),
        _ => Err(Stop::Raises("tasks is not a dict")),
    }
}

// 작업 하나: 진척 신호를 갱신하고, 새로 닿은 상태면 문구를 쌓는다
#[allow(clippy::too_many_arguments)]
fn judge(
    hook: &HookEnv,
    tasks: &mut Dict,
    task: &Dict,
    id: &str,
    input: &Dict,
    now: f64,
    tempdir: &str,
    limits: &Limits,
    model: &mut Vec<Value>,
    user: &mut Vec<Value>,
) -> Result<()> {
    let fresh = Dict::from_pairs(vec![
        ("first".to_owned(), Value::Float(now)),
        ("prog".to_owned(), Value::Float(now)),
        ("sig".to_owned(), Value::Null),
        ("done".to_owned(), Value::List(Vec::new())),
    ]);
    let Value::Dict(rec) = tasks.setdefault(id, Value::Dict(fresh)) else {
        return Err(Stop::Raises("rec.get on a task record that is not a dict"));
    };
    let sig = signal(hook, task, input, tempdir)?;

    // Progress: a new signal moves the progress time
    let prev = rec.get("sig").cloned().unwrap_or(Value::Null);
    if let Some(sig) = &sig
        && (prev == Value::Null || moved(sig, &prev)?)
    {
        let prog = if prev == Value::Null {
            if sig.mtime < now { sig.mtime } else { now }
        } else {
            now
        };
        rec.insert("prog", Value::Float(prog));
    }
    rec.insert("sig", sig.as_ref().map_or(Value::Null, Signal::value));

    // Which state the task is in now
    let age = Num::Float(now).minus(Num::need(rec.get("first").ok_or(KEY)?)?)?;
    let idle = Num::Float(now).minus(Num::need(rec.get("prog").ok_or(KEY)?)?)?;
    let state = if sig.is_some() && idle.ge(limits.idle) && age.ge(limits.age) {
        State::Stalled
    } else if age.ge(limits.long) {
        State::Long
    } else {
        return Ok(());
    };
    if !mark_done(rec, state.name())? {
        return Ok(());
    }

    // The model line and the user line
    let (text, line) = texts(&state, task, sig.as_ref(), idle, age)?;
    model.push(Value::List(vec![
        Value::Str("warn".to_owned()),
        Value::Str(text),
    ]));
    user.push(Value::Str(line));
    Ok(())
}

const KEY: Stop = Stop::Raises("KeyError on a task record");

// 새 상태의 (모델 문구, 사용자 줄)
fn texts(
    state: &State,
    task: &Dict,
    sig: Option<&Signal>,
    idle: Num,
    age: Num,
) -> Result<(String, String)> {
    let label = label(task);
    let out = match sig.and_then(|s| s.path.as_deref()) {
        Some(path) if !path.is_empty() => format!(" Output file: {path}."),
        _ => String::new(),
    };
    Ok(match state {
        State::Stalled => {
            let (idle_min, age_min) = (minutes(idle)?, minutes(age)?);
            (
                format!(
                    "Background {label} shows no output or transcript change for about {idle_min} min (watched for {age_min} min). \
                     It may be stalled or waiting on something; this is a guess from file timestamps.{out} {FINISHED_HINT}; \
                     otherwise check its output or ask the user before stopping it."
                ),
                format!(
                    "백그라운드 작업 {label} 이(가) 약 {idle_min}분째 출력 변화가 없습니다. 멈췄거나 대기 중일 수 있습니다."
                ),
            )
        }
        State::Long => {
            let age_min = minutes(age)?;
            let progress = if sig.is_some() {
                " and is still showing progress"
            } else {
                ""
            };
            let progress_ko = if sig.is_some() {
                "(진척은 있음)"
            } else {
                ""
            };
            (
                format!(
                    "Background {label} has been running for about {age_min} min{progress}.{out} {FINISHED_HINT}; \
                     otherwise mention it to the user in one line."
                ),
                format!(
                    "백그라운드 작업 {label} 이(가) {age_min}분 넘게 실행 중입니다{progress_ko}."
                ),
            )
        }
    })
}

// python `sig[:2] != prev[:2]`(prev 는 None 이 아니다). 글이면 목록과 늘 다르고, 잘라 볼 수 없는 값은 TypeError
fn moved(sig: &Signal, prev: &Value) -> Result<bool> {
    let now = [Value::Int(i128::from(sig.size)), Value::Float(sig.mtime)];
    match prev {
        Value::List(items) => {
            let head: Vec<Value> = items.iter().take(2).cloned().collect();
            Ok(!py_eq(&Value::List(now.to_vec()), &Value::List(head)))
        }
        Value::Str(_) => Ok(true),
        _ => Err(Stop::Raises("slicing a sig that is not a list")),
    }
}

// python `if state in rec["done"]: continue` 뒤 `rec["done"].append(state)`. 새로 더했으면 참
fn mark_done(rec: &mut Dict, state: &str) -> Result<bool> {
    match rec.get_mut("done") {
        Some(Value::List(done)) => {
            if done.iter().any(|d| d.as_str() == Some(state)) {
                return Ok(false);
            }
            done.push(Value::Str(state.to_owned()));
            Ok(true)
        }
        Some(Value::Str(done)) if done.contains(state) => Ok(false),
        Some(Value::Dict(done)) if done.get(state).is_some() => Ok(false),
        Some(_) => Err(Stop::Raises("done is not a list")),
        None => Err(KEY),
    }
}

// st[key] 목록에 차례로 더한다(python `st["model"].append(...)`)
fn push_all(st: &mut Dict, key: &str, items: Vec<Value>) -> Result<()> {
    if items.is_empty() {
        return Ok(());
    }
    match st.get_mut(key) {
        Some(Value::List(list)) => {
            list.extend(items);
            Ok(())
        }
        _ => Err(Stop::Raises("the message queue is not a list")),
    }
}

/// python `label(task)`: `<type> "<설명 60자>" (id <id 12자>)`.
fn label(task: &Dict) -> String {
    let desc = task
        .get("description")
        .filter(|v| v.truthy())
        .or_else(|| task.get("name"));
    let desc: String = truthy_str(desc).chars().take(60).collect();
    let kind = task
        .get("type")
        .map_or_else(|| "task".to_owned(), str_value);
    let id: String = task
        .get("id")
        .map_or_else(String::new, str_value)
        .chars()
        .take(12)
        .collect();
    format!("{kind} \"{desc}\" (id {id})")
}

/// python `max(1, int(sec // 60))`. NaN 과 무한대는 python `int()` 이 예외를 낸다.
fn minutes(sec: Num) -> Result<i128> {
    let whole = match sec {
        Num::Int(n) => n.div_euclid(60),
        Num::Float(f) => {
            let q = floor_div(f, 60.0);
            if !q.is_finite() || q.abs() >= 1.7e38 {
                return Err(Stop::Raises("int() of a non-finite float"));
            }
            q as i128
        }
    };
    Ok(whole.max(1))
}

// python `float(os.environ.get(name, default)) * 60`, 읽지 못하면 `default * 60`(int)
fn minutes_env(hook: &HookEnv, name: &str, default: i128) -> Num {
    match hook.var(name) {
        None => Num::Float(default as f64 * 60.0),
        Some(text) => match parse_float(&text) {
            Some(f) => Num::Float(f * 60.0),
            None => Num::Int(default * 60),
        },
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 분은 내림이고 1 보다 작지 않다.
    #[test]
    fn minutes_floor_at_one() {
        assert_eq!(minutes(Num::Float(59.0)).unwrap(), 1);
        assert_eq!(minutes(Num::Float(3601.0)).unwrap(), 60);
        assert_eq!(minutes(Num::Float(-30.0)).unwrap(), 1);
        assert!(minutes(Num::Float(f64::NAN)).is_err());
    }

    /// 설명이 비면 name, type 이 없으면 task, id 는 12자까지.
    #[test]
    fn label_like_python() {
        let task = Dict::from_pairs(vec![
            ("id".to_owned(), Value::Str("abcdefghijklmnop".into())),
            ("description".to_owned(), Value::Str(String::new())),
            ("name".to_owned(), Value::Str("watch".into())),
        ]);
        assert_eq!(label(&task), "task \"watch\" (id abcdefghijkl)");
        let typed = Dict::from_pairs(vec![("type".to_owned(), Value::Null)]);
        assert_eq!(label(&typed), "None \"\" (id )");
    }
}
