//! 원장 파일 `<임시 폴더>/claude-subagent-slots/<sid>.json`(+ `.lock`, `.limits.json`)을 잠그고 읽고 쓴다
//! (python `subagent_ledger.state_path`, `read`, `session`, `read_limits`).
//!
//! python 판(이 훅, `/q:away` CLI, statusline)과 같은 파일을 번갈아 쓰므로 값은 python 이 쓴 그대로 [`Dict`] 로 든다.

use std::fs::{File, OpenOptions};

use harness_hook::epoch::sanitize;
use harness_hook::py::fs::{os_path, read_bytes};
use harness_hook::py::json::{EnsureAscii, dumps_dict};
use harness_hook::py::json_load::{self, Decode};
use harness_hook::py::path::join;
use harness_hook::py::repr::truthy_str;
use harness_hook::py::value::{Dict, Value};

use crate::pyval::replace_file;
use crate::stop::{Result, Stop};

/// 원장 폴더 이름(python `NS`).
pub const NAMESPACE: &str = "claude-subagent-slots";
/// 원장에 남기는 사건 줄의 최대 수.
const LOG_KEEP: usize = 200;

/// python `state_dir()`: 폴더를 만든다. 만들지 못하면 python 은 예외로 끝난다.
pub fn state_dir(tempdir: &str) -> Result<String> {
    let dir = join(tempdir, NAMESPACE);
    let os = os_path(&dir).ok_or(Stop::Raises("bad state folder"))?;
    std::fs::create_dir_all(os).map_err(|_| Stop::Raises("cannot make the state folder"))?;
    Ok(dir)
}

/// python `_sid(sid)`: `str(sid or "nosession")` 의 단어 글자와 `-`.
pub fn sid_name(session_id: Option<&Value>) -> String {
    sanitize(&truthy_str(session_id))
}

/// python `blank()`: 새 원장.
pub fn blank() -> Dict {
    let empty = || Value::Dict(Dict::new());
    let spent = Dict::from_pairs(vec![
        ("main".to_owned(), empty()),
        ("sub".to_owned(), empty()),
    ]);
    Dict::from_pairs(vec![
        ("reserved".to_owned(), empty()),
        ("running".to_owned(), empty()),
        ("agents".to_owned(), empty()),
        ("spent".to_owned(), Value::Dict(spent)),
        ("main".to_owned(), empty()),
        ("away".to_owned(), Value::Null),
        ("spawned".to_owned(), Value::Int(0)),
        ("notes".to_owned(), empty()),
        ("burst".to_owned(), Value::Int(0)),
        ("log".to_owned(), Value::List(Vec::new())),
    ])
}

/// 잠근 원장 하나(python `session(sid)` 의 with 블록). [`Session::save`] 하지 않고 버리면 python 의 예외 자리처럼 쓰지 않는다.
pub struct Session {
    path: String,
    /// 잡은 잠금 파일. 닫으면 풀린다.
    _lock: File,
}

impl Session {
    /// 잠금을 잡고(기다린다) 원장을 읽는다. 읽지 못하면 [`blank`], 빠진 키는 [`blank`] 의 값으로 채운다.
    pub fn open(tempdir: &str, session_id: Option<&Value>) -> Result<(Session, Dict)> {
        let path = join(
            &state_dir(tempdir)?,
            &format!("{}.json", sid_name(session_id)),
        );
        let lock = lock(&format!("{path}.lock"))?;

        // python json.load(open(p)) under except Exception
        let loaded = read_bytes(&path)
            .ok()
            .and_then(|bytes| json_load::from_bytes(&bytes, Decode::Strict).ok());
        let mut st = match loaded {
            None => blank(),
            Some(value) => value
                .into_dict()
                .map_err(|_| Stop::Raises("st.setdefault on a ledger that is not a dict"))?,
        };
        for (key, value) in blank().iter() {
            st.setdefault(key, value.clone());
        }
        Ok((Session { path, _lock: lock }, st))
    }

    /// 블록 끝: 사건 줄을 [`LOG_KEEP`] 개로 자르고 `<path>.tmp` 에 쓴 뒤 바꿔 넣는다(python `json.dump(st, f)`).
    pub fn save(self, st: &mut Dict) -> Result<()> {
        let kept = match st.get("log") {
            Some(Value::List(items)) => Value::List(tail(items.clone(), LOG_KEEP)),
            Some(Value::Str(text)) => {
                let chars: Vec<char> = text.chars().collect();
                Value::Str(
                    chars[chars.len().saturating_sub(LOG_KEEP)..]
                        .iter()
                        .collect(),
                )
            }
            _ => return Err(Stop::Raises("slicing a log that is not a list")),
        };
        st.insert("log", kept);
        replace_file(
            &self.path,
            Some(&format!("{}.tmp", self.path)),
            &dumps_dict(st, EnsureAscii::Yes, None),
        )
    }
}

fn tail(mut items: Vec<Value>, keep: usize) -> Vec<Value> {
    let cut = items.len().saturating_sub(keep);
    items.split_off(cut)
}

// python file_lock.lock(open(p, "w")): 배타 flock 을 잡을 때까지 기다린다. flock 이 없는 플랫폼은 잠그지 않는다
fn lock(path: &str) -> Result<File> {
    let os = os_path(path).ok_or(Stop::Raises("bad lock path"))?;
    let file = OpenOptions::new()
        .write(true)
        .create(true)
        .truncate(true)
        .open(os)
        .map_err(|_| Stop::Raises("cannot open the lock file"))?;
    #[cfg(unix)]
    rustix::fs::flock(&file, rustix::fs::FlockOperation::LockExclusive)
        .map_err(|_| Stop::Raises("flock failed"))?;
    Ok(file)
}

/// python `read_limits(sid)`: statusline 이 쓴 한도 값(`"t"` 가 있는 dict), 없거나 읽지 못하면 `None`.
pub fn read_limits(tempdir: &str, session_id: Option<&Value>) -> Option<Dict> {
    let dir = state_dir(tempdir).ok()?;
    let path = join(&dir, &format!("{}.limits.json", sid_name(session_id)));
    let bytes = read_bytes(&path).ok()?;
    let value = json_load::from_bytes(&bytes, Decode::Strict).ok()?;
    value.into_dict().ok().filter(|d| d.get("t").is_some())
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 새 원장의 키 순서는 python `blank()` 와 같다.
    #[test]
    fn blank_like_python() {
        let text = dumps_dict(&blank(), EnsureAscii::Yes, None);
        assert_eq!(
            text,
            r#"{"reserved": {}, "running": {}, "agents": {}, "spent": {"main": {}, "sub": {}}, "main": {}, "away": null, "spawned": 0, "notes": {}, "burst": 0, "log": []}"#
        );
    }
}
