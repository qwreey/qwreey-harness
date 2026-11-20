//! python 판과 Rust 판을 같은 상태 위에서 번갈아 돌려도 python 만 돌린 것과 출력, 상태 파일이 같은지 본다.
//!
//! 한 사건 열(commit 알림, 실패 횟수, Stop, 서브에이전트 보고와 알림, 리뷰어 끝의 last-review 와 ledger 행, python 만 맡는
//! PreCompact 와 SessionStart, ambient 보충, track-reviewer)을 세 번 돌린다: 모두 python, 옮긴 훅을 python 과 Rust 가 번갈아,
//! 옮긴 훅은 모두 Rust. 저장소, HOME, 임시 폴더, salt, 스크래치, ledger 는 모두 시험 폴더 안이다. 실제 transcript 는 쓰지 않는다.
//! 시각(float 초, ledger 의 ts)과 run id(uuid4)는 실행마다 달라 자리 표시로 바꿔 비교한다.

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

/// 사건 하나: python 스크립트와 인자, 입력. `rust` 가 없으면 늘 python 이 돈다.
struct Step {
    script: &'static str,
    args: &'static [&'static str],
    rust: Option<&'static [&'static str]>,
    payload: Value,
}

fn repo_root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .canonicalize()
        .expect("repo root")
}

fn plugin_root() -> PathBuf {
    repo_root().join("plugins/qwreey-advisor")
}

/// 한 번 돌릴 시험 폴더.
struct Sandbox {
    root: PathBuf,
}

impl Sandbox {
    fn new(tag: &str) -> Sandbox {
        let root = std::env::temp_dir().join(format!("qa-interleave-{tag}-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&root);
        for dir in ["home", "tmp", "cfg", "repo", "t"] {
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
        std::fs::write(path, text).expect("write");
    }

    fn git(&self, args: &[&str]) {
        let status = Command::new("git")
            .args(args)
            .current_dir(self.path("repo"))
            .envs(self.env())
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .expect("git runs");
        assert!(status.success(), "git {args:?}");
    }

    // 커밋 하나와 커밋 안 된 변경, 서브에이전트 transcript 와 meta
    fn seed(&self) {
        std::fs::write(self.path("salt"), "00".repeat(32)).expect("salt");
        self.write("cfg/harness.env", "HARNESS_REVIEW_LINES=mid=5\n");
        self.git(&["init", "-q", "."]);
        self.write("repo/a.txt", "a\n");
        self.git(&["add", "a.txt"]);
        self.git(&["commit", "-qm", "init"]);
        let lines: String = (1..=20).map(|i| format!("{i}\n")).collect();
        self.write("repo/a.txt", &lines);
        self.write("repo/b.txt", &lines);

        let user = |text: &str| {
            json!({"type": "user", "message": {"role": "user", "content": text}}).to_string()
        };
        self.write("t/agent-w1.jsonl", &format!("{}\n", user("Fix it.")));
        self.write(
            "t/agent-w1.meta.json",
            r#"{"description": "fix it", "spawnDepth": 1}"#,
        );
        let run =
            "[qwreey-advisor run: 0b1f2c3d-aaaa-4bbb-8ccc-123456789012 caller=main scratch=/x/]";
        self.write(
            "t/agent-r1.jsonl",
            &format!("{}\n", user(&format!("Review.\n\n{run}"))),
        );
        self.write(
            "t/agent-r1.meta.json",
            r#"{"description": "second opinion: done", "model": "opus"}"#,
        );
    }

    fn env(&self) -> Vec<(String, String)> {
        let p = |rel: &str| self.path(rel).to_string_lossy().into_owned();
        vec![
            ("PATH".into(), std::env::var("PATH").unwrap_or_default()),
            ("LANG".into(), "C.UTF-8".into()),
            ("TZ".into(), "UTC".into()),
            ("HOME".into(), p("home")),
            ("TMPDIR".into(), p("tmp")),
            ("CLAUDE_CONFIG_DIR".into(), p("cfg")),
            ("HARNESS_ENV".into(), "/nonexistent".into()),
            ("QWREEY_HARNESS_SALT_FILE".into(), p("salt")),
            ("CLAUDE_AUDIT_SCRATCH".into(), p("audit")),
            (
                "CLAUDE_PLUGIN_ROOT".into(),
                plugin_root().to_string_lossy().into_owned(),
            ),
            ("GIT_CONFIG_GLOBAL".into(), "/dev/null".into()),
            ("GIT_CONFIG_NOSYSTEM".into(), "1".into()),
            ("GIT_AUTHOR_NAME".into(), "t".into()),
            ("GIT_AUTHOR_EMAIL".into(), "t@t".into()),
            ("GIT_COMMITTER_NAME".into(), "t".into()),
            ("GIT_COMMITTER_EMAIL".into(), "t@t".into()),
        ]
    }

    fn run(&self, step: &Step, side: Side) -> (i32, String) {
        let mut payload = step.payload.clone();
        let obj = payload.as_object_mut().expect("payload object");
        obj.entry("session_id").or_insert(json!("s1"));
        obj.entry("cwd")
            .or_insert(json!(self.path("repo").to_string_lossy()));
        let input = self.subst(&payload.to_string());

        let mut command = match (side, step.rust) {
            (Side::Rust, Some(args)) => {
                let mut c = Command::new(env!("CARGO_BIN_EXE_qwreey-advisor"));
                c.args(args.iter());
                c
            }
            _ => {
                let mut c = Command::new("python3");
                c.args(["-I", "-X", "utf8"])
                    .arg(plugin_root().join("hooks").join(step.script))
                    .args(step.args);
                c
            }
        };
        let mut child = command
            .env_clear()
            .envs(self.env())
            .current_dir(self.path("repo"))
            .stdin(Stdio::piped())
            .stdout(Stdio::piped())
            .stderr(Stdio::null())
            .spawn()
            .expect("hook runs");
        child
            .stdin
            .take()
            .expect("stdin")
            .write_all(input.as_bytes())
            .expect("write stdin");
        let out = child.wait_with_output().expect("hook ends");
        (
            out.status.code().unwrap_or(-1),
            self.normalize(&String::from_utf8_lossy(&out.stdout)),
        )
    }

    fn subst(&self, text: &str) -> String {
        text.replace("{sandbox}", &self.root.to_string_lossy())
    }

    // 실행마다 다른 것: 시험 폴더 경로, 시각, run id
    fn normalize(&self, text: &str) -> String {
        let text = text.replace(&*self.root.to_string_lossy(), "<sandbox>");
        let mut out = String::new();
        let mut rest = text.as_str();
        while let Some((at, len, mark)) = next_volatile(rest) {
            out.push_str(&rest[..at]);
            out.push_str(mark);
            rest = &rest[at + len..];
        }
        out.push_str(rest);
        out
    }

    /// 상태 파일 전부(임시 폴더, ledger, 스크래치), 경로와 내용 모두 정규화.
    fn state_files(&self) -> BTreeMap<String, String> {
        let mut out = BTreeMap::new();
        for dir in ["tmp", "home", "audit"] {
            collect(&self.path(dir), &self.root, &mut out);
        }
        out.into_iter()
            .map(|(k, v)| (self.normalize(&k), self.normalize(&v)))
            .collect()
    }
}

impl Drop for Sandbox {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.root);
    }
}

// 시각(1으로 시작하는 10자리 초와 소수), ISO 시각, uuid4 의 (자리, 길이, 표시)
fn next_volatile(text: &str) -> Option<(usize, usize, &'static str)> {
    let bytes = text.as_bytes();
    let digits = |from: usize| {
        bytes[from..]
            .iter()
            .take_while(|b| b.is_ascii_digit())
            .count()
    };
    let hex = |from: usize, n: usize| {
        bytes.len() >= from + n
            && bytes[from..from + n]
                .iter()
                .all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase())
    };
    for i in 0..bytes.len() {
        if i > 0 && bytes[i - 1].is_ascii_alphanumeric() {
            continue;
        }
        // Epoch seconds with a fraction
        if bytes[i] == b'1'
            && digits(i) == 10
            && bytes.get(i + 10) == Some(&b'.')
            && digits(i + 11) > 0
        {
            return Some((i, 11 + digits(i + 11), "<time>"));
        }
        // ISO time with a numeric zone
        if digits(i) == 4
            && text.get(i..i + 24).is_some_and(|s| {
                s.as_bytes()[10] == b'T' && (s.as_bytes()[19] == b'+' || s.as_bytes()[19] == b'-')
            })
        {
            return Some((i, 24, "<ts>"));
        }
        // uuid4
        if hex(i, 8)
            && bytes.get(i + 8) == Some(&b'-')
            && hex(i + 9, 4)
            && bytes.get(i + 14) == Some(&b'4')
            && hex(i + 24, 12)
        {
            return Some((i, 36, "<uuid4>"));
        }
    }
    None
}

fn collect(dir: &Path, base: &Path, out: &mut BTreeMap<String, String>) {
    let Ok(entries) = std::fs::read_dir(dir) else {
        return;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        let rel = path
            .strip_prefix(base)
            .expect("under base")
            .to_string_lossy()
            .into_owned();
        if path.is_dir() {
            out.insert(format!("{rel}/"), String::new());
            collect(&path, base, out);
        } else if !rel.ends_with(".lock") {
            out.insert(
                rel,
                String::from_utf8_lossy(&std::fs::read(&path).unwrap_or_default()).into_owned(),
            );
        }
    }
}

const NUDGE: &[&str] = &["hook", "second-opinion-nudge"];
const AMBIENT: &[&str] = &["hook", "ambient", "UserPromptSubmit"];
const TRACK: &[&str] = &["hook", "track-reviewer"];

fn nudge(payload: Value) -> Step {
    Step {
        script: "second-opinion-nudge.py",
        args: &[],
        rust: Some(NUDGE),
        payload,
    }
}

fn steps() -> Vec<Step> {
    let commit = json!({"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "git add -A && git commit -m x"}});
    let failure = json!({"hook_event_name": "PostToolUseFailure", "tool_name": "Bash", "tool_input": {"command": "make"}, "error": "Exit code 2\nboom at 12"});
    let report = |agent: &str, agent_type: &str, last: &str| {
        json!({"hook_event_name": "SubagentStop", "agent_id": agent, "agent_type": agent_type, "last_assistant_message": last,
               "agent_transcript_path": format!("{{sandbox}}/t/agent-{agent}.jsonl")})
    };
    let task = "<task-notification>\n<task-id>w2</task-id>\n<summary>Agent \"plan it\" done</summary>\n<result>I recommend A. Your call.</result>\n</task-notification>";
    vec![
        nudge(commit.clone()),
        nudge(commit.clone()),
        nudge(failure.clone()),
        nudge(failure.clone()),
        nudge(json!({"hook_event_name": "Stop", "last_assistant_message": "Done."})),
        nudge(report(
            "w1",
            "general-purpose",
            "## Recommendations\n- a\n- b",
        )),
        nudge(json!({"hook_event_name": "PostToolBatch", "tool_calls": []})),
        nudge(json!({"hook_event_name": "UserPromptSubmit", "prompt": task})),
        nudge(json!({"hook_event_name": "UserPromptSubmit", "prompt": task})),
        nudge(report("r1", "qwreey-advisor:reviewer", "Findings: none")),
        nudge(json!({"hook_event_name": "PostToolBatch", "tool_calls": []})),
        Step {
            script: "ambient.py",
            args: &["UserPromptSubmit"],
            rust: Some(AMBIENT),
            payload: json!({"hook_event_name": "UserPromptSubmit", "prompt": "hi"}),
        },
        Step {
            script: "compact_epoch.py",
            args: &["qwreey-advisor"],
            rust: None,
            payload: json!({"hook_event_name": "PreCompact", "trigger": "auto"}),
        },
        Step {
            script: "ambient.py",
            args: &["UserPromptSubmit"],
            rust: Some(AMBIENT),
            payload: json!({"hook_event_name": "UserPromptSubmit", "prompt": "hi"}),
        },
        Step {
            script: "ambient.py",
            args: &["UserPromptSubmit"],
            rust: Some(AMBIENT),
            payload: json!({"hook_event_name": "UserPromptSubmit", "prompt": "hi"}),
        },
        Step {
            script: "ambient.py",
            args: &["SessionStart"],
            rust: None,
            payload: json!({"hook_event_name": "SessionStart", "source": "startup", "session_id": "s2"}),
        },
        Step {
            script: "ambient.py",
            args: &["UserPromptSubmit"],
            rust: Some(AMBIENT),
            payload: json!({"hook_event_name": "UserPromptSubmit", "prompt": "hi", "session_id": "s2"}),
        },
        nudge(failure.clone()),
        nudge(failure),
        nudge(
            json!({"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "git commit -am y"}, "session_id": "s3"}),
        ),
        Step {
            script: "track-reviewer.py",
            args: &[],
            rust: Some(TRACK),
            payload: json!({"hook_event_name": "PreToolUse", "tool_name": "Agent", "tool_input": {"subagent_type": "qwreey-advisor:reviewer", "prompt": "Review."}}),
        },
    ]
}

/// 사건 열을 한 번 돌린다. `pick(i)` 는 옮긴 i 번째 사건을 누가 돌릴지.
fn play(tag: &str, pick: impl Fn(usize) -> Side) -> (Vec<(i32, String)>, BTreeMap<String, String>) {
    let sb = Sandbox::new(tag);
    let mut ported = 0;
    let mut outputs = Vec::new();
    for step in steps() {
        let side = if step.rust.is_some() {
            ported += 1;
            pick(ported - 1)
        } else {
            Side::Python
        };
        outputs.push(sb.run(&step, side));
    }
    (outputs, sb.state_files())
}

/// 모두 python, 번갈아, 모두 Rust 가 같은 출력과 같은 상태 파일을 남긴다.
#[test]
fn python_and_rust_interleave_on_the_same_state() {
    // Three runs over the same event sequence
    let (py_out, py_files) = play("py", |_| Side::Python);
    let (alt_out, alt_files) = play(
        "alt",
        |i| if i % 2 == 0 { Side::Rust } else { Side::Python },
    );
    let (rs_out, rs_files) = play("rs", |_| Side::Rust);

    // The sequence notifies where expected
    let notified: Vec<bool> = py_out
        .iter()
        .map(|(_, out)| !out.trim().is_empty())
        .collect();
    assert!(notified[0], "first commit over the limit notifies");
    assert!(!notified[1], "the same diff notifies once");
    assert!(notified[3], "the second same failure notifies");
    assert!(
        notified[6],
        "the batch after a recommending report notifies"
    );
    assert!(
        notified[7] && !notified[8],
        "the task notification notifies once"
    );
    assert!(
        py_files.keys().any(|k| k.ends_with("ledger.jsonl")),
        "the reviewer stop wrote a ledger row"
    );

    // Byte-identical outputs and state files
    for (i, ((py, alt), rs)) in py_out.iter().zip(&alt_out).zip(&rs_out).enumerate() {
        assert_eq!(py, alt, "step {} output, alternating", i + 1);
        assert_eq!(py, rs, "step {} output, all Rust", i + 1);
    }
    assert_eq!(py_files, alt_files, "state files, alternating");
    assert_eq!(py_files, rs_files, "state files, all Rust");
}
