//! 툴킷 표(python `TOOLKITS`, `toolkit_table`, `toolkit_of`): 확장자마다 예외 표식 주석, 생성물 접미사, 건너뛸 폴더, 테스트 판정.
//!
//! 저장소 structure.json 의 `toolkits` 가 항목을 덮어쓰거나 더하므로 항목은 JSON dict 로 둔다. 키를 읽는 자리마다
//! python 처럼 다룬다(글인 `ext` 는 부분 글로 찾는다 등).

use harness_hook::py::path::splitext;
use harness_hook::py::re::Regex;
use harness_hook::py::text::split_whitespace;
use harness_hook::py::value::{Dict, Value};

use super::config::Config;
use super::num::Limit;
use super::pyops::{contains, items, items_or_empty, re_halt};
use crate::halt::{Halt, Result};

/// 기본 표의 확장자 전부(Bash 경로 탐지가 쓴다). 길이가 긴 것부터.
pub const BASH_EXTS: &[&str] = &[
    "astro", "luau", "lua", "tsx", "jsx", "mjs", "ts", "js", "rs", "py", "go", "kt",
];

/// 예외 표식 주석의 기본값(항목에 `comment` 가 없을 때).
const DEFAULT_COMMENTS: &[&str] = &["--", "//", "#"];

/// 툴킷 하나: 이름과 항목.
#[derive(Clone, Debug, PartialEq)]
pub struct Toolkit {
    pub name: String,
    pub spec: Dict,
}

/// 이 실행의 툴킷 표(python `toolkit_table(cfg)`의 결과, 넣은 순서대로).
#[derive(Clone, Debug, PartialEq)]
pub struct Table(Vec<Toolkit>);

fn strs(values: &[&str]) -> Value {
    Value::List(values.iter().map(|s| Value::Str((*s).to_owned())).collect())
}

fn spec(pairs: &[(&str, Value)]) -> Dict {
    Dict::from_pairs(
        pairs
            .iter()
            .map(|(k, v)| ((*k).to_owned(), v.clone()))
            .collect(),
    )
}

/// python `TOOLKITS`.
pub fn defaults() -> Vec<Toolkit> {
    let py_test = r"(^|/)test_[^/]*\.py$|_test\.py$|(^|/)conftest\.py$";
    let rows = [
        (
            "luau",
            spec(&[
                ("ext", strs(&[".luau", ".lua"])),
                ("comment", strs(&["--"])),
                ("skip_suffix", strs(&[".d.luau"])),
            ]),
        ),
        (
            "web",
            spec(&[
                (
                    "ext",
                    strs(&[".ts", ".tsx", ".js", ".jsx", ".mjs", ".astro"]),
                ),
                ("comment", strs(&["//"])),
                (
                    "skip_suffix",
                    strs(&[".d.ts", ".d.mts", ".min.js", ".gen.ts"]),
                ),
                (
                    "skip_parts",
                    strs(&[".astro", ".next", ".turbo", ".svelte-kit"]),
                ),
            ]),
        ),
        (
            "rust",
            spec(&[
                ("ext", strs(&[".rs"])),
                ("comment", strs(&["//"])),
                ("skip_parts", strs(&["target"])),
            ]),
        ),
        (
            "python",
            spec(&[
                ("ext", strs(&[".py"])),
                ("comment", strs(&["#"])),
                ("skip_suffix", strs(&["_pb2.py", "_pb2_grpc.py"])),
                (
                    "skip_parts",
                    strs(&[
                        "__pycache__",
                        ".venv",
                        "venv",
                        "site-packages",
                        ".mypy_cache",
                    ]),
                ),
                ("test", Value::Str(py_test.to_owned())),
            ]),
        ),
        (
            "go",
            spec(&[
                ("ext", strs(&[".go"])),
                ("comment", strs(&["//"])),
                ("skip_suffix", strs(&[".pb.go"])),
            ]),
        ),
        (
            "jvm",
            spec(&[("ext", strs(&[".kt"])), ("comment", strs(&["//"]))]),
        ),
    ];
    rows.into_iter()
        .map(|(name, spec)| Toolkit {
            name: name.to_owned(),
            spec,
        })
        .collect()
}

impl Table {
    /// python `toolkit_table(cfg)`: `enabled`(HARNESS_TOOLKITS 글)에 든 기본 툴킷에 저장소의 덮어쓰기와 추가를 얹는다.
    ///
    /// `enabled` 가 비었으면 기본 툴킷 전부다. 같은 이름의 덮어쓰기는 키마다 합치고 자리를 지킨다.
    pub fn new(cfg: &Config, enabled: &str) -> Table {
        let enabled: Vec<&str> = split_whitespace(enabled).collect();
        let mut table: Vec<Toolkit> = defaults()
            .into_iter()
            .filter(|t| enabled.is_empty() || enabled.contains(&t.name.as_str()))
            .collect();

        // Merge the repo's overrides
        let Some(Value::Dict(over)) = cfg.get("toolkits") else {
            return Table(table);
        };
        for (name, value) in over.iter() {
            let Value::Dict(extra) = value else { continue };
            match table.iter_mut().find(|t| t.name == name) {
                Some(t) => {
                    for (k, v) in extra.iter() {
                        t.spec.insert(k, v.clone());
                    }
                }
                None => table.push(Toolkit {
                    name: name.to_owned(),
                    spec: extra.clone(),
                }),
            }
        }
        Table(table)
    }

    /// python `toolkit_of(name, table)`: 파일 이름의 확장자를 가진 첫 툴킷. 생성물 접미사면 `None`.
    pub fn of(&self, name: &str) -> Result<Option<&Toolkit>> {
        let ext = splitext(name).1;
        for t in &self.0 {
            match t.spec.get("ext") {
                Some(exts) if exts.truthy() && contains(exts, ext)? => {}
                _ => continue,
            }
            return Ok(if t.skips(name)? { None } else { Some(t) });
        }
        Ok(None)
    }
}

impl Toolkit {
    // python name.endswith(tuple(skip_suffix)): 앞에서부터, 맞으면 거기서 멈추고 글이 아닌 원소는 TypeError
    fn skips(&self, name: &str) -> Result<bool> {
        for suffix in items_or_empty(self.spec.get("skip_suffix"))? {
            let suffix = suffix
                .as_str()
                .ok_or(Halt::PyError("endswith with a non-string suffix"))?;
            if name.ends_with(suffix) {
                return Ok(true);
            }
        }
        Ok(false)
    }

    /// python `set(spec.get("skip_parts") or [])` 가운데 글. 목록이나 dict 원소는 set 에 넣지 못해 TypeError.
    pub fn skip_parts(&self) -> Result<Vec<String>> {
        let mut out = Vec::new();
        for part in items_or_empty(self.spec.get("skip_parts"))? {
            if !part.hashable() {
                return Err(Halt::PyError("an unhashable skip_parts entry"));
            }
            if let Some(s) = part.as_str() {
                out.push(s.to_owned());
            }
        }
        Ok(out)
    }

    /// python `spec.get("test") and re.search(spec["test"], rel)`.
    pub fn spec_test(&self, rel: &str) -> Result<bool> {
        match self.spec.get("test") {
            Some(Value::Str(pattern)) if !pattern.is_empty() => {
                let re = Regex::new(pattern).map_err(|e| re_halt(&e))?;
                Ok(re.is_match(rel))
            }
            Some(v) if v.truthy() => Err(Halt::PyError("re.search with a non-string pattern")),
            _ => Ok(false),
        }
    }

    /// python `spec.get(x, cfg[x]) * k`: 항목의 기준, 없으면 최상위 기준.
    pub fn limit(&self, key: &str, cfg: &Config, k: i128) -> Result<Limit> {
        let value = self.spec.get(key).unwrap_or_else(|| cfg.item(key));
        Limit::of(value, k)
    }

    /// python `spec.get("comment") or ["--", "//", "#"]`.
    pub fn comments(&self) -> Value {
        match self.spec.get("comment") {
            Some(v) if v.truthy() => v.clone(),
            _ => strs(DEFAULT_COMMENTS),
        }
    }
}

/// 예외 표식 주석들의 정규식 조각(python `re.escape(c) for c in comments`). 글이 아닌 원소는 TypeError.
pub fn comment_marks(comments: &Value) -> Result<Vec<String>> {
    items(comments)?
        .iter()
        .map(|c| {
            c.as_str()
                .map(harness_hook::py::re::escape)
                .ok_or(Halt::PyError("re.escape of a non-string comment"))
        })
        .collect()
}

/// python `comments[0]`: 목록은 첫 원소, 글은 첫 글자, dict 는 KeyError.
pub fn first_comment(comments: &Value) -> Result<String> {
    match comments {
        Value::List(v) => match v.first() {
            Some(Value::Str(s)) => Ok(s.clone()),
            _ => Err(Halt::PyError("comments[0] is not a string")),
        },
        Value::Str(s) => s
            .chars()
            .next()
            .map(String::from)
            .ok_or(Halt::PyError("comments[0] of an empty string")),
        _ => Err(Halt::PyError("comments[0] of a value without index 0")),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use harness_hook::py::json_load::loads;

    fn cfg(json: &str) -> Config {
        Config::from_value(&loads(json).unwrap())
    }

    /// 기본 표는 확장자로 툴킷을 고르고 생성물 접미사는 건너뛴다.
    #[test]
    fn picks_toolkit_by_extension() {
        // The default table
        let table = Table::new(&Config::defaults(), "");
        assert_eq!(
            table.of("A.luau").unwrap().map(|t| t.name.as_str()),
            Some("luau")
        );
        assert_eq!(table.of("types.d.ts").unwrap(), None, "generated suffix");
        assert_eq!(table.of("README.md").unwrap(), None);

        // HARNESS_TOOLKITS keeps only the named toolkits
        let only = Table::new(&Config::defaults(), " luau ");
        assert_eq!(only.of("a.ts").unwrap(), None);
    }

    /// 저장소 덮어쓰기는 키마다 합치고, 새 이름은 뒤에 더한다.
    #[test]
    fn merges_repo_overrides() {
        // web gets .vue and keeps its comment; zz is new
        let cfg = cfg(r#"{"toolkits": {"web": {"ext": [".ts", ".vue"]}, "zz": {"ext": ".zz"}}}"#);
        let table = Table::new(&cfg, "");
        let web = table.of("A.vue").unwrap().unwrap();
        assert_eq!(web.comments(), strs(&["//"]));
        assert_eq!(table.of("a.tsx").unwrap(), None);

        // A string ext is searched as a substring (python `in` on str)
        assert_eq!(
            table.of("b.zz").unwrap().map(|t| t.name.as_str()),
            Some("zz")
        );
        assert_eq!(
            table.of("b.z").unwrap().map(|t| t.name.as_str()),
            Some("zz")
        );
    }

    /// `comments[0]` 과 escape 가 값의 꼴마다 python 과 같다.
    #[test]
    fn comment_values() {
        // A string comment iterates by character
        let text = Value::Str(";;".into());
        assert_eq!(comment_marks(&text).unwrap(), vec![";", ";"]);
        assert_eq!(first_comment(&text).unwrap(), ";");

        // A dict has no index 0
        assert!(first_comment(&loads(r#"{"--": 1}"#).unwrap()).is_err());
        assert!(comment_marks(&loads("[1]").unwrap()).is_err());
    }
}
