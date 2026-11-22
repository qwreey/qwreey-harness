//! 명령 전 상태의 스냅숏 파일(python `bash_writes.snap_dir`, `snap_path`, `pending`, `sweep`, 스냅숏 JSON).
//!
//! 자리: `<임시 폴더>/claude-conventions[-<uid>]/bash/<session>.<agent 또는 main>.<tool_use_id>.json`(0600, 폴더 0700).
//! python 판과 같은 자리, 같은 JSON 꼴이다: 한쪽의 PreToolUse 가 적고 다른 쪽의 PostToolUse 가 읽어도 된다.

use std::time::{SystemTime, UNIX_EPOCH};

use harness_hook::HookInput;
use harness_hook::epoch::sanitize;
use harness_hook::py::fs;
use harness_hook::py::json::{EnsureAscii, dumps_dict};
use harness_hook::py::json_load::loads;
use harness_hook::py::path::{dirname, join};
use harness_hook::py::surrogate::{encode_os, unit_of};
use harness_hook::py::value::{Dict, Value};
use sha1::{Digest, Sha1};

use super::files::{FileStat, Recorded};
use crate::context::Context;
use crate::halt::{Halt, Result};
use crate::pyval;

/// 이보다 오래된 스냅숏은 Post 가 오지 않은 것(거절, 중단)이라 지운다(python `STALE_S`).
const STALE_S: f64 = 3600.0;
/// 다른 Bash 가 도는 중이라고 볼 스냅숏 나이(python `PENDING_S`): 앞쪽 Bash 의 최대 timeout 10분보다 조금 길게.
const PENDING_S: f64 = 620.0;

/// 명령 전 상태 하나(python 의 스냅숏 dict).
#[derive(Clone, Debug, Default, PartialEq)]
pub struct Snapshot {
    /// git 최상위, git 이 아니면 프로젝트 폴더.
    pub root: String,
    pub head: Option<String>,
    /// porcelain 을 적었는가(git 이고 worktree 를 다시 쓰는 명령이 아니다).
    pub wide: bool,
    /// 명령 전 porcelain 에 나온 파일(저장소 기준 경로)의 (mtime, 크기).
    pub dirty: Vec<(String, Option<FileStat>)>,
    /// 글을 적어 둔 파일(절대 경로).
    pub texts: Vec<(String, Recorded)>,
    /// 명령이 이름을 댄 파일의 (mtime, 크기).
    pub stats: Vec<(String, Option<FileStat>)>,
    pub named: Vec<String>,
    /// porcelain 이 `DIRTY_MAX` 를 넘었다.
    pub overflow: bool,
    /// worktree 를 다시 쓰는 git 하위 명령이 있다.
    pub rewrite: bool,
    /// 적을 때 같은 세션의 다른 스냅숏이 있었다.
    pub concurrent: bool,
}

/// (키, 값) 목록에서 키의 값.
pub fn lookup<'a, V>(pairs: &'a [(String, V)], key: &str) -> Option<&'a V> {
    pairs.iter().find(|(k, _)| k == key).map(|(_, v)| v)
}

fn stat_value(st: Option<FileStat>) -> Value {
    match st {
        Some((mtime, size)) => Value::List(vec![Value::Int(mtime), Value::Int(i128::from(size))]),
        None => Value::Null,
    }
}

fn stat_from(v: &Value) -> Option<Option<FileStat>> {
    match v {
        Value::Null => Some(None),
        Value::List(items) => match items.as_slice() {
            [Value::Int(m), Value::Int(s)] => Some(Some((*m, u64::try_from(*s).ok()?))),
            _ => None,
        },
        _ => None,
    }
}

impl Snapshot {
    /// python `json.dump(snap, f, ensure_ascii=False)` 의 글. 키 순서가 python dict 와 같다.
    pub fn to_json(&self) -> String {
        let texts = self
            .texts
            .iter()
            .map(|(k, t)| (k.clone(), t.to_value()))
            .collect();
        let named = self.named.iter().cloned().map(Value::Str).collect();
        let fields = vec![
            ("root", Value::Str(self.root.clone())),
            ("head", self.head.clone().map_or(Value::Null, Value::Str)),
            ("wide", Value::Bool(self.wide)),
            ("dirty", stats_value(&self.dirty)),
            ("texts", Value::Dict(Dict::from_pairs(texts))),
            ("stats", stats_value(&self.stats)),
            ("named", Value::List(named)),
            ("overflow", Value::Bool(self.overflow)),
            ("rewrite", Value::Bool(self.rewrite)),
            ("concurrent", Value::Bool(self.concurrent)),
        ];
        let d = Dict::from_pairs(fields.into_iter().map(|(k, v)| (k.to_owned(), v)).collect());
        dumps_dict(&d, EnsureAscii::No, None)
    }

    /// 스냅숏 JSON 에서. 두 훅이 쓰는 꼴이 아니면 `None`(이 판은 그런 파일을 판정하지 않는다).
    ///
    /// `named` 가 비었으면 python 은 `texts` 의 키를 쓴다(`snap.get("named") or texts`).
    pub fn from_json(text: &str) -> Option<Snapshot> {
        let d = loads(text).ok()?.into_dict().ok()?;
        let flag = |k: &str| d.get(k).is_some_and(Value::truthy);

        // Recorded texts, and the named paths that default to them
        let texts: Vec<(String, Recorded)> = pairs(&d, "texts")?
            .into_iter()
            .map(|(p, v)| Some((p, Recorded::from_value(&v)?)))
            .collect::<Option<_>>()?;
        let named = match d.get("named") {
            Some(Value::List(items)) if !items.is_empty() => items
                .iter()
                .map(|v| v.as_str().map(str::to_owned))
                .collect::<Option<_>>()?,
            Some(v) if v.truthy() => return None,
            _ => texts.iter().map(|(p, _)| p.clone()).collect(),
        };

        let head = match d.get("head") {
            Some(Value::Str(h)) => Some(h.clone()),
            None | Some(Value::Null) => None,
            Some(_) => return None,
        };
        Some(Snapshot {
            root: d.get("root")?.as_str()?.to_owned(),
            head,
            wide: flag("wide"),
            dirty: stat_pairs(&d, "dirty")?,
            texts,
            stats: stat_pairs(&d, "stats")?,
            named,
            overflow: flag("overflow"),
            rewrite: flag("rewrite"),
            concurrent: flag("concurrent"),
        })
    }
}

// {경로: [mtime, 크기] 또는 null}
fn stats_value(pairs: &[(String, Option<FileStat>)]) -> Value {
    Value::Dict(Dict::from_pairs(
        pairs
            .iter()
            .map(|(k, s)| (k.clone(), stat_value(*s)))
            .collect(),
    ))
}

// dict 인 필드의 (키, 값)들. 없거나 null 이면 빈 목록, 다른 꼴이면 None
fn pairs(d: &Dict, key: &str) -> Option<Vec<(String, Value)>> {
    match d.get(key) {
        Some(Value::Dict(m)) => Some(m.iter().map(|(k, v)| (k.to_owned(), v.clone())).collect()),
        None | Some(Value::Null) => Some(Vec::new()),
        _ => None,
    }
}

fn stat_pairs(d: &Dict, key: &str) -> Option<Vec<(String, Option<FileStat>)>> {
    pairs(d, key)?
        .into_iter()
        .map(|(p, v)| Some((p, stat_from(&v)?)))
        .collect()
}

/// python `snap_dir()`: TMPDIR 류가 없으면 `/tmp` 를 여러 사용자가 함께 쓰므로 사용자별 이름을 붙인다.
pub fn snap_dir(ctx: &Context) -> Result<String> {
    let base = ctx.tempdir()?;
    let shared = !["TMPDIR", "TEMP", "TMP"]
        .iter()
        .any(|k| ctx.env.get_nonempty(k).is_some());
    Ok(match uid() {
        Some(uid) if shared => join(&join(base, &format!("claude-conventions-{uid}")), "bash"),
        _ => join(&join(base, "claude-conventions"), "bash"),
    })
}

#[cfg(unix)]
fn uid() -> Option<u32> {
    Some(rustix::process::getuid().as_raw())
}

#[cfg(not(unix))]
fn uid() -> Option<u32> {
    None
}

// python _clean(v): re.sub(r"[^\w-]", "", str(v or ""))
fn clean(v: Option<&Value>) -> Result<String> {
    Ok(match pyval::truthy_text(v)? {
        Some(text) => sanitize(&text),
        None => String::new(),
    })
}

fn or_default(text: String, default: &str) -> String {
    if text.is_empty() {
        default.to_owned()
    } else {
        text
    }
}

// python _who(data): "<session>.<agent 또는 main>."
fn who(input: &HookInput) -> Result<String> {
    let sid = or_default(clean(input.get("session_id"))?, "nosession");
    let agent = or_default(clean(input.get("agent_id"))?, "main");
    Ok(format!("{sid}.{agent}."))
}

/// python `snap_path(data)`: tool_use_id 가 없으면 명령 글의 SHA-1 앞 16자로 Pre 와 Post 를 잇는다.
pub fn snap_path(ctx: &Context, input: &HookInput) -> Result<String> {
    let mut tid = clean(input.get("tool_use_id"))?;
    if tid.is_empty() {
        let cmd = match input.get("tool_input") {
            Some(Value::Dict(ti)) => ti.get("command").and_then(Value::as_str).unwrap_or(""),
            _ => "",
        };
        let bytes = encode_os(cmd).ok_or(Halt::PyError("the command has a lone surrogate"))?;
        let hex: String = Sha1::digest(&bytes)
            .iter()
            .map(|b| format!("{b:02x}"))
            .collect();
        tid = format!("c{}", &hex[..16]);
    }
    Ok(join(&snap_dir(ctx)?, &format!("{}{tid}.json", who(input)?)))
}

fn now_secs() -> f64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map_or(0.0, |d| d.as_secs_f64())
}

fn mtime_secs(path: &str) -> Option<f64> {
    fs::stat(path).ok().map(|st| st.mtime_ns as f64 / 1e9)
}

/// python `pending(data, mine)`: 같은 세션의 다른 스냅숏(아직 Post 가 오지 않은 Bash)이 있는가.
///
/// 서브에이전트도 session_id 가 같아 함께 센다. `mine` 은 지금 적는 파일 이름이다.
pub fn pending(ctx: &Context, input: &HookInput, mine: Option<&str>) -> Result<bool> {
    let dir = snap_dir(ctx)?;
    let prefix = format!(
        "{}.",
        or_default(clean(input.get("session_id"))?, "nosession")
    );
    let Ok(names) = fs::listdir(&dir) else {
        return Ok(false);
    };
    let now = now_secs();
    Ok(names.iter().any(|n| {
        n.starts_with(&prefix)
            && Some(n.as_str()) != mine
            && mtime_secs(&join(&dir, n)).is_some_and(|m| now - m < PENDING_S)
    }))
}

/// python `sweep()`: Post 가 오지 않은 스냅숏 가운데 [`STALE_S`] 를 넘은 것을 지운다. 모든 PreToolUse(Bash) 에서 부른다.
pub fn sweep(ctx: &Context) -> Result<()> {
    let dir = snap_dir(ctx)?;
    let Ok(names) = fs::listdir(&dir) else {
        return Ok(());
    };
    let now = now_secs();
    for n in names {
        let path = join(&dir, &n);
        if mtime_secs(&path).is_some_and(|m| now - m > STALE_S)
            && let Some(os) = fs::os_path(&path)
        {
            let _ = std::fs::remove_file(os);
        }
    }
    Ok(())
}

/// python `_own_dir(d)`: `d` 와 그 부모를 0700 으로 만들고, 둘 다 이 사용자의 진짜 폴더(링크 아님)인지 본다.
pub fn own_dir(dir: &str) -> bool {
    own_one(dirname(dir)) && own_one(dir)
}

fn own_one(path: &str) -> bool {
    let Some(os) = fs::os_path(path) else {
        return false;
    };

    // Make it, unless it is already there
    let mut builder = std::fs::DirBuilder::new();
    #[cfg(unix)]
    std::os::unix::fs::DirBuilderExt::mode(&mut builder, 0o700);
    match builder.create(&os) {
        Ok(()) => {}
        Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => {}
        Err(_) => return false,
    }

    // A real folder of this user, not a link
    std::fs::symlink_metadata(&os).is_ok_and(|meta| meta.is_dir() && owned_by_me(&meta))
}

#[cfg(unix)]
fn owned_by_me(meta: &std::fs::Metadata) -> bool {
    use std::os::unix::fs::MetadataExt;
    uid() == Some(meta.uid())
}

#[cfg(not(unix))]
fn owned_by_me(_: &std::fs::Metadata) -> bool {
    true
}

/// 스냅숏을 0600 파일로 쓴다(python `os.open(fp, O_WRONLY|O_CREAT|O_TRUNC|O_NOFOLLOW, 0o600)` 와 `fchmod`).
///
/// 링크인 자리는 열지 못한다(python 은 OSError 로 끝나고 bypass 가 넘긴다). python 은 글을 UTF-8 로 쓰다가
/// 짝 없는 서로게이트에서 멈춰 앞부분만 남긴다. 그 파일은 어느 판도 읽지 못하므로 여기서는 빈 파일로 둔다.
pub fn write(path: &str, snap: &Snapshot) -> Result<()> {
    let os = fs::os_path(path).ok_or(Halt::PyError("os.open of an unusable path"))?;
    let text = snap.to_json();
    let body = if text.chars().any(|c| unit_of(c).is_some()) {
        String::new()
    } else {
        text
    };
    write_private(&os, body.as_bytes()).map_err(|_| Halt::PyError("cannot write the snapshot"))
}

#[cfg(unix)]
fn write_private(path: &std::path::Path, bytes: &[u8]) -> std::io::Result<()> {
    use rustix::fs::{Mode, OFlags, fchmod, open};
    use std::io::Write;

    let flags =
        OFlags::WRONLY | OFlags::CREATE | OFlags::TRUNC | OFlags::NOFOLLOW | OFlags::CLOEXEC;
    let fd = open(path, flags, Mode::from_raw_mode(0o600))?;
    // 같은 이름이 이미 있었으면 O_CREAT 의 권한이 적용되지 않는다
    fchmod(&fd, Mode::from_raw_mode(0o600))?;
    std::fs::File::from(fd).write_all(bytes)
}

#[cfg(not(unix))]
fn write_private(path: &std::path::Path, bytes: &[u8]) -> std::io::Result<()> {
    std::fs::write(path, bytes)
}

/// 스냅숏 파일을 읽는다. 없거나 읽지 못하거나 JSON 이 아니면 `Ok(None)`(python 은 거기서 끝난다).
///
/// 읽은 JSON 이 두 훅이 쓰는 꼴이 아니면 [`Halt::Unported`].
pub fn load(path: &str) -> Result<Option<Snapshot>> {
    let Ok(text) = fs::read_text(path) else {
        return Ok(None);
    };
    if loads(&text).is_err() {
        return Ok(None);
    }
    Snapshot::from_json(&text)
        .map(Some)
        .ok_or(Halt::Unported("a snapshot of another shape"))
}

#[cfg(test)]
mod tests {
    use super::*;

    /// JSON 으로 쓰고 다시 읽으면 같은 스냅숏이다. named 가 비면 texts 의 키다.
    #[test]
    fn round_trips_and_named_falls_back() {
        let snap = Snapshot {
            root: "/r".into(),
            head: Some("abc".into()),
            wide: true,
            dirty: vec![("a.py".into(), Some((5, 3))), ("b.py".into(), None)],
            texts: vec![
                ("/r/a.py".into(), Recorded::Text("x\n".into())),
                ("/r/n.py".into(), Recorded::Missing),
                ("/r/big.py".into(), Recorded::Unread),
            ],
            stats: vec![("/r/n.py".into(), None)],
            named: vec!["/r/n.py".into()],
            ..Snapshot::default()
        };
        let text = snap.to_json();
        assert!(text.starts_with(
            "{\"root\": \"/r\", \"head\": \"abc\", \"wide\": true, \"dirty\": {\"a.py\": [5, 3]"
        ));
        assert_eq!(Snapshot::from_json(&text), Some(snap.clone()));

        let empty_named = text.replace("\"named\": [\"/r/n.py\"]", "\"named\": []");
        let got = Snapshot::from_json(&empty_named).unwrap();
        assert_eq!(got.named, vec!["/r/a.py", "/r/n.py", "/r/big.py"]);
    }
}
