//! 알림 글 만들기(python `sllib/brief.py` 의 `pending_line`, `saved_line`).

use harness_hook::Env;
use harness_hook::py::value::{Dict, Value};
use harness_hook::tag::Level;

use crate::abort::{Abort, Result};
use crate::config::{Config, Key};
use crate::messages::{self, Trigger};
use crate::paths::short_home;
use crate::pyval::Num;
use crate::records_home;
use crate::store::Store;

// python `n >= threshold`(int 와 float 를 값 그대로)
fn at_least(n: i128, threshold: f64) -> bool {
    matches!(
        Num::Int(n).compare(Num::Float(threshold)),
        Some(std::cmp::Ordering::Greater | std::cmp::Ordering::Equal)
    )
}

/// pending 알림 (level, 글). 알릴 것이 없으면 글이 비었다.
///
/// archive_only 면 알리지 않는다. 보관 위치가 있으면 import 한 줄(commit 직전이나 오래 쌓였으면 warn),
/// 위치가 없는데 쌓였으면 위치를 제안하라는 warn.
pub fn pending_line(store: &Store, config: &Config, trigger: Trigger) -> Result<(Level, String)> {
    let quiet = (Level::Info, String::new());
    if records_home::archive_only(&store.root) {
        return Ok(quiet);
    }
    let Some(summary) = store.pending_summary()? else {
        return Ok(quiet);
    };
    let (count, oldest, days) = (summary.count, summary.oldest.as_str(), summary.days);
    let strong = at_least(count as i128, config.num(Key::PendingStrongCount))
        || at_least(i128::from(days), config.num(Key::PendingStrongDays));

    // 보관 위치가 있으면 import 를 안내
    if let Some(home) = records_home::home_rel(&store.root) {
        let level = if strong || trigger == Trigger::Commit {
            Level::Warn
        } else {
            Level::Info
        };
        let home = format!("{home}/");
        return Ok((
            level,
            messages::pending(count, oldest, days, trigger, Some(&home)),
        ));
    }

    // 위치가 없는데 쌓였으면 위치를 정하자고
    let nudge = strong
        || at_least(count as i128, config.num(Key::HomeNudgeCount))
        || at_least(i128::from(days), config.num(Key::HomeNudgeDays));
    if nudge {
        let history = records_home::history_dirs(&store.root);
        return Ok((
            Level::Warn,
            messages::pending_propose(count, oldest, days, &history),
        ));
    }
    Ok((
        Level::Info,
        messages::pending(count, oldest, days, trigger, None),
    ))
}

// python `sum(x.get(key, 0) for x in notices)`
fn sum(notices: &[Dict], key: &str) -> Result<Num> {
    notices.iter().try_fold(Num::Int(0), |total, notice| {
        let value = notice
            .get(key)
            .map_or(Ok(Num::Int(0)), |v| Num::require(v, "notice count"))?;
        total.plus(value)
    })
}

/// 요약 완료 알림 글(python `saved_line`). 알림이 없으면 빈 글.
pub fn saved_line(store: &Store, notices: &[Dict], env: &Env) -> Result<String> {
    if notices.is_empty() {
        return Ok(String::new());
    }
    let sections = sum(notices, "sections")?;

    // 기록 파일들(처음 나온 순서, 겹치면 하나)
    let mut rids: Vec<&str> = Vec::new();
    for notice in notices {
        let items = match notice.get("rids") {
            None => continue,
            Some(Value::List(items)) => items,
            Some(_) => return Err(Abort("notice rids is not a list")),
        };
        for item in items {
            let rid = item.as_str().ok_or(Abort("notice rid is not a string"))?;
            if !rids.contains(&rid) {
                rids.push(rid);
            }
        }
    }
    let files: Vec<String> = rids
        .iter()
        .map(|rid| short_home(&store.record_path(rid), env))
        .collect();

    // 표시한 항목, 받아 가지 않은 기록
    let flagged = sum(notices, "flagged")?;
    let pending = if records_home::archive_only(&store.root) {
        0
    } else {
        store.pending()?.len()
    };
    messages::saved(sections, &files, pending, flagged).ok_or(Abort("saved notice without records"))
}
