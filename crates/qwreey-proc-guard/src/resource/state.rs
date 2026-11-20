//! resource-guard 의 상태 파일: 자리, 만들기, 읽고 쓰기, 잠금, 오래된 것 지우기.
//!
//! python 판과 같은 자리, 같은 꼴이라 두 판이 번갈아 돌아도 서로의 기록을 읽는다:
//! `${CLAUDE_PLUGIN_DATA}/resource-guard/`(없으면 `<임시 폴더>/claude-qwreey-proc-guard-<uid>/resource-guard/`, 0700) 아래
//! `pre/<세션 키>-<tool_use_id>.json`(Pre 측정, Post 가 읽고 지운다)과 `s-<세션 키>.json`(경고 기록, `.lock` 을 flock 하고 고친다).

use std::fs;
use std::io::{ErrorKind, Write};
use std::path::Path;
use std::time::{SystemTime, UNIX_EPOCH};

use harness_hook::Env;
use harness_hook::py::json::{EnsureAscii, to_string};
use harness_hook::py::tempfile::gettempdir;
use harness_hook::py::value::{Dict, Value};
use sha2::{Digest, Sha256};

use super::Abort;
use crate::context::py_str;

/// python `os.path.join(a, b)`(POSIX): `a` 가 비었거나 `/` 로 끝나면 그대로 잇는다.
pub fn join(a: &str, b: &str) -> String {
    if a.is_empty() || a.ends_with('/') || (cfg!(windows) && a.ends_with('\\')) {
        format!("{a}{b}")
    } else {
        format!("{a}{}{b}", std::path::MAIN_SEPARATOR)
    }
}

/// python `os.path.dirname(p)`(POSIX): 마지막 `/` 앞, 뒤의 `/` 는 떼되 루트는 남긴다.
pub fn dirname(p: &str) -> String {
    let cut = p
        .rfind(['/', std::path::MAIN_SEPARATOR])
        .map_or(0, |i| i + 1);
    let head = &p[..cut];
    if !head.is_empty() && head.chars().any(|c| c != '/') {
        head.trim_end_matches('/').to_owned()
    } else {
        head.to_owned()
    }
}

/// 자기 uid 글(python `my_uid`). Windows 는 사용자 이름(파일 이름에 못 쓰는 글자는 `_`), 모르면 python 처럼 예외.
pub fn my_uid(env: &Env) -> Result<String, Abort> {
    #[cfg(unix)]
    {
        let _ = env;
        Ok(rustix::process::getuid().as_raw().to_string())
    }

    // python getpass.getuser: LOGNAME, USER, LNAME, USERNAME 의 처음 값
    #[cfg(not(unix))]
    {
        let name = ["LOGNAME", "USER", "LNAME", "USERNAME"]
            .iter()
            .find_map(|k| env.get_nonempty(k))
            .ok_or(Abort)?;
        Ok(name
            .chars()
            .map(|c| {
                if c.is_ascii_alphanumeric() || "_.-".contains(c) {
                    c
                } else {
                    '_'
                }
            })
            .collect())
    }
}

/// 상태 폴더(python `state_dir`).
pub fn state_dir(env: &Env) -> Result<String, Abort> {
    // 임시 폴더는 여러 사용자가 같이 쓴다. 사용자마다 따로 두어 남이 만든 Pre 기록을 읽지 않게 한다
    let base = match env.get_nonempty("CLAUDE_PLUGIN_DATA") {
        Some(data) => data.to_owned(),
        None => join(
            &gettempdir(env).ok_or(Abort)?,
            &format!("claude-qwreey-proc-guard-{}", my_uid(env)?),
        ),
    };
    Ok(join(&base, "resource-guard"))
}

/// 상태 폴더와 그 부모가 내 것이고 남이 쓸 수 없는가(아직 없으면 참). Pre 기록이 core 를 지우라는 근거가 되기 때문이다.
///
/// 없음(ENOENT) 말고 stat 오류(권한, ENOTDIR)는 python 에서 예외라 [`Abort`].
pub fn state_trusted(env: &Env) -> Result<bool, Abort> {
    #[cfg(unix)]
    {
        use std::os::unix::fs::MetadataExt;

        let me = rustix::process::getuid().as_raw();
        let dir = state_dir(env)?;
        for p in [dir.clone(), dirname(&dir)] {
            match fs::metadata(&p) {
                Ok(m) if m.uid() != me || m.mode() & 0o022 != 0 => return Ok(false),
                Ok(_) => {}
                Err(e) if e.kind() == ErrorKind::NotFound => {}
                Err(_) => return Err(Abort),
            }
        }
        Ok(true)
    }

    // python 도 os.getuid 가 없으면 보지 않는다
    #[cfg(not(unix))]
    {
        let _ = env;
        Ok(true)
    }
}

/// 세션 id 의 sha256 hex 앞 16자(없으면 "none" 의).
pub fn session_key(session_id: Option<&serde_json::Value>) -> String {
    let sid = session_id
        .and_then(py_str)
        .unwrap_or_else(|| "none".to_owned());
    let mut hex: String = Sha256::digest(sid.as_bytes())
        .iter()
        .map(|b| format!("{b:02x}"))
        .collect();
    hex.truncate(16);
    hex
}

/// Pre 기록 이름에 쓸 tool_use_id: 영문자, 숫자, `_`, `-` 만 80자까지. 비면 `None`(Pre 기록 없음).
pub fn tool_use_key(tool_use_id: Option<&serde_json::Value>) -> Option<String> {
    let raw = tool_use_id.and_then(py_str).unwrap_or_default();
    let tid: String = raw
        .chars()
        .filter(|c| c.is_ascii_alphanumeric() || *c == '_' || *c == '-')
        .take(80)
        .collect();
    (!tid.is_empty()).then_some(tid)
}

/// 이 도구 호출의 Pre 기록 경로.
pub fn pre_path(dir: &str, session_key: &str, tool_use_key: &str) -> String {
    join(
        &join(dir, "pre"),
        &format!("{session_key}-{tool_use_key}.json"),
    )
}

/// JSON 객체 파일. 없거나 읽지 못하거나 객체가 아니면 빈 dict.
pub fn read_json(path: &str) -> Dict {
    let Ok(bytes) = fs::read(path) else {
        return Dict::new();
    };
    // python 이 쓴 파일 이름의 서로게이트(`\udcff`)도 읽는다
    match harness_hook::py::surrogate::json_from_slice::<Value>(&bytes) {
        Ok(Value::Dict(d)) => d,
        _ => Dict::new(),
    }
}

/// `path` 와 없는 부모를 0700 으로 만든다(python `os.makedirs` 의 mode 는 맨 끝 폴더에만 걸려 따로 짰다).
pub fn ensure_dir(path: &str) -> std::io::Result<()> {
    if Path::new(path).is_dir() {
        return Ok(());
    }
    let parent = dirname(path);
    if !parent.is_empty() && parent != path {
        ensure_dir(&parent)?;
    }

    #[cfg_attr(not(unix), allow(unused_mut))]
    let mut builder = fs::DirBuilder::new();
    #[cfg(unix)]
    std::os::unix::fs::DirBuilderExt::mode(&mut builder, 0o700);
    match builder.create(path) {
        Err(e) if e.kind() == ErrorKind::AlreadyExists => Ok(()),
        other => other,
    }
}

/// 값을 python `json.dump` 꼴로 쓴다(임시 파일에 쓰고 바꿔 단다). 오류는 넘긴다.
pub fn write_json(path: &str, value: &Dict) {
    let _ = try_write_json(path, value);
}

fn try_write_json(path: &str, value: &Dict) -> std::io::Result<()> {
    ensure_dir(&dirname(path))?;
    let text = to_string(value, EnsureAscii::Yes).expect("string keys");
    let tmp = format!("{path}.{}.tmp", std::process::id());
    fs::File::create(&tmp)?.write_all(text.as_bytes())?;
    fs::rename(&tmp, path)
}

/// 세션 기록의 읽기-고치기-쓰기를 감싸는 flock. 잡은 파일(닫으면 풀린다) 또는 `None`(실패, 시간 초과, Windows: 잠금 없이 간다).
pub fn lock(path: &str) -> Option<fs::File> {
    #[cfg(unix)]
    {
        use rustix::fs::{FlockOperation, flock};
        use std::fs::OpenOptions;
        use std::os::unix::fs::OpenOptionsExt;
        use std::time::Duration;

        const LOCK_TRIES: usize = 50;
        const LOCK_WAIT: Duration = Duration::from_millis(10);

        ensure_dir(&dirname(path)).ok()?;
        let file = OpenOptions::new()
            .read(true)
            .write(true)
            .create(true)
            .truncate(false)
            .mode(0o600)
            .open(path)
            .ok()?;

        // 잡은 쪽은 몇 ms 만 쥔다. 기다림에 끝을 둔다
        for _ in 0..LOCK_TRIES {
            match flock(&file, FlockOperation::NonBlockingLockExclusive) {
                Ok(()) => return Some(file),
                Err(e) if e == rustix::io::Errno::WOULDBLOCK => std::thread::sleep(LOCK_WAIT),
                Err(_) => break,
            }
        }
        None
    }

    // python 도 fcntl 이 없는 Windows 에서는 잠그지 않는다
    #[cfg(not(unix))]
    {
        let _ = path;
        None
    }
}

/// `dir` 안에서 `ttl` 초보다 오래된 보통 파일을 지운다. 오류는 넘긴다.
pub fn prune(dir: &str, ttl: f64, now: f64) {
    let Ok(entries) = fs::read_dir(dir) else {
        return;
    };
    for entry in entries.flatten() {
        // 링크를 따라가지 않고 보통 파일인지 본 뒤 mtime
        let is_file = entry.file_type().is_ok_and(|t| t.is_file());
        let mtime = entry
            .path()
            .metadata()
            .ok()
            .and_then(|m| m.modified().ok())
            .map(secs);
        if is_file && mtime.is_some_and(|m| now - m > ttl) {
            let _ = fs::remove_file(entry.path());
        }
    }
}

/// `SystemTime` 의 유닉스 초(python `st_mtime`, `time.time()`).
pub fn secs(t: SystemTime) -> f64 {
    match t.duration_since(UNIX_EPOCH) {
        Ok(d) => d.as_secs_f64(),
        Err(e) => -e.duration().as_secs_f64(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn paths_follow_posixpath() {
        assert_eq!(join("/a", "b"), "/a/b");
        assert_eq!(join("/a/", "b"), "/a/b");
        assert_eq!(dirname("/a/b"), "/a");
        assert_eq!(dirname("/a"), "/");
        assert_eq!(dirname("a"), "");
        assert_eq!(dirname("//a//b"), "//a");
    }

    #[test]
    fn keys_and_pre_paths() {
        let sid = serde_json::json!("abc");
        assert_eq!(session_key(Some(&sid)), "ba7816bf8f01cfea");
        assert_eq!(session_key(None), session_key(Some(&serde_json::json!(""))));
        let tid = serde_json::json!("../../x y");
        assert_eq!(tool_use_key(Some(&tid)).as_deref(), Some("xy"));
        assert_eq!(tool_use_key(Some(&serde_json::json!("../"))), None);
        assert_eq!(
            tool_use_key(Some(&serde_json::json!(12))).as_deref(),
            Some("12")
        );
        assert_eq!(pre_path("/d", "k", "xy"), "/d/pre/k-xy.json");
    }
}
