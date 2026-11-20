//! 알림 중복 상태 파일(python `state_lock`, `load_state`, `save_state`).
//!
//! `$TMPDIR/claude-conventions/<sid>.c<회차>[.a<agent>].json` = `{"files": {경로: [알린 키]}, "doc_recheck": {경로: [함수 키]}}`.
//! python 판과 번갈아 쓰므로 같은 바이트로 쓴다(`json.dump` 기본: ensure_ascii, `, ` 와 `: `).

use std::time::{Duration, Instant};

use harness_hook::py::fs;
use harness_hook::py::json::{EnsureAscii, dumps_dict};
use harness_hook::py::json_load::loads;
use harness_hook::py::value::{Dict, Value};

/// 잠금을 기다리는 한도(python `STATE_LOCK_WAIT_S`).
const LOCK_WAIT: Duration = Duration::from_secs(3);

/// 상태 파일 잠금(python `state_lock`). 나란히 도는 Bash 와 Edit 훅이 같은 알림을 두 번 내지 않게 한다.
///
/// 잠금 파일을 못 열거나 한도 안에 못 잡으면 잠그지 않고 간다(알림이 한 번 겹칠 뿐이다). 놓을 때 fd 를 닫는다.
pub struct StateLock {
    #[cfg(unix)]
    _file: Option<std::fs::File>,
}

impl StateLock {
    /// `path + ".lock"` 을 잡는다.
    pub fn acquire(path: &str) -> StateLock {
        #[cfg(unix)]
        {
            StateLock {
                _file: lock_file(&format!("{path}.lock")),
            }
        }
        #[cfg(not(unix))]
        {
            let _ = path;
            StateLock {}
        }
    }
}

#[cfg(unix)]
fn lock_file(path: &str) -> Option<std::fs::File> {
    use rustix::fs::{FlockOperation, flock};
    use std::os::unix::fs::OpenOptionsExt;

    let file = std::fs::OpenOptions::new()
        .read(true)
        .write(true)
        .create(true)
        .truncate(false)
        .mode(0o600)
        .open(fs::os_path(path)?)
        .ok()?;
    let end = Instant::now() + LOCK_WAIT;
    loop {
        match flock(&file, FlockOperation::NonBlockingLockExclusive) {
            Ok(()) => break,
            Err(e) if e == rustix::io::Errno::WOULDBLOCK => {
                if Instant::now() > end {
                    break;
                }
                std::thread::sleep(Duration::from_millis(10));
            }
            // python 은 BlockingIOError 만 다시 해 보고 다른 OSError 는 잠그지 않고 간다
            Err(_) => break,
        }
    }
    Some(file)
}

/// python `load_state(path)`: 깨졌거나 꼴이 다르면 빈 상태로 시작하고, `files`, `doc_recheck` 는 dict 로 채운다.
pub fn load(path: &str) -> Dict {
    let mut state = fs::read_text(path)
        .ok()
        .and_then(|t| loads(&t).ok())
        .and_then(|v| v.into_dict().ok())
        .unwrap_or_default();
    for name in ["files", "doc_recheck"] {
        if !matches!(state.get(name), Some(Value::Dict(_))) {
            state.insert(name, Value::Dict(Dict::new()));
        }
    }
    state
}

/// python `save_state(path, state)`. 쓰기 실패는 넘긴다.
pub fn save(path: &str, state: &Dict) {
    let _ = fs::write_text(path, &dumps_dict(state, EnsureAscii::Yes, None));
}

/// 상태 안의 dict 하나를 고칠 수 있게(`load` 가 채워 두므로 늘 있다).
pub fn section<'s>(state: &'s mut Dict, name: &str) -> &'s mut Dict {
    let slot = state.setdefault(name, Value::Dict(Dict::new()));
    if !matches!(slot, Value::Dict(_)) {
        *slot = Value::Dict(Dict::new());
    }
    match slot {
        Value::Dict(d) => d,
        _ => unreachable!("just made a dict"),
    }
}
