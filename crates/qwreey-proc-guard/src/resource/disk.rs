//! 디스크 여유 공간: 재기, 경고 줄, 같은 경고 줄이기(python 판의 `measure`, `disk_findings`, `disk_advice`).

use std::collections::BTreeSet;

use harness_hook::py::num::format_g;
use harness_hook::py::value::{Dict, Value};

use super::Abort;
use super::config::Limits;
use super::num::Num;

const GIB: f64 = (1u64 << 30) as f64;

/// 파일 시스템 하나의 측정.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Reading {
    /// `st_dev` 를 10진 글로(상태 파일의 키).
    pub dev: String,
    /// 그 파일 시스템의 맨 위 디렉터리.
    pub mount: String,
    /// 권한 없는 사용자가 쓸 수 있는 바이트.
    pub free: u64,
    pub total: u64,
}

/// `paths` 의 파일 시스템마다 한 번 잰다(st_dev 로 겹침을 뺀다). 재지 못한 경로는 건너뛴다.
pub fn measure(paths: &[&str]) -> Vec<Reading> {
    let mut out: Vec<Reading> = Vec::new();
    for p in paths.iter().filter(|p| !p.is_empty()) {
        let Some((real, dev)) = resolve(p) else {
            continue;
        };
        if out.iter().any(|r| r.dev == dev.to_string()) {
            continue;
        }
        let Some((free, total)) = disk_usage(&real) else {
            continue;
        };
        out.push(Reading {
            dev: dev.to_string(),
            mount: mount_point(&real, dev),
            free,
            total,
        });
    }
    out
}

/// 측정을 Pre 기록의 `disk` 칸 꼴로(`{dev: {"mount", "free", "total"}}`).
pub fn to_dict(readings: &[Reading]) -> Dict {
    let mut d = Dict::new();
    for r in readings {
        let mut m = Dict::new();
        m.insert("mount", Value::Str(r.mount.clone()));
        m.insert("free", Value::Int(i128::from(r.free)));
        m.insert("total", Value::Int(i128::from(r.total)));
        d.insert(r.dev.clone(), Value::Dict(m));
    }
    d
}

// python os.path.realpath 와 os.stat(p).st_dev 자리
#[cfg(unix)]
fn resolve(path: &str) -> Option<(String, u64)> {
    use std::os::unix::fs::MetadataExt;

    let real = std::fs::canonicalize(path)
        .ok()?
        .to_string_lossy()
        .into_owned();
    let dev = std::fs::metadata(&real).ok()?.dev();
    Some((real, dev))
}

// Windows 의 st_dev(볼륨 일련번호)는 std 로 읽을 수 없다(windows-sys 가 필요하다). 여유 공간도 같아 재지 않는다
#[cfg(not(unix))]
fn resolve(_path: &str) -> Option<(String, u64)> {
    None
}

// python os.statvfs 자리: 여유는 f_bavail * f_frsize, 전체는 f_blocks * f_frsize
#[cfg(unix)]
fn disk_usage(path: &str) -> Option<(u64, u64)> {
    let st = rustix::fs::statvfs(path).ok()?;
    Some((
        st.f_bavail.saturating_mul(st.f_frsize),
        st.f_blocks.saturating_mul(st.f_frsize),
    ))
}

#[cfg(not(unix))]
fn disk_usage(_path: &str) -> Option<(u64, u64)> {
    None
}

// path 가 든 파일 시스템의 맨 위 디렉터리: 부모의 st_dev 가 다를 때까지 올라간다
#[cfg(unix)]
fn mount_point(path: &str, dev: u64) -> String {
    use super::state::dirname;
    use std::os::unix::fs::MetadataExt;

    let mut cur = path.to_owned();
    loop {
        let up = dirname(&cur);
        if up == cur || up.is_empty() {
            return cur;
        }
        match std::fs::metadata(&up) {
            Ok(m) if m.dev() == dev => cur = up,
            _ => return cur,
        }
    }
}

#[cfg(not(unix))]
fn mount_point(path: &str, _dev: u64) -> String {
    path.to_owned()
}

/// 경고 줄과 그 종류(`low`, `drop`). `state["disk"]` 에 경고한 값을 적어 같은 경고를 되풀이하지 않는다.
///
/// `before` 는 Pre 기록의 `disk` 칸(Post 일 때). 상태 파일이나 Pre 기록의 값이 꼴이 틀리면 python 은 예외라 [`Abort`].
pub fn findings(
    now: &[Reading],
    before: Option<&Value>,
    limits: Limits,
    state: &mut Dict,
    when: &str,
) -> Result<(Vec<String>, BTreeSet<&'static str>), Abort> {
    let step = limits.drop_gib.max(0.5) * GIB;
    let mut lines = Vec::new();
    let mut kinds = BTreeSet::new();

    // python `seen = state.setdefault("disk", {})`: dict 가 아니면 쓸 때 예외, 거짓이면 끝에 지운다
    let seen = match state.setdefault("disk", Value::Dict(Dict::new())) {
        Value::Dict(seen) => seen,
        _ if !now.is_empty() => return Err(Abort),
        other => {
            if !other.truthy() {
                state.remove("disk");
            }
            return Ok((lines, kinds));
        }
    };

    for m in now {
        let Value::Dict(rec) = seen.setdefault(&m.dev, Value::Dict(Dict::new())) else {
            return Err(Abort);
        };
        let free = m.free as f64;
        let pct = if m.total != 0 {
            100.0 * free / m.total as f64
        } else {
            100.0
        };

        // 여유가 낮다: 처음이거나 지난 경고보다 한 단계 더 나빠졌으면 알린다
        let low = (limits.min_free_gib > 0.0 && free < limits.min_free_gib * GIB)
            || (limits.min_free_pct > 0.0 && pct < limits.min_free_pct);
        let warn_low = match rec.get("low") {
            _ if !low => false,
            None => true,
            Some(last) => free <= Num::of(last)?.as_f64() - step,
        };
        if !low {
            rec.remove("low"); // 회복했다가 다시 떨어지면 다시 알린다
        }
        if warn_low {
            rec.insert("low", Value::Int(i128::from(m.free)));
            kinds.insert("low");
            lines.push(format!(
                "Low disk space {when}: {} has {} GiB free ({pct:.1}% of {} GiB; the warning starts below {} GiB or {}%).",
                m.mount,
                gib(free),
                gib(m.total as f64),
                format_g(limits.min_free_gib),
                format_g(limits.min_free_pct)
            ));
        }

        // 이 명령 동안 줄었다: 처음이거나 지난 경고보다 한 단계 더 줄었으면 알린다
        let drop = match previous_free(before, &m.dev)? {
            Some(prev) => prev - Num::Int(i128::from(m.free)),
            None => Num::Int(0),
        };
        let warn_drop = limits.drop_gib > 0.0
            && drop.as_f64() > limits.drop_gib * GIB
            && match rec.get("drop") {
                None => true,
                Some(last) => drop.as_f64() >= Num::of(last)?.as_f64() + step,
            };
        if warn_drop {
            rec.insert("drop", drop.to_value());
            kinds.insert("drop");
            lines.push(format!(
                "Free space on {} fell by {} GiB while this command ran (now {} GiB free).",
                m.mount,
                gib(drop.as_f64()),
                gib(free)
            ));
        }

        if rec.is_empty() {
            seen.remove(&m.dev);
        }
    }

    if seen.is_empty() {
        state.remove("disk");
    }
    Ok((lines, kinds))
}

// python `prev = (before or {}).get(dev)` 와 `prev["free"]`: 참인 값은 dict 여야 하고 dict 의 참인 값은 "free" 가 있어야 한다
fn previous_free(before: Option<&Value>, dev: &str) -> Result<Option<Num>, Abort> {
    let before = match before {
        Some(v) if v.truthy() => v.as_dict().ok_or(Abort)?,
        _ => return Ok(None),
    };
    match before.get(dev) {
        Some(prev) if prev.truthy() => {
            let free = prev.as_dict().ok_or(Abort)?.get("free").ok_or(Abort)?;
            Num::of(free).map(Some)
        }
        _ => Ok(None),
    }
}

/// python `"%.1f" % (n / GIB)`.
pub fn gib(n: f64) -> String {
    format!("{:.1}", n / GIB)
}

/// 경고 뒤에 붙이는 할 일.
pub fn advice(kinds: &BTreeSet<&str>) -> String {
    let mut advice = vec!["Tell the user in one line: the mount and its free GiB."];
    if kinds.contains("drop") {
        advice.push(
            "If the drop came from this command, also say what used the space (check the directories it wrote, \
             e.g. `du -sh <dir>`); other sessions share this disk, so it may not be this command.",
        );
    }
    if kinds.contains("low") {
        advice.push(
            "A full disk breaks builds and every session on this machine. If this session made large files it no longer \
             needs (build output, temp data, core dumps), consider removing them; ask before deleting anything else.",
        );
    }
    advice.join(" ")
}

#[cfg(test)]
mod tests {
    use super::*;

    fn reading(free_gib: f64, total_gib: f64) -> Reading {
        Reading {
            dev: "42".into(),
            mount: "/m".into(),
            free: (free_gib * GIB) as u64,
            total: (total_gib * GIB) as u64,
        }
    }

    const LIMITS: Limits = Limits {
        min_free_gib: 10.0,
        min_free_pct: 5.0,
        drop_gib: 2.0,
    };

    #[test]
    fn low_is_warned_once_then_on_each_step() {
        let mut state = Dict::new();
        let (lines, _) = findings(
            &[reading(3.0, 100.0)],
            None,
            LIMITS,
            &mut state,
            "before this command",
        )
        .unwrap();
        assert_eq!(
            lines,
            [
                "Low disk space before this command: /m has 3.0 GiB free (3.0% of 100.0 GiB; the warning starts below 10 GiB or 5%)."
            ]
        );
        let (lines, _) = findings(&[reading(2.0, 100.0)], None, LIMITS, &mut state, "x").unwrap();
        assert!(lines.is_empty());
        let (lines, _) = findings(&[reading(0.9, 100.0)], None, LIMITS, &mut state, "x").unwrap();
        assert_eq!(lines.len(), 1);
        let (lines, _) = findings(&[reading(50.0, 100.0)], None, LIMITS, &mut state, "x").unwrap();
        assert!(lines.is_empty() && state.is_empty());
    }

    #[test]
    fn drop_is_warned_and_repeated_only_when_worse() {
        let mut state = Dict::new();
        let before = Value::Dict(to_dict(&[reading(50.0, 100.0)]));
        let (lines, kinds) = findings(
            &[reading(47.0, 100.0)],
            Some(&before),
            LIMITS,
            &mut state,
            "after",
        )
        .unwrap();
        assert_eq!(
            lines,
            ["Free space on /m fell by 3.0 GiB while this command ran (now 47.0 GiB free)."]
        );
        assert!(kinds.contains("drop") && advice(&kinds).contains("du -sh"));
        let (lines, _) = findings(
            &[reading(47.0, 100.0)],
            Some(&before),
            LIMITS,
            &mut state,
            "after",
        )
        .unwrap();
        assert!(lines.is_empty());
    }

    #[test]
    fn malformed_records_abort() {
        let mut state = Dict::new();
        state.insert("disk", Value::List(vec![]));
        assert_eq!(
            findings(&[reading(50.0, 100.0)], None, LIMITS, &mut state, "x"),
            Err(Abort)
        );
        let before = Value::Str("x".into());
        assert_eq!(
            findings(
                &[reading(50.0, 100.0)],
                Some(&before),
                LIMITS,
                &mut Dict::new(),
                "x"
            ),
            Err(Abort)
        );
        assert!(findings(&[], Some(&before), LIMITS, &mut Dict::new(), "x").is_ok());
    }
}
