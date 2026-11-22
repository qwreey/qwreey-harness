//! 이미 알린 (쓴 파일, 형제) 쌍(python `read_seen`, `write_seen`). 파일은 `{"seen": ["<경로>\t<형제>", ...]}` 이다.

use std::collections::HashSet;

use harness_hook::py::fs;
use harness_hook::py::json::{EnsureAscii, dumps};
use harness_hook::py::json_load::loads;
use harness_hook::py::surrogate::unit_of;
use harness_hook::py::value::{Dict, Value};

use crate::stop::{Result, Stop};

/// 읽은 쌍들. python 은 `set(...)` 이라 글이 아닌 원소(수, None)도 담는다.
#[derive(Debug, Default)]
pub struct Seen {
    keys: HashSet<String>,
    /// 글이 아닌 원소가 있다. 그러면 python 은 쓸 때 `sorted()` 의 TypeError 로 끝난다.
    has_other: bool,
}

impl Seen {
    /// python `read_seen(p)`: 읽지 못하거나 JSON 객체가 아니면 빈 것.
    ///
    /// `seen` 이 순회할 수 없는 참 값(수)이거나 해시할 수 없는 원소(목록)를 담으면 python 은 TypeError 로 끝난다.
    pub fn read(path: &str) -> Result<Seen> {
        let data = fs::read_text(path).ok().and_then(|t| loads(&t).ok());
        let Some(Value::Dict(data)) = &data else {
            return Ok(Seen::default());
        };
        Seen::from_value(data.get("seen"))
    }

    // python `set(v or [])`
    fn from_value(value: Option<&Value>) -> Result<Seen> {
        let mut seen = Seen::default();
        match value {
            // Nothing seen yet
            None => {}
            Some(v) if !v.truthy() => {}

            // Iterables python turns into a set
            Some(Value::List(items)) => {
                for item in items {
                    match item {
                        Value::Str(s) => {
                            seen.keys.insert(s.clone());
                        }
                        Value::List(_) | Value::Dict(_) => {
                            return Err(Stop::Raises("unhashable item in seen"));
                        }
                        _ => seen.has_other = true,
                    }
                }
            }
            Some(Value::Str(s)) => seen.keys.extend(s.chars().map(String::from)),
            Some(Value::Dict(d)) => seen.keys.extend(d.iter().map(|(k, _)| k.to_owned())),

            // A number or bool is not iterable
            Some(_) => return Err(Stop::Raises("seen is not iterable")),
        }
        Ok(seen)
    }

    /// 이미 알린 쌍인가.
    pub fn contains(&self, key: &str) -> bool {
        self.keys.contains(key)
    }

    /// python `write_seen(p, seen | fresh)`: 임시 파일에 쓰고 바꿔 단다. 쓰기 실패는 넘긴다.
    pub fn write_with(self, path: &str, fresh: impl IntoIterator<Item = String>) -> Result<()> {
        if self.has_other {
            return Err(Stop::Raises("sorted() of str and non-str items"));
        }
        let mut keys: Vec<String> = self.keys.into_iter().chain(fresh).collect();
        keys.sort_by_key(|k| python_order(k));
        keys.dedup();

        // Write a temporary file, then rename it over
        let data = Dict::from_pairs(vec![(
            "seen".to_owned(),
            Value::List(keys.into_iter().map(Value::Str).collect()),
        )]);
        let tmp = format!("{path}.{}.tmp", std::process::id());
        if fs::write_text(&tmp, &dumps(&Value::Dict(data), EnsureAscii::Yes, None)).is_ok()
            && let (Some(from), Some(to)) = (fs::os_path(&tmp), fs::os_path(path))
        {
            let _ = std::fs::rename(from, to);
        }
        Ok(())
    }
}

// python 의 글 비교 순서(코드 포인트). 서로게이트 자리표는 원래 코드로
fn python_order(text: &str) -> Vec<u32> {
    text.chars()
        .map(|c| unit_of(c).unwrap_or(u32::from(c)))
        .collect()
}
