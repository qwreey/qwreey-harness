//! 게이트 상태 파일과 deny.log(python `read_state`, `write_state`, `log_deny`).
//!
//! 상태 파일은 (세션, agent_id, compact 회차)마다 하나다: `<임시 폴더>/claude-workspace-gate/<sid>.c<회차>[.a<agent>].json`.
//! 내용은 `{"loaded": true}`(스킬을 불렀다), `{"warned": true}`(읽기 알림을 냈다). python 판과 같은 꼴로 읽고 쓴다.

use std::io::Write;

use harness_hook::py::fs;
use harness_hook::py::json::{EnsureAscii, dumps};
use harness_hook::py::json_load::loads;
use harness_hook::py::ospath::join;
use harness_hook::py::surrogate::unit_of;
use harness_hook::py::value::Value;

use crate::stop::{Result, Stop};

/// 상태 파일 하나의 값. python 은 JSON 이면 무엇이든 받으므로 dict 가 아닐 수도 있다.
pub struct State {
    path: String,
    value: Value,
}

impl State {
    /// python `read_state(p)`: 읽지 못하거나 JSON 이 아니면 빈 dict.
    pub fn read(path: String) -> State {
        let value = fs::read_text(&path)
            .ok()
            .and_then(|text| loads(&text).ok())
            .unwrap_or_else(|| Value::Dict(Default::default()));
        State { path, value }
    }

    /// `st.get(key)` 가 참인가. dict 가 아니면 python 은 AttributeError 다.
    pub fn flag(&self, key: &str) -> Result<bool> {
        match &self.value {
            Value::Dict(d) => Ok(d.get(key).is_some_and(Value::truthy)),
            _ => Err(Stop::Raises("the state file is not a JSON object")),
        }
    }

    /// `st[key] = True` 한 뒤 python `write_state`: 쓰기 실패는 넘긴다.
    pub fn set_and_write(&mut self, key: &str) -> Result<()> {
        let Value::Dict(d) = &mut self.value else {
            return Err(Stop::Raises("the state file is not a JSON object"));
        };
        d.insert(key, Value::Bool(true));
        let _ = fs::write_text(&self.path, &dumps(&self.value, EnsureAscii::Yes, None));
        Ok(())
    }
}

/// python `log_deny`: `<임시 폴더>/<ns>/deny.log` 에 한 줄을 더한다. 실패는 넘긴다.
///
/// 줄: `<이 기기 시각 %F %T> sid=<id> agent=<id> repo=<루트> <설명>`. 짝 없는 서로게이트는 python
/// `errors="backslashreplace"` 처럼 `\udcXX` 로 쓴다.
pub fn log_deny(state_dir: &str, sid: &str, agent: &str, repo: &str, what: &str) {
    let now = jiff::Zoned::now().strftime("%F %T").to_string();
    let line = backslash_surrogates(&format!(
        "{now} sid={sid} agent={agent} repo={repo} {what}\n"
    ));
    let Some(dir) = fs::os_path(state_dir) else {
        return;
    };
    if std::fs::create_dir_all(dir).is_err() {
        return;
    }
    let Some(log) = fs::os_path(&join(state_dir, "deny.log")) else {
        return;
    };
    if let Ok(mut file) = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(log)
    {
        let _ = file.write_all(line.as_bytes());
    }
}

fn backslash_surrogates(text: &str) -> String {
    let mut out = String::with_capacity(text.len());
    for c in text.chars() {
        match unit_of(c) {
            Some(unit) => out.push_str(&format!("\\u{unit:04x}")),
            None => out.push(c),
        }
    }
    out
}
