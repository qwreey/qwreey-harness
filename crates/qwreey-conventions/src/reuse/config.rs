//! 저장소 설정 `.claude/conventions.json` 의 `reuse`(python reuse-check 의 `load_cfg`, `mode_of`, `allowed`).
//!
//! 값은 python 이 읽는 그대로 dict 로 들고, 쓰는 자리에서 python 의 `or`, `int()`, 반복 규칙으로 읽는다.
//! python 이 예외로 끝나는 값(목록인 `min_shared`, 글이 아닌 `reason` 등)은 그 값을 쓰는 자리에서 [`Halt::PyError`] 다.

use std::collections::BTreeSet;

use harness_hook::py::fnmatch::fnmatch;
use harness_hook::py::fs;
use harness_hook::py::json_load::loads;
use harness_hook::py::num::parse_int;
use harness_hook::py::path::join;
use harness_hook::py::value::{Dict, Value};

use crate::context::Context;
use crate::halt::{Halt, Result};
use crate::reuse::sets::reason_ok;

/// 검사 모드(python `mode_of`).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Mode {
    /// 모든 검사를 끈다.
    Off,
    /// 겹침(H1)은 알리지 않고 그림자 기록에만 남긴다(기본).
    Shadow,
    /// 겹침도 알린다.
    On,
}

/// `reuse` 설정 dict.
#[derive(Clone, Debug, Default)]
pub struct ReuseConfig {
    raw: Dict,
}

impl ReuseConfig {
    /// python `load_cfg(root)`: 읽지 못하거나 dict 가 아니면 빈 설정.
    pub fn load(root: &str) -> ReuseConfig {
        let path = join(&join(root, ".claude"), "conventions.json");
        let raw = fs::read_text(&path)
            .ok()
            .and_then(|text| loads(&text).ok())
            .and_then(|v| v.into_dict().ok())
            .and_then(|mut d| d.remove("reuse"))
            .and_then(|r| r.into_dict().ok())
            .unwrap_or_default();
        ReuseConfig { raw }
    }

    /// python `mode_of(cfg)`: 환경 변수 `REUSE_CHECK`, harness.env 층, 설정 `mode`, 기본 `shadow` 의 차례.
    pub fn mode(&self, ctx: &Context) -> Result<Mode> {
        let chosen = match ctx.env.get_nonempty("REUSE_CHECK") {
            Some(v) => v.to_owned(),
            // harness.env 층, 그다음 설정 값
            None => match ctx.env_value("REUSE_CHECK") {
                v if !v.is_empty() => v,
                _ => match self.raw.get("mode") {
                    Some(Value::Str(s)) if !s.is_empty() => s.clone(),
                    Some(v) if v.truthy() => {
                        return Err(Halt::PyError("reuse.mode is not a string"));
                    }
                    _ => "shadow".to_owned(),
                },
            },
        };

        Ok(match chosen.to_lowercase().as_str() {
            "off" => Mode::Off,
            "on" => Mode::On,
            _ => Mode::Shadow,
        })
    }

    /// python `allowed(rel, cfg)`: 사유 있는 `allow` 글롭에 맞는 파일인가.
    pub fn allowed(&self, rel: &str) -> Result<bool> {
        for a in iterate(self.raw.get("allow"))? {
            // python `a.get("path") and reason_ok(a.get("reason")) and fnmatch(rel, a["path"])`
            let Value::Dict(a) = &a else { continue };
            let path = match a.get("path") {
                Some(p) if p.truthy() => p,
                _ => continue,
            };
            if !reason_value_ok(a.get("reason"))? {
                continue;
            }

            // The glob; python's fnmatch ends on a path that is not a string
            let Value::Str(path) = path else {
                return Err(Halt::PyError("an allow path that is not a string"));
            };
            let hit = fnmatch(rel, path)
                .map_err(|_| Halt::Unported("an allow glob this port cannot translate"))?;
            if hit {
                return Ok(true);
            }
        }
        Ok(false)
    }

    /// python `int(cfg.get("min_shared") or 3)`.
    pub fn min_shared(&self) -> Result<i128> {
        match self.raw.get("min_shared") {
            Some(v) if v.truthy() => py_int(v),
            _ => Ok(3),
        }
    }

    /// python `[frozenset(v) for v in cfg.get("vocab_ok") or [] if isinstance(v, list)]` 의 글 원소들.
    pub fn vocab(&self) -> Result<Vec<BTreeSet<String>>> {
        let mut out = Vec::new();
        for v in iterate(self.raw.get("vocab_ok"))? {
            let Value::List(items) = &v else { continue };

            // frozenset(v) needs hashable items; only strings can meet a shared set
            let mut set = BTreeSet::new();
            for item in items {
                match item {
                    Value::Str(s) => {
                        set.insert(s.clone());
                    }
                    Value::List(_) | Value::Dict(_) => {
                        return Err(Halt::PyError("vocab_ok holds an unhashable value"));
                    }
                    _ => {}
                }
            }
            out.push(set);
        }
        Ok(out)
    }
}

// python `for a in (value or [])`: 목록은 원소, dict 는 키, 글은 글자. 다른 참인 값은 TypeError
fn iterate(value: Option<&Value>) -> Result<Vec<Value>> {
    Ok(match value {
        None => Vec::new(),
        Some(v) if !v.truthy() => Vec::new(),
        Some(Value::List(items)) => items.clone(),
        Some(Value::Dict(d)) => d.iter().map(|(k, _)| Value::Str(k.to_owned())).collect(),
        Some(Value::Str(s)) => s.chars().map(|c| Value::Str(c.to_string())).collect(),
        Some(_) => return Err(Halt::PyError("a config value that is not iterable")),
    })
}

// python reason_ok(a.get("reason")): `(text or "").strip()` 은 글이 아닌 참인 값에서 끝난다
fn reason_value_ok(reason: Option<&Value>) -> Result<bool> {
    match reason {
        Some(Value::Str(s)) => Ok(reason_ok(s)),
        Some(v) if v.truthy() => Err(Halt::PyError("an allow reason that is not a string")),
        _ => Ok(reason_ok("")),
    }
}

// python int(v) 가 받는 값. 잡지 않는 예외(ValueError, TypeError, OverflowError)는 PyError
fn py_int(v: &Value) -> Result<i128> {
    match v {
        Value::Bool(b) => Ok(i128::from(*b)),
        Value::Int(i) => Ok(*i),
        Value::Float(f) if f.is_finite() => Ok(f.trunc() as i128),
        Value::Str(s) => parse_int(s).ok_or(Halt::PyError("min_shared is not an integer")),
        Value::BigInt(_) => Err(Halt::Unported("a huge min_shared")),
        _ => Err(Halt::PyError("min_shared is not an integer")),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn cfg(json: &str) -> ReuseConfig {
        ReuseConfig {
            raw: loads(json).unwrap().into_dict().unwrap(),
        }
    }

    /// `allow` 는 사유가 있는 글롭만 받고, python 이 끝나는 값은 PyError 다.
    #[test]
    fn allow_needs_a_reason() {
        let c = cfg(
            r#"{"allow": [{"path": "gen/*", "reason": "generated by the build"}, {"path": "x/*", "reason": "later"}]}"#,
        );
        assert_eq!(c.allowed("gen/a.py"), Ok(true));
        assert_eq!(c.allowed("x/a.py"), Ok(false));

        // A non-string path fails only when the reason is good
        assert!(
            cfg(r#"{"allow": [{"path": 5, "reason": "a fine reason"}]}"#)
                .allowed("a")
                .is_err()
        );
        assert_eq!(cfg(r#"{"allow": [{"path": 5}]}"#).allowed("a"), Ok(false));
    }

    /// `min_shared` 는 python `int(x or 3)`: 0 은 거짓이라 3 이다.
    #[test]
    fn min_shared_like_python_int() {
        assert_eq!(cfg(r#"{"min_shared": 0}"#).min_shared(), Ok(3));
        assert_eq!(cfg(r#"{"min_shared": " 4 "}"#).min_shared(), Ok(4));
        assert_eq!(cfg(r#"{"min_shared": 2.9}"#).min_shared(), Ok(2));
        assert!(cfg(r#"{"min_shared": [1]}"#).min_shared().is_err());
    }
}
