//! 저장소 단위 색인 `<임시 폴더>/claude-qwreey-reuse/<sha1(루트)[:12]>.json`(python reuse-check 의 `load_index`, `save_index`).
//!
//! python 과 같은 꼴로 읽고 쓴다: `{"v":2,"files":{rel:[mtime_ns,size,묶음들,표시들]}}`, 구분자 `,` `:`, ASCII 밖 글자는 그대로.
//! 두 판이 같은 파일을 번갈아 고친다. 이 판이 쓰는 꼴이 아닌 항목(손으로 고친 파일)은 [`Halt::Unported`] 로 넘긴다.
//! 파일 순서는 python dict 처럼 넣은 차례다. 있던 파일을 다시 읽으면 자리는 그대로다.

use std::collections::{HashMap, HashSet};

use harness_hook::py::fs::{self, FsError};
use harness_hook::py::json::{EnsureAscii, dumps_compact};
use harness_hook::py::json_load::loads;
use harness_hook::py::path::join;
use harness_hook::py::surrogate::unit_of;
use harness_hook::py::value::{Dict, Value};
use sha1::{Digest, Sha1};

use crate::edit::MAX_BYTES;
use crate::halt::{Halt, Result};
use crate::lex::{Family, family};
use crate::reuse::Clock;
use crate::reuse::files::{ext_of, generated};
use crate::reuse::sets::{Budget, Deadline, Mark, MarkKind, StringSet, extract_within};

/// 색인 판(python `INDEX_VERSION`). 2 부터 표시에 영역 사본(`"r"`)이 든다. 다른 판은 새로 만든다.
pub const INDEX_VERSION: i128 = 2;
/// 첫 색인은 여기서 끊고 다음 편집에서 잇는다(python `COLD_MS`).
pub const COLD_MS: f64 = 300.0;

/// 파일 하나의 항목(python `[mtime_ns, size, 묶음, 표시]`). 생성 파일은 묶음과 표시가 비었다.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Entry {
    pub mtime_ns: i128,
    pub size: i128,
    pub sets: Vec<StringSet>,
    pub marks: Vec<Mark>,
}

/// 넣은 차례를 지키는 rel -> 항목.
#[derive(Clone, Debug, Default)]
pub struct Index {
    entries: Vec<(String, Entry)>,
    slot: HashMap<String, usize>,
}

impl Index {
    /// `ents.get(rel)`.
    pub fn get(&self, rel: &str) -> Option<&Entry> {
        self.slot.get(rel).map(|&i| &self.entries[i].1)
    }

    /// `rel in ents`.
    pub fn contains(&self, rel: &str) -> bool {
        self.slot.contains_key(rel)
    }

    /// `ents[rel] = entry`: 있던 키는 자리를 지킨다.
    pub fn insert(&mut self, rel: &str, entry: Entry) {
        match self.slot.get(rel) {
            Some(&i) => self.entries[i].1 = entry,
            None => {
                self.slot.insert(rel.to_owned(), self.entries.len());
                self.entries.push((rel.to_owned(), entry));
            }
        }
    }

    /// 넣은 차례로.
    pub fn iter(&self) -> impl Iterator<Item = (&str, &Entry)> {
        self.entries.iter().map(|(k, e)| (k.as_str(), e))
    }

    // live 에 없는 파일을 지운다. 지운 것이 있으면 true
    fn retain(&mut self, live: &HashSet<&str>) -> bool {
        let before = self.entries.len();
        self.entries.retain(|(k, _)| live.contains(k.as_str()));
        if self.entries.len() == before {
            return false;
        }
        self.slot = self
            .entries
            .iter()
            .enumerate()
            .map(|(i, (k, _))| (k.clone(), i))
            .collect();
        true
    }
}

/// python `index_path(root)`: 폴더를 만든다(못 만들면 python 은 예외로 끝난다).
pub fn index_path(tempdir: &str, root: &str) -> Result<String> {
    let dir = join(tempdir, "claude-qwreey-reuse");
    let os = fs::os_path(&dir).ok_or(Halt::PyError("index folder path is not encodable"))?;
    std::fs::create_dir_all(os).map_err(|_| Halt::PyError("cannot create the index folder"))?;
    Ok(join(&dir, &format!("{}.json", short_sha1(root)?)))
}

/// python `sha1_12(text)`: `hashlib.sha1(text.encode("utf-8", "surrogatepass")).hexdigest()[:12]`.
///
/// 짝 없는 서로게이트(자리표)는 surrogatepass 처럼 세 바이트 `ED xx xx` 로 센다.
pub fn short_sha1(text: &str) -> Result<String> {
    let mut bytes = Vec::with_capacity(text.len());
    for c in text.chars() {
        match unit_of(c) {
            Some(u) => bytes.extend_from_slice(&[
                0xE0 | (u >> 12) as u8,
                0x80 | ((u >> 6) & 0x3F) as u8,
                0x80 | (u & 0x3F) as u8,
            ]),
            None => bytes.extend_from_slice(c.encode_utf8(&mut [0; 4]).as_bytes()),
        }
    }
    let digest = Sha1::digest(&bytes);
    Ok(digest.iter().take(6).map(|b| format!("{b:02x}")).collect())
}

/// [`read_entry`] 가 끝나지 못한 까닭.
#[derive(Debug)]
pub enum ReadError {
    /// 읽지 못했다(python 의 OSError, UnicodeDecodeError).
    Fs,
    /// 한도 안에 다 뽑지 못했다(python `reuse_sets.Budget`).
    Budget,
}

impl From<FsError> for ReadError {
    fn from(_: FsError) -> ReadError {
        ReadError::Fs
    }
}

impl From<Budget> for ReadError {
    fn from(_: Budget) -> ReadError {
        ReadError::Budget
    }
}

/// python `read_entry(root, rel, text, deadline)`: 파일 하나를 읽어 항목으로. `text` 가 없으면 디스크에서 읽는다.
pub fn read_entry(
    root: &str,
    rel: &str,
    text: Option<&str>,
    deadline: Option<Deadline>,
) -> std::result::Result<Entry, ReadError> {
    let fp = join(root, rel);
    let st = fs::stat(&fp)?;
    let owned;
    let text = match text {
        Some(t) => t,
        None => {
            // FIFO 를 열면 쓰는 쪽이 올 때까지 멈춘다
            if !fs::is_file(&fp) {
                return Err(ReadError::Fs);
            }
            owned = fs::read_text(&fp)?;
            &owned
        }
    };

    let (sets, marks) = if generated(text) {
        (Vec::new(), Vec::new())
    } else {
        extract_within(text, family(&ext_of(rel)).unwrap_or(Family::C), deadline)?
    };
    Ok(Entry {
        mtime_ns: st.mtime_ns,
        size: i128::from(st.size),
        sets,
        marks,
    })
}

/// [`load`] 의 결과(python `(idx, dirty, cut)`).
pub struct Loaded {
    pub index: Index,
    /// 고친 것이 있어 다시 써야 한다.
    pub dirty: bool,
    /// 시간 한도에서 끊었다.
    pub cut: bool,
}

/// python `load_index(root, files, own_rel)`: 색인을 읽고 바뀐 파일만 다시 읽는다. 편집한 파일은 부르는 쪽이 채운다.
pub fn load(
    ip: &str,
    root: &str,
    files: &[String],
    own_rel: &str,
    clock: &Clock,
) -> Result<Loaded> {
    let mut index = read_index(ip)?;

    // Drop files that are gone
    let live: HashSet<&str> = files.iter().map(String::as_str).collect();
    let mut dirty = index.retain(&live);
    let mut cut = false;

    // Re-read changed files until the cold budget
    for rel in files {
        if rel == own_rel {
            continue;
        }
        let Ok(st) = fs::stat(&join(root, rel)) else {
            continue;
        };
        if index
            .get(rel)
            .is_some_and(|e| e.mtime_ns == st.mtime_ns && e.size == i128::from(st.size))
        {
            continue;
        }
        if st.size > MAX_BYTES {
            continue;
        }

        // A cut leaves the rest for the next edit
        if clock.ms() > COLD_MS {
            cut = true;
            break;
        }
        let deadline = Deadline { clock, ms: COLD_MS };
        match read_entry(root, rel, None, Some(deadline)) {
            Ok(entry) => {
                index.insert(rel, entry);
                dirty = true;
            }

            // 한도 안에 다 읽지 못한 파일은 바뀔 때까지 빈 항목이다: 다음 색인이 이 파일에서 멈추지 않는다
            Err(ReadError::Budget) => {
                let empty = Entry {
                    mtime_ns: st.mtime_ns,
                    size: i128::from(st.size),
                    sets: Vec::new(),
                    marks: Vec::new(),
                };
                index.insert(rel, empty);
                dirty = true;
                cut = true;
                break;
            }
            Err(ReadError::Fs) => {}
        }
    }
    Ok(Loaded { index, dirty, cut })
}

/// python `save_index(root, idx)`: 임시 파일에 쓰고 바꿔 단다. 쓰기 실패는 넘긴다.
///
/// 짝 없는 서로게이트가 든 항목(UTF-8 이 아닌 파일 이름, 입력의 escape)은 python 이 인코딩하지 못해 빼고 쓴다.
pub fn save(ip: &str, index: &Index) -> Result<()> {
    let mut text = to_json(index);
    if has_placeholder(&text) {
        let mut kept = Index::default();
        for (rel, e) in index.iter() {
            if !has_placeholder(rel)
                && !has_placeholder(&dumps_compact(&entry_value(e), EnsureAscii::No))
            {
                kept.insert(rel, e.clone());
            }
        }
        text = to_json(&kept);
    }
    let tmp = format!("{ip}.{}.tmp", std::process::id());
    if fs::write_text(&tmp, &text).is_ok()
        && let (Some(from), Some(to)) = (fs::os_path(&tmp), fs::os_path(ip))
    {
        let _ = std::fs::rename(from, to);
    }
    Ok(())
}

fn has_placeholder(text: &str) -> bool {
    text.chars().any(|c| unit_of(c).is_some())
}

// 색인 파일을 읽는다. 없거나 JSON 이 아니거나 판이 다르면 빈 색인.
// dict 가 아니거나 files 가 없으면 python 은 예외로 끝난다
fn read_index(ip: &str) -> Result<Index> {
    let Ok(text) = fs::read_text(ip) else {
        return Ok(Index::default());
    };
    let Ok(value) = loads(&text) else {
        return Ok(Index::default());
    };
    let Ok(top) = value.into_dict() else {
        return Err(Halt::PyError("the index is not a dict"));
    };
    match top.get("v") {
        Some(Value::Int(INDEX_VERSION)) => {}
        Some(Value::Float(f)) if *f == 2.0 => {
            return Err(Halt::Unported("a float index version python keeps"));
        }
        _ => return Ok(Index::default()),
    }

    // Only the shape this port writes
    let keys: Vec<&str> = top.iter().map(|(k, _)| k).collect();
    if keys != ["v", "files"] {
        return Err(Halt::Unported("an index with other top-level keys"));
    }
    let Some(Value::Dict(files)) = top.get("files") else {
        return Err(Halt::PyError("the index files is not a dict"));
    };
    let mut index = Index::default();
    for (rel, e) in files.iter() {
        index.insert(
            rel,
            entry_from(e).ok_or(Halt::Unported("an index entry this port does not write"))?,
        );
    }
    Ok(index)
}

fn entry_from(v: &Value) -> Option<Entry> {
    let Value::List(items) = v else { return None };
    let [
        Value::Int(mtime_ns),
        Value::Int(size),
        Value::List(sets),
        Value::List(marks),
    ] = items.as_slice()
    else {
        return None;
    };
    Some(Entry {
        mtime_ns: *mtime_ns,
        size: *size,
        sets: sets.iter().map(set_from).collect::<Option<_>>()?,
        marks: marks.iter().map(mark_from).collect::<Option<_>>()?,
    })
}

fn set_from(v: &Value) -> Option<StringSet> {
    let Value::List(items) = v else { return None };
    let [
        Value::Int(line),
        Value::Str(name),
        Value::Int(flags),
        Value::List(words),
        copy_of,
        dup,
    ] = items.as_slice()
    else {
        return None;
    };
    Some(StringSet {
        line: i64::try_from(*line).ok()?,
        name: name.clone(),
        flags: i64::try_from(*flags).ok()?,
        words: words
            .iter()
            .map(|w| w.as_str().map(str::to_owned))
            .collect::<Option<_>>()?,
        copy_of: opt_str(copy_of)?,
        dup: opt_str(dup)?,
    })
}

fn mark_from(v: &Value) -> Option<Mark> {
    let Value::List(items) = v else { return None };
    let [Value::Int(line), Value::Str(target), name, Value::Str(kind)] = items.as_slice() else {
        return None;
    };
    Some(Mark {
        line: i64::try_from(*line).ok()?,
        target: target.clone(),
        name: opt_str(name)?,
        kind: MarkKind::from_code(kind)?,
    })
}

// 글 또는 null. 다른 값은 None(옮기지 않는 꼴)
fn opt_str(v: &Value) -> Option<Option<String>> {
    match v {
        Value::Null => Some(None),
        Value::Str(s) => Some(Some(s.clone())),
        _ => None,
    }
}

/// python `json.dump(idx, f, ensure_ascii=False, separators=(",", ":"))` 의 글.
pub fn to_json(index: &Index) -> String {
    let files: Vec<(String, Value)> = index
        .iter()
        .map(|(rel, e)| (rel.to_owned(), entry_value(e)))
        .collect();
    let top = Dict::from_pairs(vec![
        ("v".to_owned(), Value::Int(INDEX_VERSION)),
        ("files".to_owned(), Value::Dict(Dict::from_pairs(files))),
    ]);
    dumps_compact(&Value::Dict(top), EnsureAscii::No)
}

fn entry_value(e: &Entry) -> Value {
    let text = |s: &str| Value::Str(s.to_owned());
    let opt = |s: &Option<String>| s.as_deref().map_or(Value::Null, text);
    let sets = e
        .sets
        .iter()
        .map(|s| {
            Value::List(vec![
                Value::Int(i128::from(s.line)),
                text(&s.name),
                Value::Int(i128::from(s.flags)),
                Value::List(s.words.iter().map(|w| text(w)).collect()),
                opt(&s.copy_of),
                opt(&s.dup),
            ])
        })
        .collect();

    let marks = e
        .marks
        .iter()
        .map(|m| {
            Value::List(vec![
                Value::Int(i128::from(m.line)),
                text(&m.target),
                opt(&m.name),
                text(m.kind.code()),
            ])
        })
        .collect();

    Value::List(vec![
        Value::Int(e.mtime_ns),
        Value::Int(e.size),
        Value::List(sets),
        Value::List(marks),
    ])
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 색인 글은 python json.dump(ensure_ascii=False, separators=(",", ":")) 와 같고 읽으면 같은 값이다.
    #[test]
    fn index_round_trips_python_format() {
        let line = r#"{"v":2,"files":{"a.luau":[1,2,[[2,"F",1,["back","coin","é"],"b.luau#F",null]],[[1,"b.luau","F","v"]]],"g.py":[3,4,[],[]]}}"#;
        let dir = std::env::temp_dir().join(format!("qc-index-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let ip = dir.join("i.json");
        std::fs::write(&ip, line).unwrap();

        // Read, then write back byte for byte
        let index = read_index(ip.to_str().unwrap()).unwrap();
        assert_eq!(index.get("a.luau").unwrap().sets[0].words[2], "\u{e9}");
        assert_eq!(to_json(&index), line);

        // Another version starts over; a list is python's AttributeError
        std::fs::write(&ip, r#"{"v":1,"files":{"x":1}}"#).unwrap();
        assert!(
            read_index(ip.to_str().unwrap())
                .unwrap()
                .iter()
                .next()
                .is_none()
        );
        std::fs::write(&ip, "[]").unwrap();
        assert!(matches!(
            read_index(ip.to_str().unwrap()),
            Err(Halt::PyError(_))
        ));
        std::fs::remove_dir_all(&dir).unwrap();
    }

    /// 이름은 python hashlib.sha1(root.encode()).hexdigest()[:12] 다.
    #[test]
    fn short_sha1_matches_hashlib() {
        // python: hashlib.sha1(b"/repo").hexdigest()[:12]
        assert_eq!(short_sha1("/repo").unwrap(), "83630750896a");
    }

    /// 서로게이트는 surrogatepass 바이트로 해시하고, 그것이 든 항목은 색인 파일에서 뺀다.
    #[test]
    fn surrogates_hash_and_drop_like_python() {
        use harness_hook::py::surrogate::placeholder;
        let low = placeholder(0xDCFF).unwrap();

        // python: hashlib.sha1("/r\udcff".encode("utf-8", "surrogatepass")).hexdigest()[:12]
        assert_eq!(short_sha1(&format!("/r{low}")).unwrap(), "c840a8f64e23");

        // The entry with the surrogate is left out, the other stays
        let mut index = Index::default();
        let entry = |words: Vec<String>| Entry {
            mtime_ns: 1,
            size: 2,
            sets: vec![StringSet {
                line: 1,
                name: "X".into(),
                flags: 0,
                words,
                copy_of: None,
                dup: None,
            }],
            marks: Vec::new(),
        };
        index.insert("ok.py", entry(vec!["aa".into()]));
        index.insert(&format!("bad{low}.py"), entry(vec!["bb".into()]));
        index.insert("text.py", entry(vec![format!("c{low}")]));
        let dir = std::env::temp_dir().join(format!("reuse-idx-{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let ip = dir.join("i.json");
        save(ip.to_str().unwrap(), &index).unwrap();
        let text = std::fs::read_to_string(&ip).unwrap();
        assert_eq!(
            text,
            r#"{"v":2,"files":{"ok.py":[1,2,[[1,"X",0,["aa"],null,null]],[]]}}"#
        );
        std::fs::remove_dir_all(&dir).unwrap();
    }
}
