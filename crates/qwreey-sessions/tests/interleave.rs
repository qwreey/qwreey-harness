//! python 판과 Rust 판을 같은 상태 위에서 번갈아 돌려도 python 만 돌린 것과 출력, 상태 파일이 같은지 본다.
//!
//! 한 사건 열(PreToolUse commit, PostToolUse 요약 알림과 워커 띄우기, UserPromptSubmit 인계, records-read, python 만 맡는
//! PreCompact 와 SessionStart)을 세 번 돌린다: 모두 python, 옮긴 이벤트를 python 과 Rust 가 번갈아, 옮긴 이벤트는 모두 Rust.
//! 워커는 띄우지 않는다: PATH 맨 앞의 가짜 `setsid` 가 받은 명령줄만 적는다. 그래서 워커 명령줄도 비교한다.
//! 저장소, HOME, 임시 폴더, salt 는 모두 시험 폴더 안이다. 실제 트랜스크립트와 실제 session-log 저장소는 건드리지 않는다.

use std::collections::BTreeMap;
use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

use serde_json::{Value, json};

/// 사건 하나를 누가 돌리나.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Side {
    Python,
    Rust,
}

/// 사건 하나: 훅, 이벤트 인자, 입력. `ported` 가 거짓이면 늘 python 이 돈다.
struct Step {
    script: &'static str,
    event: &'static str,
    payload: Value,
    ported: bool,
    /// 이 사건 앞에 할 일(알림 큐에 줄 더하기 등).
    before: Option<fn(&Sandbox)>,
}

fn repo_root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .canonicalize()
        .expect("repo root")
}

/// 한 번 돌릴 시험 폴더.
struct Sandbox {
    root: PathBuf,
}

impl Sandbox {
    fn new(tag: &str) -> Sandbox {
        let root = std::env::temp_dir().join(format!("qs-interleave-{tag}-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&root);
        for dir in ["home", "tmp", "store", "repo/.claude", "bin", "cfg"] {
            std::fs::create_dir_all(root.join(dir)).expect("sandbox dir");
        }
        let root = root.canonicalize().expect("sandbox root");
        let sandbox = Sandbox { root };
        sandbox.seed();
        sandbox
    }

    fn path(&self, rel: &str) -> PathBuf {
        self.root.join(rel)
    }

    fn write(&self, rel: &str, text: &str) {
        let path = self.path(rel);
        std::fs::create_dir_all(path.parent().expect("parent")).expect("parent dir");
        std::fs::write(path, text).expect("fixture");
    }

    fn store_dir(&self) -> PathBuf {
        let repo = self.path("repo").to_string_lossy().into_owned();
        let key: String = repo
            .chars()
            .map(|c| if c.is_ascii_alphanumeric() { c } else { '-' })
            .collect();
        self.path("store").join(key)
    }

    // git 저장소, 외부 저장소(pending 기록, 알림 큐, 워커 상태), 512 KB 넘는 트랜스크립트, 가짜 setsid
    fn seed(&self) {
        let git = Command::new("git")
            .args(["init", "-q"])
            .arg(self.path("repo"))
            .status()
            .expect("git init");
        assert!(git.success());
        self.write("salt", &"00".repeat(32));
        self.write(
            "repo/.claude/session-log.json",
            r#"{"records_home": "docs/sessions"}"#,
        );

        let store = self.store_dir();
        let index = json!({
            "2026-01-02-s8aaaaaa": {"created": "2026-01-02T09:00:00", "status": "pending"},
            "2026-11-01-s1aaaaaa": {"created": "2026-11-01T01:00:00", "status": "imported", "sections": 2, "imported_sections": 1},
        });
        std::fs::create_dir_all(store.join(".state")).expect("store");
        std::fs::write(store.join("index.json"), index.to_string()).expect("index");
        let notice =
            json!({"seq": 1, "rids": ["2026-11-01-s1aaaaaa"], "sections": 2, "flagged": 0});
        std::fs::write(store.join(".state/notices.jsonl"), format!("{notice}\n")).expect("notices");
        std::fs::write(store.join(".state/notice.seq"), "1").expect("seq");
        std::fs::write(
            store.join(".state/s1.json"),
            r#"{"offset": 5, "line": 9, "last_run": 0}"#,
        )
        .expect("ws");

        let line = json!({"type": "user", "message": {"role": "user", "content": "x".repeat(200)}})
            .to_string();
        self.write("t.jsonl", &format!("{line}\n").repeat(3000));
        self.write("bin/setsid", "#!/bin/sh\nfor a in \"$@\"; do printf '%s\\037' \"$a\"; done >> \"$SPAWN_LOG\"\necho >> \"$SPAWN_LOG\"\n");
        let mut perms = std::fs::metadata(self.path("bin/setsid"))
            .expect("stub")
            .permissions();
        std::os::unix::fs::PermissionsExt::set_mode(&mut perms, 0o755);
        std::fs::set_permissions(self.path("bin/setsid"), perms).expect("chmod");
    }

    fn env(&self) -> Vec<(String, String)> {
        let path = format!(
            "{}:{}",
            self.path("bin").display(),
            std::env::var("PATH").unwrap_or_else(|_| "/usr/bin:/bin".to_owned())
        );
        let s = |rel: &str| self.path(rel).to_string_lossy().into_owned();
        vec![
            ("PATH".into(), path),
            ("LANG".into(), "C.UTF-8".into()),
            ("HOME".into(), s("home")),
            ("TMPDIR".into(), s("tmp")),
            ("CLAUDE_CONFIG_DIR".into(), s("cfg")),
            ("CLAUDE_PROJECT_DIR".into(), s("repo")),
            (
                "CLAUDE_PLUGIN_ROOT".into(),
                repo_root()
                    .join("plugins/qwreey-sessions")
                    .to_string_lossy()
                    .into_owned(),
            ),
            ("QWREEY_HARNESS_SALT_FILE".into(), s("salt")),
            ("XDG_DATA_HOME".into(), s("home/.local/share")),
            ("SESSION_LOG_HOME".into(), s("store")),
            ("SESSION_LOG_CLAUDE".into(), "/bin/false".into()),
            ("HARNESS_ENV".into(), "/nonexistent".into()),
            ("CLAUDE_CODE_ENTRYPOINT".into(), "cli".into()),
            ("SPAWN_LOG".into(), s("spawn.log")),
        ]
    }

    fn run(&self, step: &Step, side: Side) -> (i32, String) {
        let mut payload = step.payload.clone();
        let map = payload.as_object_mut().expect("payload object");
        map.insert("hook_event_name".into(), json!(step.event));
        map.entry("cwd").or_insert(json!(self.path("repo")));
        map.entry("transcript_path")
            .or_insert(json!(self.path("t.jsonl")));
        self.run_raw(step.script, step.event, side, &payload.to_string())
    }

    /// 입력 글 그대로(짝 없는 서로게이트 escape 등 serde_json 이 만들 수 없는 꼴도) 훅 하나를 돌린다.
    fn run_raw(&self, script: &str, event: &str, side: Side, input: &str) -> (i32, String) {
        let mut command = match side {
            Side::Python => {
                let mut c = Command::new("python3");
                c.args(["-I", "-X", "utf8"])
                    .arg(
                        repo_root()
                            .join("plugins/qwreey-sessions/scripts")
                            .join(script),
                    )
                    .arg(event);
                c
            }
            Side::Rust => {
                let sub = if script == "hook.py" {
                    "session-log"
                } else {
                    "records-read"
                };
                let mut c = Command::new(env!("CARGO_BIN_EXE_qwreey-sessions"));
                c.args(["hook", sub, event]);
                c
            }
        };
        let mut child = command
            .env_clear()
            .envs(self.env())
            .current_dir(self.path("repo"))
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .expect("start hook");
        child
            .stdin
            .take()
            .expect("stdin")
            .write_all(input.as_bytes())
            .expect("write input");
        let out = child.wait_with_output().expect("hook output");
        (
            out.status.code().unwrap_or(-1),
            self.normalize(&String::from_utf8_lossy(&out.stdout)),
        )
    }

    fn normalize(&self, text: &str) -> String {
        let root = self.root.to_string_lossy().into_owned();
        let key: String = root
            .chars()
            .map(|c| if c.is_ascii_alphanumeric() { c } else { '-' })
            .collect();
        text.replace(&root, "<sandbox>")
            .replace(&key, "<sandbox-key>")
    }

    /// 상태 파일들: 상대 경로 -> 내용(시각 값은 지운다). 규칙 줄 claim 폴더는 30초 칸 이름이라 뺀다.
    fn state_files(&self) -> BTreeMap<String, String> {
        let mut out = BTreeMap::new();
        for top in ["store", "tmp", "home"] {
            collect(&self.path(top), &self.root, &mut out);
        }
        out.retain(|rel, _| !rel.starts_with("tmp/claude-harness-rule"));

        // 오류 기록은 있고 없음만 본다(줄의 꼴은 두 판이 다르다: 예외 이름 대 Abort 까닭)
        if let Some(log) = out.get_mut("store/hook-errors.log") {
            *log = "<logged>".to_owned();
        }

        // 경로와 시각을 지운다. 훅 상태는 python indent=1 꼴 그대로(한 줄에 키 하나) 바이트로 비교한다
        let mut out: BTreeMap<String, String> = out
            .into_iter()
            .map(|(rel, text)| (self.normalize(&rel), self.normalize(&text)))
            .collect();
        for (rel, text) in out.iter_mut() {
            if rel.ends_with(".hook.json") {
                *text = text
                    .lines()
                    .map(|line| match line.split_once(": ") {
                        Some((key, _))
                            if key == " \"last_spawn\"" || key == " \"errors_checked\"" =>
                        {
                            format!(
                                "{key}: <time>{}",
                                if line.ends_with(',') { "," } else { "" }
                            )
                        }
                        _ => line.to_owned(),
                    })
                    .collect::<Vec<_>>()
                    .join("\n");
            }
        }
        if let Ok(log) = std::fs::read_to_string(self.path("spawn.log")) {
            out.insert("spawn.log".into(), self.normalize(&log));
        }
        out
    }
}

impl Drop for Sandbox {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.root);
    }
}

fn collect(dir: &Path, base: &Path, out: &mut BTreeMap<String, String>) {
    let Ok(entries) = std::fs::read_dir(dir) else {
        return;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        if path.is_dir() {
            collect(&path, base, out);
        } else {
            let rel = path
                .strip_prefix(base)
                .expect("under base")
                .to_string_lossy()
                .into_owned();
            let text = std::fs::read(&path)
                .map(|b| String::from_utf8_lossy(&b).into_owned())
                .unwrap_or_default();
            out.insert(rel, text);
        }
    }
}

fn add_notice(sb: &Sandbox) {
    let state = sb.store_dir().join(".state");
    let notice = json!({"seq": 2, "rids": ["2026-11-20-s1aaaaaa"], "sections": 1, "flagged": 1});
    let mut f = std::fs::OpenOptions::new()
        .append(true)
        .open(state.join("notices.jsonl"))
        .expect("notices");
    writeln!(f, "{notice}").expect("append notice");
    std::fs::write(state.join("notice.seq"), "2\n").expect("seq");
}

fn steps() -> Vec<Step> {
    let commit = json!({"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": "git commit -m x"}});
    let read_record = |sid: &str| json!({"session_id": sid, "tool_name": "Read", "tool_input": {"file_path": "<store-record>"}});
    let step = |script, event, payload: Value, ported| Step {
        script,
        event,
        payload,
        ported,
        before: None,
    };
    vec![
        step(
            "hook.py",
            "SessionStart",
            json!({"session_id": "s1", "source": "startup"}),
            false,
        ),
        step("hook.py", "PreToolUse", commit.clone(), true),
        step(
            "hook.py",
            "PostToolUse",
            json!({"session_id": "s1", "tool_name": "Read"}),
            true,
        ),
        step(
            "hook.py",
            "UserPromptSubmit",
            json!({"session_id": "s1", "prompt": "/checkpoint"}),
            true,
        ),
        step("hook.py", "PreToolUse", commit.clone(), true),
        step("records_read.py", "PostToolUse", read_record("s1"), true),
        step("records_read.py", "PostToolUse", read_record("s1"), true),
        step(
            "hook.py",
            "PreCompact",
            json!({"session_id": "s1", "trigger": "manual"}),
            false,
        ),
        step("hook.py", "PreToolUse", commit.clone(), true),
        step("records_read.py", "PostToolUse", read_record("s1"), true),
        Step {
            before: Some(add_notice),
            ..step(
                "hook.py",
                "PostToolUse",
                json!({"session_id": "s1", "tool_name": "Bash"}),
                true,
            )
        },
        step(
            "hook.py",
            "UserPromptSubmit",
            json!({"session_id": "s1", "prompt": "/checkpoint"}),
            true,
        ),
        step(
            "hook.py",
            "SessionStart",
            json!({"session_id": "s1", "source": "resume"}),
            false,
        ),
        step(
            "hook.py",
            "UserPromptSubmit",
            json!({"session_id": "s2", "prompt": "핸드오버 하자 handover"}),
            true,
        ),
        step(
            "hook.py",
            "PostToolUse",
            json!({"session_id": "s2", "tool_name": "Bash"}),
            true,
        ),
        step("records_read.py", "PreToolUse", read_record("s2"), true),
    ]
}

/// 사건 열을 돌린 출력과 상태. `pick(i)` 은 i 번째 옮긴 사건을 누가 돌릴지.
fn play(tag: &str, pick: impl Fn(usize) -> Side) -> (Vec<(i32, String)>, BTreeMap<String, String>) {
    let sb = Sandbox::new(tag);
    let record = sb.store_dir().join("records/2026-11-01-s1aaaaaa.md");
    std::fs::create_dir_all(record.parent().expect("records")).expect("records dir");
    std::fs::write(&record, "x\n").expect("record");

    let mut outputs = Vec::new();
    let mut ported = 0;
    for step in steps() {
        if let Some(before) = step.before {
            before(&sb);
        }
        let side = if step.ported {
            ported += 1;
            pick(ported)
        } else {
            Side::Python
        };
        let mut step = step;
        if let Some(input) = step
            .payload
            .get_mut("tool_input")
            .and_then(Value::as_object_mut)
            && input.get("file_path") == Some(&json!("<store-record>"))
        {
            input.insert("file_path".into(), json!(record));
        }
        outputs.push(sb.run(&step, side));
    }
    (outputs, sb.state_files())
}

#[test]
fn python_and_rust_interleave_on_the_same_state() {
    let (py_out, py_state) = play("py", |_| Side::Python);
    let (mix_out, mix_state) = play(
        "mix",
        |i| if i % 2 == 0 { Side::Rust } else { Side::Python },
    );
    let (rust_out, rust_state) = play("rust", |_| Side::Rust);

    // 사건 열이 시험할 것을 실제로 거치는가
    let joined: String = py_out.iter().map(|(_, o)| o.as_str()).collect();
    for want in [
        "saved 1 new section to",
        "1 item failed",
        "summarizing this session (L10",
        "summarizing this session (L1\u{2013}",
        "(Not blocking.)",
        "A handover is a good time",
        "snapshots",
    ] {
        assert!(
            joined.contains(want),
            "sequence does not reach {want:?}:\n{joined}"
        );
    }
    assert!(
        py_state.contains_key("spawn.log"),
        "no worker command was recorded"
    );

    for (name, out, state) in [
        ("interleaved", &mix_out, &mix_state),
        ("rust", &rust_out, &rust_state),
    ] {
        for (i, (want, got)) in py_out.iter().zip(out.iter()).enumerate() {
            assert_eq!(want, got, "{name}: step {} output differs", i + 1);
        }
        assert_eq!(&py_state, state, "{name}: state files differ");
    }
}

/// 꼴이 어긋난 입력과 상태: python 이 예외로 끝나는 곳에서 Rust 도 아무것도 내지 않고, python 이 받는 곳에서는 같은 출력.
#[test]
fn odd_inputs_match_python() {
    let cases: &[(&str, &str, &str)] = &[
        (
            "hook.py",
            "PreToolUse",
            r#"{"session_id": "s\udc80", "tool_name": "Bash", "tool_input": {"command": "git commit"}}"#,
        ),
        (
            "hook.py",
            "PreToolUse",
            r#"{"session_id": "s\ud800", "tool_name": "Bash", "tool_input": {"command": "git commit"}}"#,
        ),
        (
            "hook.py",
            "PreToolUse",
            r#"{"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": "git 😀 commit; git commit"}}"#,
        ),
        (
            "hook.py",
            "PreToolUse",
            r#"{"session_id": "s1", "tool_name": "Bash", "tool_input": "git commit"}"#,
        ),
        (
            "hook.py",
            "PreToolUse",
            r#"{"session_id": "s1", "tool_name": "Skill", "tool_input": {"skill": 7}}"#,
        ),
        (
            "hook.py",
            "PreToolUse",
            r#"{"session_id": true, "tool_name": "Bash", "tool_input": {"command": "git commit"}}"#,
        ),
        (
            "hook.py",
            "PreToolUse",
            r#"{"session_id": 1.5, "tool_name": "Bash", "tool_input": {"command": "git commit"}}"#,
        ),
        (
            "hook.py",
            "PreToolUse",
            r#"{"session_id": "", "tool_name": "Bash", "tool_input": {"command": "git commit"}}"#,
        ),
        (
            "hook.py",
            "PostToolUse",
            r#"{"session_id": "s1", "transcript_path": 1.5}"#,
        ),
        (
            "hook.py",
            "PostToolUse",
            r#"{"session_id": "s1", "transcript_path": "/no\u0000pe"}"#,
        ),
        ("hook.py", "PostToolUse", r#"[1, 2]"#),
        ("hook.py", "PostToolUse", r#"{"session_id": "s1""#),
        (
            "hook.py",
            "UserPromptSubmit",
            r#"{"session_id": "s1", "prompt": null}"#,
        ),
        (
            "hook.py",
            "UserPromptSubmit",
            r#"{"session_id": "s1", "prompt": "\ud800 handover"}"#,
        ),
        (
            "hook.py",
            "UserPromptSubmit",
            r#"{"session_id": "s1", "prompt": "/checkpoint", "cwd": "/"}"#,
        ),
        (
            "records_read.py",
            "PostToolUse",
            r#"{"session_id": "s\udcff", "tool_name": "Read", "tool_input": {"file_path": "<store-record>"}}"#,
        ),
        (
            "records_read.py",
            "PostToolUse",
            r#"{"session_id": "s1", "agent_id": 3, "tool_name": "Read", "tool_input": {"file_path": "<store-record>"}}"#,
        ),
        (
            "records_read.py",
            "PreToolUse",
            r#"{"session_id": "s1", "tool_name": "Read", "tool_input": {"file_path": "<big>\udc80"}}"#,
        ),
        (
            "records_read.py",
            "PreToolUse",
            r#"{"session_id": "s1", "tool_name": "Read", "tool_input": {"file_path": "", "path": "<big>"}}"#,
        ),
        (
            "records_read.py",
            "PreToolUse",
            r#"{"session_id": "s1", "cwd": 4, "tool_name": "Read", "tool_input": {"file_path": "/x/.claude/plan/big.md"}}"#,
        ),
    ];

    // 경우마다 새 시험 폴더 둘에서 python 과 Rust
    for (i, (script, event, raw)) in cases.iter().enumerate() {
        let mut outputs = Vec::new();
        for side in [Side::Python, Side::Rust] {
            let sb = Sandbox::new(&format!("odd{i}-{side:?}"));
            let record = sb.store_dir().join("records/r.md");
            std::fs::create_dir_all(record.parent().expect("records")).expect("records dir");
            std::fs::write(&record, "x\n").expect("record");
            sb.write("repo/.claude/audit/1/big.md", &"y".repeat(40_000));
            let big = sb.path("repo/.claude/audit/1/big.md");
            let raw = raw
                .replace("<store-record>", &record.to_string_lossy())
                .replace("<big>", &big.to_string_lossy());
            let (rc, out) = sb.run_raw(script, event, side, &raw);
            outputs.push((rc, out, sb.state_files()));
        }

        assert_eq!(outputs[0].0, outputs[1].0, "case {i}: exit code");
        assert_eq!(outputs[0].1, outputs[1].1, "case {i}: output of {raw}");
        assert_eq!(outputs[0].2, outputs[1].2, "case {i}: state files of {raw}");
    }
}
