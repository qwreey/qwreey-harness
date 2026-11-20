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
use harness_hook::py::json::{EnsureAscii, dumps};
use harness_hook::py::json_load::{Decode, from_bytes};
use harness_hook::py::num::parse_int;
use harness_hook::py::path::pathlib_join;
use harness_hook::py::surrogate::unit_of;
use harness_hook::py::text::strip;
use harness_hook::py::value::{Dict, Value};

use crate::abort::{Abort, Result};
use crate::date::Date;
use crate::fsx::{self, FsError};
use crate::paths::{project_key, safe_sid};
use crate::pyval::{self, ZERO, greater};

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
        .and_then(|bytes| from_bytes(&bytes, Decode::Strict).ok());
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

    /// `.state/<sid><suffix>`(python `session_file`). 파일 이름에 쓸 수 없는 id 는 python 의 ValueError 자리라 [`Abort`]:
    /// 훅은 그런 id 를 먼저 걸러 조용히 끝낸다([`crate::paths::safe_sid`]).
    pub fn session_file(&self, sid: &str, suffix: &str) -> Result<String> {
        if !safe_sid(sid) {
            return Err(Abort("session id is not a safe file name"));
        }
        Ok(pathlib_join(&self.state, &format!("{sid}{suffix}")))
    }

    /// 워커 상태 파일.
    pub fn wstate_path(&self, sid: &str) -> Result<String> {
        self.session_file(sid, ".json")
    }

    /// 훅 상태 파일.
    pub fn hstate_path(&self, sid: &str) -> Result<String> {
        self.session_file(sid, ".hook.json")
    }

    /// 기록 파일.
    pub fn record_path(&self, rid: &str) -> String {
        pathlib_join(&self.records, &format!("{rid}.md"))
    }

    /// 훅 상태를 쓴다(python `save_hstate`).
    pub fn save_hstate(&self, sid: &str, state: &Value) -> Result<()> {
        let path = self.hstate_path(sid)?;
        mkdir_all(&self.state)?;
        write_json(&path, state)
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
            let Ok(notice) = harness_hook::py::json_load::loads(line) else {
                continue;
            };
            let Ok(notice) = notice.into_dict() else {
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
        let Ok(index) = self.index().into_dict() else {
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
        sort_by_created(&mut out);
        Ok(out)
    }

    /// pending 요약(python `pending_summary`). 기록이 없으면 `None`.
    pub fn pending_summary(&self) -> Result<Option<PendingSummary>> {
        let pending = self.pending()?;
        let Some(first) = pending.first() else {
            return Ok(None);
        };

        // 가장 오래된 기록의 날짜와 나이. 글이 아니면 빈 날짜, 날짜를 읽지 못하면 0 일
        let oldest: String = match &first.created {
            Value::Str(created) => created.chars().take(10).collect(),
            _ => String::new(),
        };
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
static NULL: Value = Value::Null;

/// python `Store.is_pending(e)`.
fn is_pending(entry: &Value) -> Result<bool> {
    let status = pyval::get(entry, "status", &NULL, "index entry")?;
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

// python `list.sort(key=lambda e: created_order(e.get("created", "")))`(안정 정렬)
fn sort_by_created(items: &mut [PendingRecord]) {
    items.sort_by(|a, b| created_order(&a.created, &b.created));
}

/// python `store.created_order` 의 순서: 글(코드 포인트 순), 수(float 로 견준다, bool 도 수), NaN, 그 밖(서로 같다).
///
/// 꼴이 섞인 index 에서도 순서가 정해진다. i128 밖의 정수는 python 처럼 float 로 바꿔 견준다(넘치면 무한대).
pub fn created_order(a: &Value, b: &Value) -> Ordering {
    match (created_rank(a), created_rank(b)) {
        (Rank::Text(x), Rank::Text(y)) => x.chars().map(py_code).cmp(y.chars().map(py_code)),
        (Rank::Number(x), Rank::Number(y)) => x.partial_cmp(&y).expect("NaN has its own rank"),
        (x, y) => x.group().cmp(&y.group()),
    }
}

enum Rank<'a> {
    Text(&'a str),
    Number(f64),
    NaN,
    Other,
}

impl Rank<'_> {
    fn group(&self) -> u8 {
        match self {
            Rank::Text(_) => 0,
            Rank::Number(_) => 1,
            Rank::NaN => 2,
            Rank::Other => 3,
        }
    }
}

fn created_rank(v: &Value) -> Rank<'_> {
    let number = match v {
        Value::Str(s) => return Rank::Text(s),
        Value::Bool(b) => f64::from(u8::from(*b)),
        Value::Int(i) => *i as f64,
        Value::BigInt(digits) => digits.parse().unwrap_or(f64::NAN),
        Value::Float(f) => *f,
        _ => return Rank::Other,
    };
    if number.is_nan() {
        Rank::NaN
    } else {
        Rank::Number(number)
    }
}

// python 의 코드 포인트(서로게이트 자리표는 그 서로게이트)
fn py_code(c: char) -> u32 {
    unit_of(c).unwrap_or(u32::from(c))
}

/// python `Path.mkdir(parents=True, exist_ok=True)`.
pub fn mkdir_all(dir: &str) -> Result<()> {
    let os = fsx::os_path(dir).ok_or(Abort("unencodable state dir"))?;
    fs::create_dir_all(os).map_err(|_| Abort("cannot create state dir"))
}

/// python `write_json(path, obj)`: `json.dumps(obj, ensure_ascii=False, indent=1)` 를 [`atomic_write`].
pub fn write_json(path: &str, value: &Value) -> Result<()> {
    atomic_write(path, &dumps(value, EnsureAscii::No, Some(1)))
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
        assert_eq!(
            store.hstate_path("s").unwrap(),
            "/h/-r-x-y/.state/s.hook.json"
        );
        assert!(store.hstate_path("../x").is_err());
        assert_eq!(store.record_path("a//b"), "/h/-r-x-y/records/a/b.md");
    }

    #[test]
    fn sorts_created_like_python() {
        let values = [
            Value::Int(3),
            Value::Str("b".into()),
            Value::Null,
            Value::Float(f64::NAN),
            Value::Float(1.5),
            Value::Bool(true),
            Value::Str("a".into()),
            Value::BigInt("1".repeat(400)),
            Value::List(vec![]),
        ];
        let mut items: Vec<PendingRecord> = values
            .iter()
            .map(|v| PendingRecord { created: v.clone() })
            .collect();
        sort_by_created(&mut items);

        // python: sorted([...], key=created_order)
        let got: Vec<String> = items
            .iter()
            .map(|p| p.created.scalar_str().unwrap_or_else(|| "[]".into()))
            .collect();
        let big = "1".repeat(400);
        assert_eq!(
            got,
            [
                "a",
                "b",
                "True",
                "1.5",
                "3",
                big.as_str(),
                "nan",
                "None",
                "[]"
            ]
        );
    }
}
