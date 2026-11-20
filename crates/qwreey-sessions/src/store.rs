//! 외부 저장소 `${SESSION_LOG_HOME}/<project-key>/` (python `sllib/store.py` 의 훅이 쓰는 쪽).
//!
//! ```text
//! records/<rid>.md         세션 기록
//! index.json               rid -> 상태(pending|imported|dismissed), 절 수, 만든 때
//! .state/<sid>.json        워커 상태(바이트 오프셋, 줄 수, 마지막 실행)
//! .state/<sid>.hook.json   훅 상태(알림 커서, 이미 한 알림, 마지막 띄움)
//! .state/notices.jsonl, notice.seq   요약 완료 알림 큐(워커가 쓴다)
//! ```
//! python 워커와 훅이 같은 파일을 읽고 쓴다. 쓰는 것은 훅 상태 하나이고 꼴은 python 과 같다:
//! `json.dumps(ensure_ascii=False, indent=1)` 를 nonce 를 지운 뒤 임시 파일(0600)에 써서 바꿔 놓는다.

use std::cmp::Ordering;
use std::fs::{self, OpenOptions};
use std::io::{ErrorKind, Write};

use harness_hook::nonce::redact_text;
use harness_hook::py::json::{EnsureAscii, to_string_indented};
use harness_hook::py::num::parse_int;
use harness_hook::py::path::pathlib_join;
use harness_hook::py::surrogate::{json_from_slice, unit_of};
use harness_hook::py::text::strip;
use harness_hook::py::value::{Dict, Value};

use crate::abort::{Abort, Result};
use crate::date::Date;
use crate::fsx::{self, FsError};
use crate::paths::project_key;
use crate::pyval::{self, Num, ZERO, greater};

/// 한 저장소의 외부 저장소 자리. 경로는 모두 python `str(Path)` 꼴이다.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Store {
    pub root: String,
    pub key: String,
    pub dir: String,
    pub records: String,
    pub state: String,
}

/// 받아 가지 않은 기록(python `pending()` 의 한 항목). 훅은 만든 때만 본다.
#[derive(Clone, Debug, PartialEq)]
pub struct PendingRecord {
    pub created: Value,
}

/// pending 요약: 개수, 가장 오래된 날짜 글(앞 10자), 그 나이(일).
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct PendingSummary {
    pub count: usize,
    pub oldest: String,
    pub days: i64,
}

/// python `read_json(path)`: 읽지 못하거나 JSON 이 아니면 `{}`. dict 가 아닌 JSON 도 그대로 준다.
pub fn read_json(path: &str) -> Value {
    let parsed = fsx::os_path(path)
        .and_then(|os| fs::read(os).ok())
        .and_then(|bytes| json_from_slice::<Value>(&bytes).ok());
    parsed.unwrap_or_else(|| Value::Dict(Dict::new()))
}

impl Store {
    /// 저장소 루트 `root` 의 자리. `home` 은 [`crate::config::Config::home`].
    pub fn new(root: String, home: &str) -> Store {
        let key = project_key(&root);
        let dir = pathlib_join(home, &key);
        let records = pathlib_join(&dir, "records");
        let state = pathlib_join(&dir, ".state");
        Store {
            root,
            key,
            dir,
            records,
            state,
        }
    }

    /// 외부 저장소가 있나.
    pub fn exists(&self) -> bool {
        fsx::is_dir(&self.dir)
    }

    /// 워커 상태 파일. `sid` 는 python `f"{sid}"` 글이다(정리하지 않는다: python 판과 같은 자리).
    pub fn wstate_path(&self, sid: &str) -> String {
        pathlib_join(&self.state, &format!("{sid}.json"))
    }

    /// 훅 상태 파일.
    pub fn hstate_path(&self, sid: &str) -> String {
        pathlib_join(&self.state, &format!("{sid}.hook.json"))
    }

    /// 기록 파일.
    pub fn record_path(&self, rid: &str) -> String {
        pathlib_join(&self.records, &format!("{rid}.md"))
    }

    /// 훅 상태를 쓴다(python `save_hstate`).
    pub fn save_hstate(&self, sid: &str, state: &Value) -> Result<()> {
        mkdir_all(&self.state)?;
        write_json(&self.hstate_path(sid), state)
    }

    /// 알림 큐의 마지막 번호(python `notice_seq`). 읽지 못하면 0.
    pub fn notice_seq(&self) -> i128 {
        match fsx::read_text(&pathlib_join(&self.state, "notice.seq")) {
            Ok(text) if strip(&text).is_empty() => 0,
            Ok(text) => parse_int(&text).unwrap_or(0),
            Err(_) => 0,
        }
    }

    /// 번호가 `seq` 보다 큰 알림(python `notices_after`). 줄마다 JSON 하나, 읽지 못한 줄은 건너뛴다.
    ///
    /// 파일이 UTF-8 이 아니거나 알림이 dict 가 아니면 python 은 예외로 끝난다.
    pub fn notices_after(&self, seq: &Value) -> Result<Vec<Dict>> {
        let text = match fsx::read_text(&pathlib_join(&self.state, "notices.jsonl")) {
            Ok(text) => text,
            Err(FsError::Os(_)) => return Ok(Vec::new()),
            Err(FsError::Value) => return Err(Abort("notices.jsonl is not UTF-8")),
        };

        // 줄마다 알림 하나
        let mut out = Vec::new();
        for line in text.split_inclusive('\n') {
            let Ok(notice) = json_from_slice::<Value>(line.as_bytes()) else {
                continue;
            };
            let Value::Dict(notice) = notice else {
                return Err(Abort("notice is not a dict"));
            };
            if greater(notice.get("seq").unwrap_or(&ZERO), seq, "notice seq")? {
                out.push(notice);
            }
        }
        Ok(out)
    }

    /// 기록 목록(python `index()`): rid -> 항목.
    pub fn index(&self) -> Value {
        read_json(&pathlib_join(&self.dir, "index.json"))
    }

    /// 받아 가지 않은 기록, 만든 때 순서(python `pending()`).
    pub fn pending(&self) -> Result<Vec<PendingRecord>> {
        let Value::Dict(index) = self.index() else {
            return Err(Abort("index.json is not a dict"));
        };
        let mut out = Vec::new();
        for (_, entry) in index.iter() {
            if is_pending(entry)? {
                let created = pyval::get(entry, "created", &EMPTY, "index entry")?;
                out.push(PendingRecord {
                    created: created.clone(),
                });
            }
        }
        sort_by_created(&mut out)?;
        Ok(out)
    }

    /// pending 요약(python `pending_summary`). 기록이 없으면 `None`.
    pub fn pending_summary(&self) -> Result<Option<PendingSummary>> {
        let pending = self.pending()?;
        let Some(first) = pending.first() else {
            return Ok(None);
        };

        // 가장 오래된 기록의 날짜와 나이. 날짜를 읽지 못하면 0 일
        let Value::Str(created) = &first.created else {
            return Err(Abort("created is not a string"));
        };
        let oldest: String = created.chars().take(10).collect();
        let today = Date::today().ok_or(Abort("no local date"))?;
        let days = Date::fromisoformat(&oldest).map_or(0, |d| today.days_since(d));
        Ok(Some(PendingSummary {
            count: pending.len(),
            oldest,
            days,
        }))
    }
}

static EMPTY: Value = Value::Str(String::new());

/// python `Store.is_pending(e)`.
fn is_pending(entry: &Value) -> Result<bool> {
    let status = pyval::get(entry, "status", &Value::Null, "index entry")?;
    match status.as_str() {
        Some("dismissed") => Ok(false),
        Some("imported") => greater(
            pyval::get(entry, "sections", &ZERO, "index entry")?,
            pyval::get(entry, "imported_sections", &ZERO, "index entry")?,
            "sections",
        ),
        _ => Ok(true),
    }
}

// python `list.sort(key=created)`: 글끼리, 수끼리는 비교하고, 섞였으면 TypeError. 하나 이하면 비교하지 않는다
fn sort_by_created(items: &mut [PendingRecord]) -> Result<()> {
    if items.len() <= 1 {
        return Ok(());
    }

    // 모두 글
    if items.iter().all(|p| matches!(p.created, Value::Str(_))) {
        items.sort_by(|a, b| a.created.as_str().cmp(&b.created.as_str()));
        return Ok(());
    }

    // 모두 수(NaN 은 python 이 순서 없이 두므로 옮기지 않았다)
    let comparable = items
        .iter()
        .all(|p| Num::of(&p.created).is_some_and(|n| n.compare(n).is_some()));
    if !comparable {
        return Err(Abort("created values do not compare"));
    }
    items.sort_by(|a, b| {
        let (Some(x), Some(y)) = (Num::of(&a.created), Num::of(&b.created)) else {
            return Ordering::Equal;
        };
        x.compare(y).unwrap_or(Ordering::Equal)
    });
    Ok(())
}

/// python `Path.mkdir(parents=True, exist_ok=True)`.
pub fn mkdir_all(dir: &str) -> Result<()> {
    let os = fsx::os_path(dir).ok_or(Abort("unencodable state dir"))?;
    fs::create_dir_all(os).map_err(|_| Abort("cannot create state dir"))
}

/// python `write_json(path, obj)`: `json.dumps(obj, ensure_ascii=False, indent=1)` 를 [`atomic_write`].
pub fn write_json(path: &str, value: &Value) -> Result<()> {
    let text =
        to_string_indented(value, EnsureAscii::No, 1).map_err(|_| Abort("state is not JSON"))?;
    atomic_write(path, &text)
}

/// python `atomic_write(path, text)`: nonce 를 지우고, 같은 폴더의 임시 파일(0600)에 쓴 뒤 바꿔 놓는다.
///
/// 짝 없는 서로게이트가 든 글은 python 이 UTF-8 로 쓰지 못한다(UnicodeEncodeError): 임시 파일을 지우고 끝낸다.
pub fn atomic_write(path: &str, text: &str) -> Result<()> {
    let text = redact_text(text, None);
    let (dir, name) = match path.rfind('/') {
        Some(i) => (&path[..i.max(1)], &path[i + 1..]),
        None => (".", path),
    };
    mkdir_all(dir)?;

    // 임시 파일 만들기(python mkstemp)
    let (tmp, mut file) = create_temp(dir, name)?;
    let written = if text.chars().any(|c| unit_of(c).is_some()) {
        Err(Abort("state text has a lone surrogate"))
    } else {
        file.write_all(text.as_bytes())
            .map_err(|_| Abort("cannot write state"))
    };
    drop(file);

    // 바꿔 놓기, 실패하면 임시 파일을 지운다
    let target = fsx::os_path(path).ok_or(Abort("unencodable state path"));
    let moved = written
        .and(target)
        .and_then(|target| fs::rename(&tmp, target).map_err(|_| Abort("cannot replace state")));
    if moved.is_err() {
        let _ = fs::remove_file(&tmp);
    }
    moved
}

const TEMP_CHARS: &[u8] = b"abcdefghijklmnopqrstuvwxyz0123456789_";
const TEMP_TRIES: usize = 100;

// `.<name>.` 로 시작하는 새 파일(O_EXCL, 0600)
fn create_temp(dir: &str, name: &str) -> Result<(std::path::PathBuf, fs::File)> {
    for _ in 0..TEMP_TRIES {
        let candidate = pathlib_join(dir, &format!(".{name}.{}", random_suffix()));
        let os = fsx::os_path(&candidate).ok_or(Abort("unencodable temp path"))?;
        let mut options = OpenOptions::new();
        options.write(true).create_new(true);
        #[cfg(unix)]
        std::os::unix::fs::OpenOptionsExt::mode(&mut options, 0o600);
        match options.open(&os) {
            Ok(file) => return Ok((os, file)),
            Err(e) if e.kind() == ErrorKind::AlreadyExists => continue,
            Err(_) => return Err(Abort("cannot create temp file")),
        }
    }
    Err(Abort("no free temp name"))
}

fn random_suffix() -> String {
    let mut raw = [0u8; 8];
    if getrandom::fill(&mut raw).is_err() {
        // 난수가 없으면 시각과 pid. 겹치면 다음 이름을 만든다
        let nanos = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map_or(0, |d| d.subsec_nanos());
        raw = u64::from(nanos ^ std::process::id()).to_le_bytes();
    }
    raw.iter()
        .map(|b| char::from(TEMP_CHARS[usize::from(*b) % TEMP_CHARS.len()]))
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn paths_follow_pathlib() {
        let store = Store::new("/r/x.y".to_owned(), "/h/");
        assert_eq!(store.dir, "/h/-r-x-y");
        assert_eq!(store.hstate_path("s"), "/h/-r-x-y/.state/s.hook.json");
        assert_eq!(store.record_path("a//b"), "/h/-r-x-y/records/a/b.md");
    }

    #[test]
    fn sorts_created_like_python() {
        let mut items: Vec<PendingRecord> = ["b", "a"]
            .iter()
            .map(|s| PendingRecord {
                created: Value::Str((*s).to_owned()),
            })
            .collect();
        sort_by_created(&mut items).unwrap();
        assert_eq!(items[0].created, Value::Str("a".to_owned()));

        // 글과 수가 섞이면 python 은 TypeError
        let mut mixed = vec![
            PendingRecord {
                created: Value::Int(1),
            },
            PendingRecord {
                created: Value::Str("a".to_owned()),
            },
        ];
        assert!(sort_by_created(&mut mixed).is_err());
    }
}
