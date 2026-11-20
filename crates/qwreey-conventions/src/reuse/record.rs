//! 기록과 출력(python reuse-check 의 dedup 상태, `shadow_log`, `record_report`, `emit`).
//!
//! 세 파일 모두 python 과 같은 꼴로 쓴다: 상태는 `json.dump(state)`(ASCII, `", "` `": "`), 그림자 기록은 줄마다
//! `json.dumps(rec, ensure_ascii=False)`, 턴 끝 보고는 `json.dump(rec, ensure_ascii=False)`. 두 판이 번갈아 써도 된다.

use std::io::Write;

use harness_hook::output::{EnsureAscii, HookOutput};
use harness_hook::py::fs;
use harness_hook::py::json::dumps;
use harness_hook::py::json_load::loads;
use harness_hook::py::path::{abspath, join};
use harness_hook::py::surrogate::unit_of;
use harness_hook::py::value::{Dict, Value};

use crate::context::{Context, PLUGIN};
use crate::halt::{Halt, Result};
use crate::pyval;
use crate::reuse::judge::Hit;
use crate::reuse::sets::StringSet;

/// 턴 끝 보고 기록의 폴더(python `NS`, conventions-check 의 Stop 이 합쳐 보인다).
const NS: &str = "claude-conventions";

/// 파일당 겹침 알림 수(python `MAX_NOTICES_PER_FILE`).
pub const MAX_NOTICES_PER_FILE: i128 = 2;

/// dedup 상태 파일(python `state`): `seen` 목록과 파일별 알림 수 `n`.
pub struct State {
    path: String,
    data: Dict,
}

impl State {
    /// python `json.load(open(sp))` 뒤 `state.setdefault("seen", [])`.
    ///
    /// dict 가 아니면 python 은 `setdefault` 에서 끝난다. 목록이 아닌 `seen` 은 python 이 글이나 dict 로 다루는 자리라 옮기지 않는다.
    pub fn load(path: String) -> Result<State> {
        let value = fs::read_text(&path)
            .ok()
            .and_then(|t| loads(&t).ok())
            .unwrap_or_else(|| Value::Dict(Dict::new()));
        let Ok(mut data) = value.into_dict() else {
            return Err(Halt::PyError("the state file is not a dict"));
        };
        if !matches!(
            data.setdefault("seen", Value::List(Vec::new())),
            Value::List(_)
        ) {
            return Err(Halt::Unported("a state seen that is not a list"));
        }
        Ok(State { path, data })
    }

    fn seen(&mut self) -> &mut Vec<Value> {
        match self.data.get_mut("seen") {
            Some(Value::List(items)) => items,
            _ => unreachable!("load keeps seen a list"),
        }
    }

    /// 처음 보는 키면 적고 true(python `if key not in seen: seen.append(key)`).
    pub fn first_time(&mut self, key: &str) -> bool {
        let seen = self.seen();
        if seen.iter().any(|v| v.as_str() == Some(key)) {
            return false;
        }
        seen.push(Value::Str(key.to_owned()));
        true
    }

    /// `key` 를 이미 봤나.
    pub fn has_seen(&mut self, key: &str) -> bool {
        self.seen().iter().any(|v| v.as_str() == Some(key))
    }

    /// python `state.setdefault("n", {}).get(rel, 0) < MAX_NOTICES_PER_FILE`.
    pub fn under_notice_cap(&mut self, rel: &str) -> Result<bool> {
        let Value::Dict(n) = self.data.setdefault("n", Value::Dict(Dict::new())) else {
            return Err(Halt::PyError("a state n without .get"));
        };
        Ok(match n.get(rel) {
            None => true,
            Some(Value::Int(i)) => *i < MAX_NOTICES_PER_FILE,
            Some(Value::Bool(b)) => i128::from(*b) < MAX_NOTICES_PER_FILE,
            Some(Value::Float(f)) => *f < MAX_NOTICES_PER_FILE as f64,
            Some(Value::BigInt(_)) => return Err(Halt::Unported("a huge state count")),
            Some(_) => return Err(Halt::PyError("a state count python cannot compare with 2")),
        })
    }

    /// python `state["n"][rel] = state["n"].get(rel, 0) + 1`.
    pub fn count_notice(&mut self, rel: &str) -> Result<()> {
        let Some(Value::Dict(n)) = self.data.get_mut("n") else {
            return Err(Halt::Unported("a state n that is not a dict"));
        };
        let next = match n.get(rel) {
            None => Value::Int(1),
            Some(Value::Int(i)) => Value::Int(i + 1),
            Some(Value::Bool(b)) => Value::Int(i128::from(*b) + 1),
            Some(Value::Float(f)) => Value::Float(f + 1.0),
            Some(_) => return Err(Halt::Unported("a state count that is not a number")),
        };
        n.insert(rel, next);
        Ok(())
    }

    /// python `json.dump(state, open(sp, "w"))`. 쓰기 실패는 넘긴다.
    pub fn save(&self) {
        let _ = fs::write_text(
            &self.path,
            &dumps(&Value::Dict(self.data.clone()), EnsureAscii::Yes, None),
        );
    }
}

/// python `emit(sid, sp, state, notes)`: 상태를 저장하고, 알림이 있으면 한 블록의 stdout 글을 돌려준다.
pub fn emit(
    ctx: &Context,
    session_id: Option<&Value>,
    state: &State,
    notes: &[String],
) -> Result<Option<String>> {
    state.save();
    if notes.is_empty() {
        return Ok(None);
    }
    let nonce = ctx.nonce_attr(session_id)?;
    let msg = format!(
        "<harness-hook name=\"{PLUGIN}\" level=\"info\"{nonce}>{}</harness-hook>",
        notes.join("; ")
    );
    Ok(Some(
        HookOutput::context("PostToolUse", msg).render(EnsureAscii::No),
    ))
}

/// 그림자 기록 한 줄(python `log_rec` 의 dict). 키 순서가 곧 출력 순서다.
pub struct ShadowRecord {
    fields: Dict,
}

/// [`ShadowRecord`] 를 만드는 데 드는 이 편집의 값.
pub struct Edited<'a> {
    pub rel: &'a str,
    /// `os.path.basename(root)`.
    pub repo: &'a str,
    /// `LANG.get(ext)`.
    pub lang: Option<&'a str>,
}

impl ShadowRecord {
    /// python `log_rec(check, notice, st, hit, extra)`.
    pub fn new(
        edited: &Edited<'_>,
        check: &str,
        notice: &str,
        set_hit: Option<(&StringSet, &Hit)>,
        extra: Vec<(&str, Value)>,
    ) -> Result<ShadowRecord> {
        let line = set_hit.map_or(0, |(st, _)| st.line);
        let at = format!("{}:{line}", edited.rel);
        let id = crate::reuse::index::short_sha1(&format!("{at}:{check}:{notice}"))?;

        // Fields every record has
        let mut f = Dict::new();
        f.insert("id", Value::Str(id));
        f.insert("t", Value::Int(now().trunc() as i128));
        f.insert("repo", Value::Str(edited.repo.to_owned()));
        f.insert(
            "lang",
            edited
                .lang
                .map_or(Value::Null, |l| Value::Str(l.to_owned())),
        );
        f.insert("check", Value::Str(check.to_owned()));
        f.insert("notice", Value::Str(notice.to_owned()));
        f.insert("at", Value::Str(at));

        // The pair, without source text beyond the shared strings
        if let Some((st, hit)) = set_hit {
            let bools = |a: bool, b: bool| Value::List(vec![Value::Bool(a), Value::Bool(b)]);
            let shared: Vec<Value> = hit
                .shared
                .iter()
                .take(8)
                .map(|x| Value::Str(x.chars().take(40).collect()))
                .collect();
            let signals = Dict::from_pairs(vec![
                (
                    "def".to_owned(),
                    bools(st.is_def(), hit.other_flags & 1 != 0),
                ),
                (
                    "type".to_owned(),
                    bools(st.is_type(), hit.other_flags & 2 != 0),
                ),
            ]);
            f.insert(
                "other",
                Value::Str(format!("{}:{}", hit.other_rel, hit.other_line)),
            );
            f.insert("name", Value::Str(st.name.clone()));
            f.insert("shared", Value::List(shared));
            f.insert("k", Value::Int(hit.k as i128));
            f.insert("n", Value::Int(hit.n as i128));
            f.insert("j", Value::Float(round2(hit.j)));
            f.insert("signals", Value::Dict(signals));
        }
        for (k, v) in extra {
            f.insert(k, v);
        }
        Ok(ShadowRecord { fields: f })
    }
}

/// python `round(x, 2)`: 정확한 이진 값을 소수 둘째 자리로(동점은 짝수 쪽), 그 글을 다시 float 로.
pub fn round2(x: f64) -> f64 {
    format!("{x:.2}").parse().unwrap_or(x)
}

/// python `time.time()`.
pub fn now() -> f64 {
    harness_hook::nonce::now_secs()
}

/// 기록들에 `ms`, `budget` 을 붙여 차례로 한 줄씩 덧붙인다(python `shadow_log`).
///
/// 자리는 `$CLAUDE_PLUGIN_DATA/reuse-shadow.jsonl`, 없으면 `<임시 폴더>/claude-qwreey-reuse/shadow.jsonl`.
/// 짝 없는 서로게이트가 든 줄은 python 이 쓰다 UnicodeEncodeError 로 끝난다(앞 줄들은 이미 쓰였다).
pub fn shadow_log(ctx: &Context, records: Vec<ShadowRecord>, ms: i128, budget: bool) -> Result<()> {
    if records.is_empty() {
        return Ok(());
    }
    let (dir, name) = match ctx.env.get_nonempty("CLAUDE_PLUGIN_DATA") {
        Some(d) => (d.to_owned(), "reuse-shadow.jsonl"),
        None => (join(ctx.tempdir()?, "claude-qwreey-reuse"), "shadow.jsonl"),
    };
    let path = join(&dir, name);

    for mut rec in records {
        rec.fields.insert("ms", Value::Int(ms));
        rec.fields.insert("budget", Value::Bool(budget));
        let line = format!(
            "{}\n",
            dumps(&Value::Dict(rec.fields), EnsureAscii::No, None)
        );
        if line.chars().any(|c| unit_of(c).is_some()) {
            return Err(Halt::PyError("a shadow record with a lone surrogate"));
        }
        let _ = append(&dir, &path, &line);
    }
    Ok(())
}

fn append(dir: &str, path: &str, line: &str) -> std::io::Result<()> {
    let bad = || std::io::Error::from(std::io::ErrorKind::InvalidInput);
    std::fs::create_dir_all(fs::os_path(dir).ok_or_else(bad)?)?;
    let mut f = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(fs::os_path(path).ok_or_else(bad)?)?;
    f.write_all(line.as_bytes())
}

/// python `record_report(data, path, rel, dup, differ)`: 턴 끝 보고용 기록. 무엇이 실패해도 조용히 넘긴다.
///
/// 같은 파일은 마지막 편집 기준으로 덮어쓰고, 둘 다 0 이면 지운다(없으면 쓰지 않는다).
pub fn record_report(
    ctx: &Context,
    session_id: Option<&Value>,
    agent_id: Option<&Value>,
    path: &str,
    rel: &str,
    dup: usize,
    differ: usize,
) {
    let _ = try_record_report(ctx, session_id, agent_id, path, rel, dup, differ);
}

fn try_record_report(
    ctx: &Context,
    session_id: Option<&Value>,
    agent_id: Option<&Value>,
    path: &str,
    rel: &str,
    dup: usize,
    differ: usize,
) -> Option<()> {
    let dir = join(ctx.tempdir().ok()?, NS);
    std::fs::create_dir_all(fs::os_path(&dir)?).ok()?;
    let who = match pyval::truthy_text(agent_id).ok()? {
        Some(agent) => harness_hook::epoch::sanitize(&agent),
        None => "main".to_owned(),
    };
    let sid = pyval::sanitized_id(session_id).ok()?;
    let fp = join(&dir, &format!("{sid}.reuse.{who}.json"));

    // Update or drop this file's line
    let mut rec = fs::read_text(&fp)
        .ok()
        .and_then(|t| loads(&t).ok())
        .unwrap_or_else(|| Value::Dict(Dict::new()))
        .into_dict()
        .ok()?;
    let key = abspath(path)?;
    if dup > 0 || differ > 0 {
        let line = Dict::from_pairs(vec![
            ("rel".to_owned(), Value::Str(rel.to_owned())),
            ("dup".to_owned(), Value::Int(dup as i128)),
            ("differ".to_owned(), Value::Int(differ as i128)),
            ("t".to_owned(), Value::Float(now())),
        ]);
        rec.insert(key, Value::Dict(line));
    } else if rec.remove(&key).is_none() {
        return Some(());
    }

    // python 은 파일을 먼저 비우고 쓰다 인코딩 오류에서 멈춘다
    let text = dumps(&Value::Dict(rec), EnsureAscii::No, None);
    if text.chars().any(|c| unit_of(c).is_some()) {
        let _ = fs::write_text(&fp, "");
        return None;
    }
    fs::write_text(&fp, &text).ok()
}

#[cfg(test)]
mod tests {
    use super::*;
    use harness_hook::py::num::float_repr;

    /// python round(x, 2) 는 정확한 이진 값의 동점에서 짝수 쪽이다(0.125 -> 0.12).
    #[test]
    fn round2_like_python() {
        assert_eq!(float_repr(round2(0.125)), "0.12");
        assert_eq!(float_repr(round2(0.375)), "0.38");
        assert_eq!(float_repr(round2(1.0)), "1.0");
        assert_eq!(float_repr(round2(2.0 / 3.0)), "0.67");
    }
}
