//! 세션 상태(알렸는지)와 성장 기준점 파일. python 판과 같은 바이트로 읽고 써서 두 판이 번갈아 돌아도 알림이 겹치지 않는다.
//!
//! - 상태: `$TMPDIR/claude-structure-reminder/<sid>.c<회차>[.a<agent>].json`, compact 회차마다 새로 시작한다.
//!   `{"files": {<경로>: {"base": N, "said": [...]}}, "dirs": [...], "ref_said": true}`
//! - 기준점: `$TMPDIR/claude-structure-reminder/<sid>.base.json`, session_id 단위라 compact 뒤에도 남는다. `{<경로>: N}`
//!
//! 값은 읽은 JSON 그대로 들고 python 이 쓰는 연산만 한다. 꼴이 틀린 파일은 python 이 예외를 내는 자리에서 같이 끝난다.

use harness_hook::epoch;
use harness_hook::py::fs::{self, FsError};
use harness_hook::py::json::{EnsureAscii, dumps};
use harness_hook::py::json_load::loads;
use harness_hook::py::path::join;
use harness_hook::py::value::{Dict, Value};

use super::num::Num;
use super::pyops::{append, contains};
use crate::context::{Context, PLUGIN};
use crate::halt::{Halt, Result};

/// 상태 폴더 이름(python `dedup_path` 의 namespace).
pub const NAMESPACE: &str = "claude-structure-reminder";

/// 이 실행이 읽고 쓰는 두 파일.
#[derive(Debug)]
pub struct Ledger {
    state: Value,
    bases: Value,
    n_bases: usize,
    state_path: String,
    base_path: String,
}

// python json.load(open(path)): 무엇이 잘못되든 {}
fn read_json(path: &str) -> Value {
    fs::read_text(path)
        .ok()
        .and_then(|text| loads(&text).ok())
        .unwrap_or_else(|| Value::Dict(Dict::new()))
}

// python len(x): dict, 목록, 글만
fn py_len(value: &Value) -> Result<usize> {
    match value {
        Value::Dict(d) => Ok(d.len()),
        Value::List(v) => Ok(v.len()),
        Value::Str(s) => Ok(s.chars().count()),
        _ => Err(Halt::PyError("len() of a value without a length")),
    }
}

fn fs_halt(_: FsError) -> Halt {
    Halt::PyError("cannot make the state folder")
}

impl Ledger {
    /// 두 파일을 읽는다. `session_id`, `agent_id` 는 python 에서 참인 값의 `str()` 이다.
    ///
    /// 폴더를 만들지 못하거나 기준점 파일이 길이 없는 JSON(수 등)이면 python 은 예외로 끝난다.
    pub fn load(ctx: &Context, session_id: Option<&str>, agent_id: Option<&str>) -> Result<Ledger> {
        let tmp = ctx.tempdir()?;
        let sid = session_id.unwrap_or("");

        // The per-epoch notice state
        let state_path =
            epoch::state_path(tmp, PLUGIN, NAMESPACE, sid, agent_id).map_err(fs_halt)?;
        let state = read_json(&state_path);

        // The per-session growth baselines
        let dir = join(tmp, NAMESPACE);
        let os = fs::os_path(&dir).ok_or(Halt::PyError("cannot make the state folder"))?;
        std::fs::create_dir_all(os).map_err(|_| Halt::PyError("cannot make the state folder"))?;
        let base_path = join(&dir, &format!("{}.base.json", epoch::sanitize(sid)));
        let bases = read_json(&base_path);
        let n_bases = py_len(&bases)?;

        Ok(Ledger {
            state,
            bases,
            n_bases,
            state_path,
            base_path,
        })
    }

    /// python `json.dump(state, ...)`, 기준점이 늘었으면 그것도. 쓰기 실패(OSError)는 넘긴다.
    pub fn save(&self) -> Result<()> {
        let write = |path: &str, value: &Value| match fs::write_text(
            path,
            &dumps(value, EnsureAscii::Yes, None),
        ) {
            Ok(()) => Ok(true),
            Err(FsError::Os(_)) => Ok(false),
            Err(FsError::Value) => Err(Halt::PyError("a state path python cannot open")),
        };
        if write(&self.state_path, &self.state)? && py_len(&self.bases)? != self.n_bases {
            write(&self.base_path, &self.bases)?;
        }
        Ok(())
    }

    /// python `path in state.get("files", {})`.
    pub fn knows_file(&self, path: &str) -> Result<bool> {
        match self.state_dict_ref()?.get("files") {
            Some(files) => contains(files, path),
            None => Ok(false),
        }
    }

    /// python check_file 의 `setdefault` 와 새 항목: 이 파일의 항목이 없으면 기준점과 함께 만든다.
    ///
    /// `new_base` 는 기준점 파일에도 없을 때만 부른다(python 은 그때만 `added_lines` 를 센다).
    pub fn open_entry(
        &mut self,
        path: &str,
        new_base: impl FnOnce() -> Result<i128>,
    ) -> Result<()> {
        // State keys in python's setdefault order
        let Value::Dict(state) = &mut self.state else {
            return Err(Halt::PyError("the state file is not a JSON object"));
        };
        state.setdefault("files", Value::Dict(Dict::new()));
        state.setdefault("dirs", Value::List(Vec::new()));
        let Some(Value::Dict(files)) = state.get_mut("files") else {
            return Err(Halt::PyError("state files is not a dict"));
        };
        if !matches!(files.get(path), None | Some(Value::Null)) {
            return Ok(());
        }

        // A baseline kept across compacts, else a new one
        if !contains(&self.bases, path)? {
            let base = new_base()?;
            let Value::Dict(bases) = &mut self.bases else {
                return Err(Halt::PyError(
                    "item assignment on a baseline file that is not a dict",
                ));
            };
            bases.insert(path, Value::Int(base.max(0)));
        }
        let Value::Dict(bases) = &self.bases else {
            return Err(Halt::PyError("baselines is not a dict"));
        };
        let base = bases.get(path).cloned().unwrap_or(Value::Null);

        let entry = Dict::from_pairs(vec![
            ("base".to_owned(), base),
            ("said".to_owned(), Value::List(Vec::new())),
        ]);
        files.insert(path, Value::Dict(entry));
        Ok(())
    }

    /// python `entry["said"]`(알린 종류 목록)의 사본.
    pub fn said(&self, path: &str) -> Result<Value> {
        self.entry(path)?
            .get("said")
            .cloned()
            .ok_or(Halt::PyError("KeyError: said"))
    }

    /// 바꾼 `said` 를 항목에 되돌려 놓는다.
    pub fn set_said(&mut self, path: &str, said: Value) -> Result<()> {
        if let Some(Value::Dict(files)) = self.state_dict()?.get_mut("files")
            && let Some(Value::Dict(entry)) = files.get_mut(path)
        {
            entry.insert("said", said);
        }
        Ok(())
    }

    /// python `entry["base"]` 와 그 `str()`. 수가 아니면 python 은 `n - base` 에서 끝난다.
    pub fn base(&self, path: &str) -> Result<(Num, String)> {
        let value = self
            .entry(path)?
            .get("base")
            .ok_or(Halt::PyError("KeyError: base"))?;
        let num = Num::of(value)?.ok_or(Halt::PyError("a baseline that is not a number"))?;
        Ok((num, value.scalar_str().unwrap_or_default()))
    }

    /// python `seen_dirs`(알린 폴더와 접두 묶음).
    pub fn seen_dirs(&self) -> Result<&Value> {
        self.state_dict_ref()?
            .get("dirs")
            .ok_or(Halt::PyError("KeyError: dirs"))
    }

    /// python `seen_dirs.append(key)`.
    pub fn see_dir(&mut self, key: &str) -> Result<()> {
        let dirs = self
            .state_dict()?
            .get_mut("dirs")
            .ok_or(Halt::PyError("KeyError: dirs"))?;
        append(dirs, key)
    }

    /// 기준 문서 안내를 이 회차에 이미 했는가. 했다고 적는다.
    pub fn take_ref(&mut self) -> Result<bool> {
        let state = self.state_dict()?;
        if state.get("ref_said").is_some_and(Value::truthy) {
            return Ok(false);
        }
        state.insert("ref_said", Value::Bool(true));
        Ok(true)
    }

    fn entry(&self, path: &str) -> Result<&Dict> {
        match self.state_dict_ref()?.get("files") {
            Some(Value::Dict(files)) => match files.get(path) {
                Some(Value::Dict(entry)) => Ok(entry),
                _ => Err(Halt::PyError("a state entry that is not a dict")),
            },
            _ => Err(Halt::PyError("state files is not a dict")),
        }
    }

    // python 은 dict 가 아닌 상태에서 `.get`, `.setdefault` 로 끝난다
    fn state_dict(&mut self) -> Result<&mut Dict> {
        match &mut self.state {
            Value::Dict(d) => Ok(d),
            _ => Err(Halt::PyError("the state file is not a JSON object")),
        }
    }

    fn state_dict_ref(&self) -> Result<&Dict> {
        match &self.state {
            Value::Dict(d) => Ok(d),
            _ => Err(Halt::PyError("the state file is not a JSON object")),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use harness_hook::Env;

    /// 새 항목은 기준점을 만들고, 두 파일을 python json.dump 꼴로 쓴다.
    #[test]
    fn writes_python_json() {
        // A fresh session in a private temp dir
        let tmp = std::env::temp_dir().join(format!("structrem-state-{}", std::process::id()));
        std::fs::create_dir_all(&tmp).unwrap();
        let ctx = Context::new(Env::from_pairs([("TMPDIR", tmp.to_str().unwrap())]), None);
        let mut ledger = Ledger::load(&ctx, Some("s1"), None).unwrap();

        // A new entry takes its baseline; a known path keeps it
        ledger.open_entry("/r/a.luau", || Ok(-3)).unwrap();
        ledger
            .open_entry("/r/a.luau", || {
                panic!("an existing entry needs no baseline")
            })
            .unwrap();
        assert_eq!(
            ledger.base("/r/a.luau").unwrap(),
            (Num::Int(0), "0".to_owned()),
            "max(0, base)"
        );
        assert!(ledger.take_ref().unwrap());
        assert!(!ledger.take_ref().unwrap());

        // Both files with python's separators
        ledger.save().unwrap();
        let state = std::fs::read_to_string(tmp.join(NAMESPACE).join("s1.c0.json")).unwrap();
        assert_eq!(
            state,
            r#"{"files": {"/r/a.luau": {"base": 0, "said": []}}, "dirs": [], "ref_said": true}"#
        );
        let bases = std::fs::read_to_string(tmp.join(NAMESPACE).join("s1.base.json")).unwrap();
        assert_eq!(bases, r#"{"/r/a.luau": 0}"#);
        std::fs::remove_dir_all(&tmp).unwrap();
    }
}
