//! 검토 ledger 의 자동 행(python `skills/fresh-advisor/scripts/review-ledger.py` 의 `auto_add`, `ledger_auto`).
//!
//! 메인이 add 를 잊어도 검토 횟수가 보이게, 검토가 끝나면 판정 `미기록` 인 행을 덧붙인다. python 판은 어떤 예외든 삼키고
//! 행만 건너뛴다. 그래서 여기서도 쓰지 못하면 조용히 넘긴다.

use std::io::Write;

use harness_hook::Env;
use harness_hook::py::json::{EnsureAscii, dumps_dict};
use harness_hook::py::path::{expanduser, join, pathlib_join};
use harness_hook::py::surrogate::{encode_os, from_os, unit_of};
use harness_hook::py::text::strip;
use harness_hook::py::value::{Dict, Value};

use crate::git;
use crate::pylib::fs::{is_file, makedirs, os_path};
use crate::pylib::pathx::pathlib_name;

const UNRECORDED: &str = "미기록";

/// 자동 행 하나의 재료.
pub struct AutoRow<'a> {
    pub kind: &'a str,
    pub reviewer: &'a str,
    pub caller: &'a str,
    /// `agent-<id>`.
    pub reference: String,
    /// 저장소 이름을 찾을 디렉터리(입력의 cwd, 없으면 현재 디렉터리).
    pub repo_dir: &'a str,
    /// 입력의 session_id 값 그대로(python 은 JSON 값을 그대로 넣는다).
    pub session: Value,
}

/// python `ledger_auto`: 플러그인의 ledger 스크립트가 있으면 행을 덧붙인다. 실패는 넘긴다.
pub fn auto_add(env: &Env, plugin_root: &str, row: &AutoRow<'_>) {
    // python loads the script; a missing one skips the row
    let script = join(
        &join(
            &join(&join(plugin_root, "skills"), "fresh-advisor"),
            "scripts",
        ),
        "review-ledger.py",
    );
    if !is_file(&script) {
        return;
    }
    let Some(repo) = repo_name(row.repo_dir) else {
        return;
    };

    let ts = jiff::Zoned::now()
        .strftime("%Y-%m-%dT%H:%M:%S%z")
        .to_string();
    let rec = Dict::from_pairs(vec![
        ("ts".to_owned(), Value::Str(ts)),
        ("session".to_owned(), row.session.clone()),
        ("repo".to_owned(), Value::Str(repo)),
        ("kind".to_owned(), Value::Str(row.kind.to_owned())),
        ("reviewer".to_owned(), Value::Str(row.reviewer.to_owned())),
        ("trigger".to_owned(), Value::Str(String::new())),
        ("verdict".to_owned(), Value::Str(UNRECORDED.to_owned())),
        ("caller".to_owned(), Value::Str(row.caller.to_owned())),
        ("found".to_owned(), Value::Int(0)),
        ("adopted".to_owned(), Value::Int(0)),
        ("must".to_owned(), Value::Int(0)),
        ("ref".to_owned(), Value::Str(row.reference.clone())),
        ("note".to_owned(), Value::Str(String::new())),
        ("auto".to_owned(), Value::Bool(true)),
    ]);
    append(
        env,
        &format!("{}\n", dumps_dict(&rec, EnsureAscii::No, None)),
    );
}

/// python `repo_name(d)`: `git rev-parse --show-toplevel` 의 이름, 없으면 `d` 의 이름. git 출력이 UTF-8 이 아니면 `None`.
fn repo_name(dir: &str) -> Option<String> {
    let top = match git::run(dir, &["rev-parse", "--show-toplevel"]) {
        Ok(out) => strip(&out.stdout).to_owned(),
        Err(git::GitError::Failed) => String::new(),
        Err(_) => return None,
    };
    Some(pathlib_name(if top.is_empty() { dir } else { &top }))
}

/// python `ledger_path()`: `${XDG_STATE_HOME:-~/.local/state}/claude-second-opinion/ledger.jsonl`.
fn ledger_dir(env: &Env) -> String {
    let base = match env.get_os_nonempty("XDG_STATE_HOME") {
        Some(dir) => from_os(dir),
        None => expanduser("~/.local/state", env),
    };
    pathlib_join(&base, "claude-second-opinion")
}

// python open(p, "a", encoding="utf-8").write(line): 파일은 만들고, 서로게이트가 든 줄은 쓰지 못한다
fn append(env: &Env, line: &str) {
    let dir = ledger_dir(env);
    if makedirs(&dir).is_err() {
        return;
    }
    let Some(path) = os_path(&pathlib_join(&dir, "ledger.jsonl")) else {
        return;
    };
    let Ok(mut file) = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)
    else {
        return;
    };
    if line.chars().any(|c| unit_of(c).is_some()) {
        return;
    }
    if let Some(bytes) = encode_os(line) {
        let _ = file.write_all(&bytes);
    }
}
