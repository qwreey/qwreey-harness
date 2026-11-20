//! 손댄 파일에 전부터 있던 문제의 기록과 Stop 보고(python `hooks/conv_leftovers.py`).
//!
//! 편집마다 이번에 추가하지 않은 줄의 문제를 범주별 줄 수로 세어 `$TMPDIR/claude-conventions/<sid>.left.<main|agent>.json` 에
//! 조용히 쌓고, Stop 에서 reuse-check 의 `<sid>.reuse.<main|agent>.json` 과 합쳐 사용자에게 한 줄(systemMessage)로 보인다.

use std::cmp::Ordering;

use harness_hook::py::fs;
use harness_hook::py::json::{EnsureAscii, dumps, dumps_dict};
use harness_hook::py::json_load::loads;
use harness_hook::py::path::join;
use harness_hook::py::surrogate::unit_of;
use harness_hook::py::value::{Dict, Value};

use super::Category;
use super::docs::doc_class;
use crate::halt::{Halt, Result};

/// 상태 폴더 이름(python `NS`).
pub const NS: &str = "claude-conventions";
const LEFT_MAX_FILES: usize = 5;
const DUP: &str = "같은 목록이 두 곳";
const ORDER: &[&str] = &["이력", "기호", "이스케이프", "보이지 않는 문자", DUP];

/// 범주의 보고 이름(python `LEFT_LABEL.get(cat, cat)`).
fn label(cat: Category) -> &'static str {
    match cat {
        Category::History | Category::RefTail => "이력",
        Category::Symbol => "기호",
        Category::Escape => "이스케이프",
        Category::Invisible => "보이지 않는 문자",
        other => other.as_str(),
    }
}

/// python `left_dir()`: 기록 폴더(만든다). 만들지 못하면 python 은 예외로 끝난다.
pub fn left_dir(tempdir: &str) -> Result<String> {
    let d = join(tempdir, NS);
    let os = fs::os_path(&d).ok_or(Halt::PyError("bad temp dir"))?;
    std::fs::create_dir_all(os).map_err(|_| Halt::PyError("cannot create the leftover dir"))?;
    Ok(d)
}

/// python `record_leftovers(...)` 의 쓰기: 이 파일의 범주별 줄 수를 덮어쓰고, 없으면 지운다. 실패는 넘긴다.
///
/// `probs` 는 이번에 추가하지 않은 줄의 (줄, 범주)들, `who` 는 `main` 또는 정리한 agent id 다.
pub fn record(
    dir: &str,
    sid: &str,
    who: &str,
    key: &str,
    rel: &str,
    probs: &[(usize, Category)],
    now: f64,
) {
    // Count lines per report label
    let mut uniq: Vec<(usize, Category)> = probs.to_vec();
    uniq.sort_by_key(|(ln, c)| (*ln, *c as u8));
    uniq.dedup();
    let mut cnt: Vec<(&str, i128)> = Vec::new();
    for (_, cat) in uniq {
        let name = label(cat);
        match cnt.iter_mut().find(|(k, _)| *k == name) {
            Some((_, n)) => *n += 1,
            None => cnt.push((name, 1)),
        }
    }

    // Rewrite this file's entry
    let fp = join(dir, &format!("{sid}.left.{who}.json"));
    let rec = fs::read_text(&fp)
        .ok()
        .and_then(|t| loads(&t).ok())
        .unwrap_or(Value::Dict(Dict::new()));
    let Ok(mut rec) = rec.into_dict() else { return };
    if !cnt.is_empty() {
        let mut n = Dict::new();
        for (k, v) in cnt {
            n.insert(k, Value::Int(v));
        }
        let mut entry = Dict::new();
        entry.insert("rel", Value::Str(rel.to_owned()));
        entry.insert("n", Value::Dict(n));
        entry.insert("t", Value::Float(now));
        rec.insert(key, Value::Dict(entry));
    } else if rec.remove(key).is_none() {
        return;
    }
    // python 은 짝 없는 서로게이트가 든 글을 인코딩하지 못해 옛 파일을 그대로 둔다
    let text = dumps_dict(&rec, EnsureAscii::No, None);
    if !has_placeholder(&text) {
        let _ = fs::write_text(&fp, &text);
    }
}

fn has_placeholder(text: &str) -> bool {
    text.chars().any(|c| unit_of(c).is_some())
}

// ---------- Stop ----------

// python `v["t"] > best[k]["t"]`. 견줄 수 없는 값(TypeError, KeyError)은 Err: 그 파일의 나머지를 건너뛴다
fn newer(v: &Value, best: &Value) -> std::result::Result<bool, ()> {
    let t = |x: &Value| match x {
        Value::Dict(d) => d.get("t").cloned().ok_or(()),
        _ => Err(()),
    };
    let (a, b) = (t(v)?, t(best)?);
    let num = |x: &Value| match x {
        Value::Bool(b) => Some(f64::from(u8::from(*b))),
        Value::Int(i) => Some(*i as f64),
        Value::Float(f) => Some(*f),
        _ => None,
    };
    match (&a, &b) {
        (Value::Str(x), Value::Str(y)) => Ok(x > y),
        _ => match (num(&a), num(&b)) {
            (Some(x), Some(y)) => Ok(x.partial_cmp(&y) == Some(Ordering::Greater)),
            _ => Err(()),
        },
    }
}

/// python `_latest(pattern)`: 같은 파일의 여러 호출한 쪽 기록 가운데 가장 최근 것. 파일 이름이 `prefix*suffix` 인 것을 본다.
fn latest(dir: &str, prefix: &str, suffix: &str) -> Vec<(String, Value)> {
    let mut best: Vec<(String, Value)> = Vec::new();
    let names = fs::listdir(dir).unwrap_or_default();
    for name in names.iter().filter(|n| {
        n.len() >= prefix.len() + suffix.len() && n.starts_with(prefix) && n.ends_with(suffix)
    }) {
        let loaded = fs::read_text(&join(dir, name))
            .ok()
            .and_then(|t| loads(&t).ok());
        let Some(Value::Dict(rec)) = loaded.as_ref() else {
            continue;
        };
        for (k, v) in rec.iter() {
            match best.iter_mut().find(|(bk, _)| bk == k) {
                None => best.push((k.to_owned(), v.clone())),
                Some((_, b)) => match newer(v, b) {
                    Ok(true) => *b = v.clone(),
                    Ok(false) => {}
                    Err(()) => break,
                },
            }
        }
    }
    best
}

// 보고할 파일 하나: (기록 키, 상대 경로, (보고 이름, 수) 들)
struct FileRow {
    key: String,
    rel: String,
    counts: Vec<(String, Value)>,
}

fn field<'v>(v: &'v Value, key: &str) -> Result<&'v Value> {
    match v {
        Value::Dict(d) => d
            .get(key)
            .ok_or(Halt::PyError("a leftover record lacks a field")),
        _ => Err(Halt::PyError("a leftover record is not a dict")),
    }
}

fn text(v: &Value) -> Result<String> {
    match v {
        Value::Str(s) => Ok(s.clone()),
        _ => Err(Halt::Unported("a leftover path that is not a string")),
    }
}

fn shown(v: &Value) -> Result<String> {
    v.scalar_str()
        .ok_or(Halt::Unported("a leftover count is a container"))
}

// python `dict(v["n"])`. dict 가 아닌 n 은 옮기지 않는다
fn counts(v: &Value) -> Result<Vec<(String, Value)>> {
    match v {
        Value::Dict(n) => Ok(n.iter().map(|(k, c)| (k.to_owned(), c.clone())).collect()),
        _ => Err(Halt::Unported("leftover counts are not a dict")),
    }
}

// 기록 두 벌을 합친 (파일 줄, 다른 사본 (상대 경로, 수))
type Gathered = (Vec<FileRow>, Vec<(String, i128)>);

fn gather(left: &[(String, Value)], reuse: &[(String, Value)]) -> Result<Gathered> {
    let mut rows: Vec<FileRow> = Vec::new();
    for (k, v) in left {
        if field(v, "n")?.truthy() && fs::exists(k) {
            let row = FileRow {
                key: k.clone(),
                rel: text(field(v, "rel")?)?,
                counts: counts(field(v, "n")?)?,
            };
            match rows.iter_mut().find(|r| r.key == *k) {
                Some(slot) => *slot = row,
                None => rows.push(row),
            }
        }
    }

    let mut diff = Vec::new();
    for (k, v) in reuse {
        if !fs::exists(k) {
            continue;
        }
        let Value::Dict(d) = v else {
            return Err(Halt::PyError("a reuse record is not a dict"));
        };
        if let Some(dup) = d.get("dup").filter(|x| x.truthy()) {
            let rel = field(v, "rel")?;
            if !rows.iter().any(|r| r.key == *k) {
                rows.push(FileRow {
                    key: k.clone(),
                    rel: text(rel)?,
                    counts: Vec::new(),
                });
            }
            if let Some(row) = rows.iter_mut().find(|r| r.key == *k) {
                match row.counts.iter_mut().find(|(c, _)| c == DUP) {
                    Some(slot) => slot.1 = dup.clone(),
                    None => row.counts.push((DUP.to_owned(), dup.clone())),
                }
            }
        }
        if let Some(differ) = d.get("differ").filter(|x| x.truthy()) {
            let Value::Int(n) = differ else {
                return Err(Halt::Unported("a differ count that is not an int"));
            };
            diff.push((text(field(v, "rel")?)?, *n));
        }
    }
    Ok((rows, diff))
}

/// python `leftover_message(sid)`: 세션의 모든 호출한 쪽 기록을 합친 사용자용 글. 없으면 `None`.
///
/// 첫 줄은 전부터 있던 문제(주석, 같은 목록), 둘째 줄은 원본과 달라진 사본이다. 파일은 상대 경로로만 정렬한다:
/// 두 저장소의 같은 상대 경로는 모은 차례 그대로다(python `sorted(key=...)` 는 안정 정렬이다).
pub fn message(dir: &str, sid: &str) -> Result<Option<String>> {
    let left = latest(dir, &format!("{sid}.left."), ".json");
    let reuse = latest(dir, &format!("{sid}.reuse."), ".json");
    let (mut rows, mut diff) = gather(&left, &reuse)?;
    rows.sort_by(|a, b| a.rel.cmp(&b.rel));
    diff.sort();
    let mut lines = Vec::new();

    // Old problems in touched files
    if !rows.is_empty() {
        let mut parts = Vec::new();
        for r in rows.iter().take(LEFT_MAX_FILES) {
            let mut cs = Vec::new();
            for c in ORDER {
                if let Some((_, n)) = r.counts.iter().find(|(k, _)| k == c) {
                    cs.push(format!("{c} {}", shown(n)?));
                }
            }
            parts.push(format!("{}({})", r.rel, cs.join(", ")));
        }
        let more = if rows.len() > LEFT_MAX_FILES {
            format!(" 외 {}개", rows.len() - LEFT_MAX_FILES)
        } else {
            String::new()
        };
        let mut is_doc = Vec::new();
        for r in rows
            .iter()
            .filter(|r| r.counts.iter().any(|(c, _)| c != DUP))
        {
            is_doc.push(doc_class(&r.rel)?.is_some());
        }
        let mut tools = Vec::new();
        if !is_doc.iter().all(|d| *d) {
            tools.push("주석은 /qwreey-conventions:comments-cleanup");
        }
        if is_doc.iter().any(|d| *d) {
            tools.push("모델용 문서는 /qwreey-conventions:docs-cleanup");
        }
        let mut how = Vec::new();
        if !tools.is_empty() {
            how.push(format!("{} 으로 정리합니다.", tools.join(", ")));
        }
        if rows.iter().any(|r| r.counts.iter().any(|(c, _)| c == DUP)) {
            how.push("같은 목록은 \"기존 문제도 정리해줘\" 라고 하시면 됩니다.".to_owned());
        }
        lines.push(format!(
            "손댄 파일에 전부터 있던 문제: {}{more}. {}",
            parts.join(", "),
            how.join(" ")
        ));
    }

    // Copies that drifted from their source
    if !diff.is_empty() {
        let shown: Vec<String> = diff
            .iter()
            .take(LEFT_MAX_FILES)
            .map(|(rel, n)| format!("{rel} {n}"))
            .collect();
        let more = if diff.len() > LEFT_MAX_FILES {
            format!(" 외 {}개", diff.len() - LEFT_MAX_FILES)
        } else {
            String::new()
        };
        lines.push(format!(
            "사본이 원본과 다름: {}{more}. 동작이 달라질 수 있습니다.",
            shown.join(", ")
        ));
    }
    Ok((!lines.is_empty()).then(|| lines.join("\n")))
}

/// python `report_leftovers(data)`: 글이 지난번과 달라졌을 때만 systemMessage 로 한 번 보인다.
pub fn report(tempdir: &str, sid: &str) -> Result<Option<String>> {
    let dir = left_dir(tempdir)?;
    let Some(msg) = message(&dir, sid)? else {
        return Ok(None);
    };

    // Skip a message the user already saw
    let mark = join(&dir, &format!("{sid}.reported.json"));
    let seen = fs::read_text(&mark).ok().and_then(|t| loads(&t).ok());
    if let Some(Value::Dict(d)) = &seen
        && d.get("msg").and_then(Value::as_str) == Some(msg.as_str())
    {
        return Ok(None);
    }

    let mut rec = Dict::new();
    rec.insert("msg", Value::Str(msg.clone()));
    let text = dumps(&Value::Dict(rec), EnsureAscii::No, None);
    if !has_placeholder(&text) {
        let _ = fs::write_text(&mark, &text);
    }
    Ok(Some(
        harness_hook::HookOutput::system_message(msg).render(EnsureAscii::No),
    ))
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 두 저장소의 같은 상대 경로는 모은 차례 그대로 둘 다 보인다(python 은 dict 끼리 견주다 끝났었다).
    #[test]
    fn same_relative_path_in_two_repos() {
        // Two left records for files that exist, under one relative path
        let dir = std::env::temp_dir().join(format!("conv-left-{}", std::process::id()));
        let (a, b) = (dir.join("a").join("x.luau"), dir.join("b").join("x.luau"));
        for f in [&a, &b] {
            std::fs::create_dir_all(f.parent().unwrap()).unwrap();
            std::fs::write(f, "x").unwrap();
        }
        let rec = format!(
            r#"{{"{}": {{"rel": "x.luau", "n": {{"기호": 1}}, "t": 1.0}}, "{}": {{"rel": "x.luau", "n": {{"이력": 2}}, "t": 1.0}}}}"#,
            a.to_str().unwrap(),
            b.to_str().unwrap()
        );
        std::fs::write(dir.join("s.left.main.json"), rec).unwrap();

        // Both rows, in the order they were gathered
        let msg = message(dir.to_str().unwrap(), "s").unwrap().unwrap();
        assert!(msg.contains("x.luau(기호 1), x.luau(이력 2)"), "{msg}");
        std::fs::remove_dir_all(&dir).unwrap();
    }
}
