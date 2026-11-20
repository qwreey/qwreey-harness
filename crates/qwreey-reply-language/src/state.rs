//! 세션 상태 파일(`<임시 폴더>/claude-conventions-lang/<sid>.json`)과 감지 로그(`${CLAUDE_PLUGIN_DATA}/drift.jsonl`).
//!
//! python 판과 번갈아 읽고 쓴다. 키 순서와 값 꼴을 지키려고 `py::value::Dict` 로 다룬다.

use std::io::Write;

use harness_hook::nonce::now_secs;
use harness_hook::py::json::{EnsureAscii, dumps_dict};
use harness_hook::py::path::join;
use harness_hook::py::value::{Dict, Value};

use crate::context::Context;
use crate::language::data_dir;
use crate::pyval::{
    Abort, Result, os_path, parse_object, read_bytes, round3, sanitize, take_chars,
};

const NS: &str = "claude-conventions-lang";

/// python `state_file(session_id)`: 폴더를 만든다. 임시 폴더가 없거나 만들지 못하면 `None`(python OSError).
fn state_file(ctx: &Context, sid: &str) -> Option<String> {
    let dir = join(ctx.tempdir()?, NS);
    std::fs::create_dir_all(os_path(&dir)?).ok()?;
    Some(join(&dir, &format!("{}.json", sanitize(sid))))
}

/// python `load_state(session_id)`: 읽지 못하면 빈 dict. 객체가 아닌 JSON 은 python 이 쓰다가 예외로 끝난다.
pub fn load(ctx: &Context, sid: &str) -> Result<Dict> {
    let Some(path) = state_file(ctx, sid) else {
        return Ok(Dict::new());
    };
    match read_bytes(&path).map(|bytes| parse_object(&bytes)) {
        Some(Ok(dict)) => Ok(dict),
        Some(Err(Some(_))) => Err(Abort("state file is not an object")),
        Some(Err(None)) | None => Ok(Dict::new()),
    }
}

/// python `save_state(session_id, st)`: pid 붙은 임시 파일에 쓰고 바꿔 놓는다. 실패는 넘긴다.
pub fn save(ctx: &Context, sid: &str, st: &Dict) {
    let Some(path) = state_file(ctx, sid) else {
        return;
    };
    let tmp = format!("{path}.{}.tmp", std::process::id());
    let (Some(tmp_os), Some(path_os)) = (os_path(&tmp), os_path(&path)) else {
        return;
    };
    if std::fs::write(&tmp_os, dumps_dict(st, EnsureAscii::Yes, None)).is_ok() {
        let _ = std::fs::rename(tmp_os, path_os);
    }
}

/// python `log(session_id, kind, ratio, length)`: 감지와 조치마다 한 줄(본문 없음). 데이터 폴더가 없거나 쓰지 못하면 넘긴다.
pub fn log(ctx: &Context, sid: &str, kind: &str, ratio: Option<f64>, length: Option<Value>) {
    let Some(dir) = data_dir(ctx) else {
        return;
    };
    let Some(dir_os) = os_path(&dir) else {
        return;
    };
    if std::fs::create_dir_all(&dir_os).is_err() {
        return;
    }

    // {"ts", "session", "kind", "ratio", "length"} in python's order
    // python int(time.time()) truncates
    let ts = now_secs() as i128;
    let rec = Dict::from_pairs(vec![
        ("ts".to_owned(), Value::Int(ts)),
        (
            "session".to_owned(),
            Value::Str(take_chars(&sanitize(sid), 8).to_owned()),
        ),
        ("kind".to_owned(), Value::Str(kind.to_owned())),
        (
            "ratio".to_owned(),
            ratio.map_or(Value::Null, |r| Value::Float(round3(r))),
        ),
        ("length".to_owned(), length.unwrap_or(Value::Null)),
    ]);
    let line = format!("{}\n", dumps_dict(&rec, EnsureAscii::Yes, None));
    if let Ok(mut file) = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(dir_os.join("drift.jsonl"))
    {
        let _ = file.write_all(line.as_bytes());
    }
}
