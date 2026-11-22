//! away 예산 판정(python `away_eval`, `away_check`). 기준은 `/q:away` 이후 증가분이다.
//!
//! 단위는 USD, 띄운 에이전트 수, 한도 %(statusline 이 쓴 `<sid>.limits.json`) 가운데 하나다. 1단계는 예산 도달,
//! 2단계는 예산의 `HARNESS_AWAY_STAGE2_MULT` 배. 한도 값이 오래됐으면 USD 가드로 메운다. 훅은 창 상태를 원장에 고쳐 둔다.

use harness_hook::py::repr::str_value;
use harness_hook::py::value::{Dict, Value};

use super::config::Cfg;
use super::ledger::{log, num_or, total_usd};
use crate::num::{Num, py_max, py_min};
use crate::stop::{Result, Stop};

/// 판정 결과 가운데 훅이 쓰는 것.
#[derive(Clone, Debug, PartialEq)]
pub struct Verdict {
    /// 0, 1(예산 도달), 2(2단계).
    pub level: u8,
    /// 가장 높은 단계의 까닭.
    pub why: Option<String>,
}

impl Verdict {
    // python mark(level, why): 더 높은 단계만 남긴다
    fn mark(&mut self, level: u8, why: String) {
        if level > self.level {
            self.level = level;
            self.why = Some(why);
        }
    }
}

/// python `st.get("away")` 가 참이고 `on` 이 참인가(참인 값이 dict 가 아니면 `.get` 에서 예외).
pub fn is_on(st: &Dict) -> Result<bool> {
    match st.get("away").filter(|v| v.truthy()) {
        None => Ok(false),
        Some(Value::Dict(away)) => Ok(away.get("on").is_some_and(Value::truthy)),
        Some(_) => Err(Stop::Raises("away.get on a value that is not a dict")),
    }
}

/// python `away_check(st, cfg, lim, now)`: away 중이면 판정하고(창 상태 갱신 포함) 1, 2단계 도달 시각을 처음 한 번만 적는다.
pub fn check(st: &mut Dict, cfg: &Cfg, limits: Option<&Dict>, now: f64) -> Result<Option<Verdict>> {
    if !is_on(st)? {
        return Ok(None);
    }
    let verdict = evaluate(st, cfg, limits, now)?;

    // First time over each stage
    for (level, key, event) in [(1, "over_at", "over-budget"), (2, "over2_at", "stage2")] {
        if verdict.level < level {
            continue;
        }
        let away = away_mut(st)?;
        if away.get(key).is_some_and(Value::truthy) {
            continue;
        }
        away.insert(key, Value::Float(now));
        let why = verdict.why.clone().map_or(Value::Null, Value::Str);
        log(st, event, vec![("why", why)])?;
    }
    Ok(Some(verdict))
}

fn away_mut(st: &mut Dict) -> Result<&mut Dict> {
    match st.get_mut("away") {
        Some(Value::Dict(away)) => Ok(away),
        _ => Err(Stop::Raises("away is not a dict")),
    }
}

/// python `away_eval(st, lim, now, persist=True, cfg)`.
fn evaluate(st: &mut Dict, cfg: &Cfg, limits: Option<&Dict>, now: f64) -> Result<Verdict> {
    let mult = cfg.float("HARNESS_AWAY_STAGE2_MULT");
    let total = total_usd(st)?;
    let spawned_now = num_or(st, "spawned", Num::Int(0))?;
    let away = away_mut(st)?;
    let spent = total.minus(num_or(away, "base_usd", Num::Float(0.0))?)?;
    let spawned = spawned_now.minus(num_or(away, "base_spawned", Num::Int(0))?)?;
    let mut verdict = Verdict {
        level: 0,
        why: None,
    };

    let set = |key: &str| away.get(key).filter(|v| **v != Value::Null).cloned();
    if let Some(budget) = set("budget_usd") {
        usd_budget(&mut verdict, Num::need(&budget)?, mult, spent)?;
    } else if let Some(budget) = set("budget_agents") {
        agent_budget(&mut verdict, &budget, mult, spawned)?;
    } else if let Some(budget) = set("budget_pct") {
        let fresh = match limits {
            Some(lim) => Num::Float(now)
                .minus(num_or(lim, "t", Num::Int(0))?)?
                .compare(
                    cfg.float("HARNESS_AWAY_LIMITS_STALE_MIN")
                        .times(Num::Int(60))?,
                )
                .is_some_and(|o| o.is_le()),
            None => false,
        };
        pct_budget(
            &mut verdict,
            away,
            Num::need(&budget)?,
            mult,
            limits.filter(|_| fresh),
        )?;

        // Stale limit data: the USD guard fills the gap
        if !fresh {
            let guard = cfg.float("HARNESS_AWAY_BUDGET_USD");
            if spent.ge(guard.times(mult)?) {
                let line = format!(
                    "limit data stale; USD guard ${} reached (${})",
                    guard.times(mult)?.g(),
                    spent.fixed(2)
                );
                verdict.mark(2, line);
            }
            if spent.ge(guard) {
                verdict.mark(
                    1,
                    format!(
                        "limit data stale; USD guard ${} used (${})",
                        guard.g(),
                        spent.fixed(2)
                    ),
                );
            }
        }
    }
    Ok(verdict)
}

fn usd_budget(verdict: &mut Verdict, budget: Num, mult: Num, spent: Num) -> Result<()> {
    let stage2 = budget.times(mult)?;
    if spent.ge(stage2) {
        let line = format!(
            "${} (x{} budget) reached (${})",
            stage2.g(),
            mult.g(),
            spent.fixed(2)
        );
        verdict.mark(2, line);
    }
    if spent.ge(budget) {
        verdict.mark(
            1,
            format!("budget ${} used (${})", budget.g(), spent.fixed(2)),
        );
    }
    Ok(())
}

// 띄운 수 예산. 1단계 글의 예산은 python `f"{b}"` 라 값 그대로 쓴다
fn agent_budget(verdict: &mut Verdict, budget: &Value, mult: Num, spawned: Num) -> Result<()> {
    let b = Num::need(budget)?;
    let stage2 = b.times(mult)?;
    if spawned.ge(stage2) {
        let line = format!(
            "{} agents (x{} budget) reached ({} spawned)",
            stage2.g(),
            mult.g(),
            spawned.text()
        );
        verdict.mark(2, line);
    }
    if spawned.ge(b) {
        let line = format!(
            "agent budget {} used ({} spawned)",
            str_value(budget),
            spawned.text()
        );
        verdict.mark(1, line);
    }
    Ok(())
}

// 한도 % 예산: 창마다 증가분을 셈한다. `fresh` 는 오래되지 않은 한도 값
fn pct_budget(
    verdict: &mut Verdict,
    away: &mut Dict,
    budget: Num,
    mult: Num,
    fresh: Option<&Dict>,
) -> Result<()> {
    let windows = match away.get_mut("pct").filter(|v| v.truthy()) {
        None => return Ok(()),
        Some(Value::Dict(windows)) => windows,
        Some(_) => return Err(Stop::Raises("pct.items on a value that is not a dict")),
    };
    let names: Vec<String> = windows.iter().map(|(k, _)| k.to_owned()).collect();
    for name in names {
        let Some(Value::Dict(window)) = windows.get_mut(&name) else {
            return Err(Stop::Raises("a pct window that is not a dict"));
        };
        let current = match fresh.and_then(|lim| lim.get(&name)).filter(|v| v.truthy()) {
            None => None,
            Some(Value::Dict(cur)) => Some(cur),
            Some(_) => return Err(Stop::Raises("cur.get on a value that is not a dict")),
        };
        if let Some(cur) = current {
            follow_window(window, cur)?;
        }

        // Increase since away, against the budget and the room left
        let field = |key: &str| {
            Num::need(
                window
                    .get(key)
                    .ok_or(Stop::Raises("KeyError on a pct window"))?,
            )
        };
        let delta = field("acc")?.plus(py_max(
            Num::Float(0.0),
            field("last")?.minus(field("start")?)?,
        ))?;
        let room = field("room")?;
        let (t1, t2) = (py_min(budget, room), py_min(budget.times(mult)?, room));
        let label = match name.as_str() {
            "five_hour" => "5h",
            "seven_day" => "week",
            _ => return Err(Stop::Raises("KeyError on WLABEL")),
        };
        if delta.ge(t2) {
            let line = format!(
                "{label} limit +{}%p since away (stage-2 threshold {}%p)",
                delta.fixed(0),
                t2.g()
            );
            verdict.mark(2, line);
        }
        if delta.ge(t1) {
            verdict.mark(
                1,
                format!(
                    "{label} limit +{}%p since away (budget {}%p)",
                    delta.fixed(0),
                    t1.g()
                ),
            );
        }
    }
    Ok(())
}

// 창 하나를 지금 한도 값으로: 창이 리셋됐으면 리셋 전 증가분을 쌓고 새로 센다
fn follow_window(window: &mut Dict, cur: &Dict) -> Result<()> {
    let truthy = |d: &Dict, key: &str| d.get(key).filter(|v| v.truthy()).cloned();
    if let (Some(cur_r), Some(win_r)) = (truthy(cur, "r"), truthy(window, "r"))
        && Num::need(&cur_r)?.gt(Num::need(&win_r)?.plus(Num::Int(60))?)
    {
        let field = |key: &str| {
            Num::need(
                window
                    .get(key)
                    .ok_or(Stop::Raises("KeyError on a pct window"))?,
            )
        };
        let acc = field("acc")?.plus(py_max(
            Num::Float(0.0),
            field("last")?.minus(field("start")?)?,
        ))?;
        window.insert("acc", acc.value());
        window.insert("start", Value::Float(0.0));
        window.insert("room", Value::Float(100.0));
        window.insert("r", cur_r);
    }

    let last = cur
        .get("p")
        .ok_or(Stop::Raises("KeyError on cur[\"p\"]"))?
        .clone();
    window.insert("last", last);
    if window.get("r").is_none_or(|v| *v == Value::Null) {
        window.insert("r", cur.get("r").cloned().unwrap_or(Value::Null));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use harness_hook::py::json_load::loads;

    fn ledger(json: &str) -> Dict {
        loads(json).unwrap().into_dict().unwrap()
    }

    /// USD 예산: 예산이면 1단계, 2배면 2단계, 도달 시각은 한 번만 적는다.
    #[test]
    fn usd_budget_stages() {
        let cfg = Cfg::default();
        let mut st = ledger(
            r#"{"away": {"on": true, "budget_usd": 1.0, "base_usd": 0.0}, "spent": {"main": {"m": {"usd": 2.5}}}, "log": []}"#,
        );
        let verdict = check(&mut st, &cfg, None, 100.0).unwrap().unwrap();
        assert_eq!(verdict.level, 2);
        assert_eq!(
            verdict.why.as_deref(),
            Some("$2 (x2 budget) reached ($2.50)")
        );
        let away = st.get("away").unwrap().as_dict().unwrap();
        assert_eq!(away.get("over_at"), Some(&Value::Float(100.0)));
        assert_eq!(away.get("over2_at"), Some(&Value::Float(100.0)));
    }

    /// 에이전트 수 예산의 1단계 글은 예산 값을 python str 그대로 쓴다.
    #[test]
    fn agent_budget_text() {
        let cfg = Cfg::default();
        let mut st =
            ledger(r#"{"away": {"on": true, "budget_agents": 3}, "spawned": 4, "log": []}"#);
        let verdict = check(&mut st, &cfg, None, 1.0).unwrap().unwrap();
        assert_eq!(
            verdict.why.as_deref(),
            Some("agent budget 3 used (4 spawned)")
        );
    }
}
