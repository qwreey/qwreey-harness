//! python 판과 Rust 판을 같은 상태 위에서 번갈아 돌려도 python 만 돌린 것과 출력, 상태 파일이 같은지 본다.
//!
//! 한 사건 열(언어 묻기, 도구 호출 세기와 알림, 도구 사이 글의 이탈, Stop 막기와 통과)을 세 번 돌린다: 모두 python, 번갈아,
//! 모두 Rust. HOME, 임시 폴더, 데이터 폴더, salt, transcript 는 모두 시험 폴더 안이다. 로그의 시각(ts)은 자리 표시로 바꾼다.

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

/// 사건 하나: 입력, 그리고 그 앞에 쓸 파일(저장소 기준 경로, 내용).
struct Step {
    payload: Value,
    write: Option<(&'static str, String)>,
}

fn plugin_root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../plugins/qwreey-reply-language")
        .canonicalize()
        .expect("plugin root")
}

/// 한 번 돌릴 시험 폴더.
struct Sandbox {
    root: PathBuf,
}

impl Sandbox {
    fn new(tag: &str) -> Sandbox {
        let root =
            std::env::temp_dir().join(format!("qrl-interleave-{tag}-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&root);
        for dir in ["home", "tmp", "cfg", "data", "proj/.claude"] {
            std::fs::create_dir_all(root.join(dir)).expect("sandbox dir");
        }
        let root = root.canonicalize().expect("sandbox root");
        std::fs::write(root.join("salt"), "00".repeat(32)).expect("salt");
        Sandbox { root }
    }

    fn path(&self, rel: &str) -> PathBuf {
        self.root.join(rel)
    }

    fn env(&self) -> Vec<(&'static str, String)> {
        let p = |rel: &str| self.path(rel).to_string_lossy().into_owned();
        vec![
            ("PATH", std::env::var("PATH").unwrap_or_default()),
            ("LANG", "C.UTF-8".into()),
            ("HOME", p("home")),
            ("TMPDIR", p("tmp")),
            ("CLAUDE_CONFIG_DIR", p("cfg")),
            ("CLAUDE_PROJECT_DIR", p("proj")),
            ("CLAUDE_PLUGIN_DATA", p("data")),
            ("HARNESS_ENV", "/nonexistent".into()),
            ("QWREEY_HARNESS_SALT_FILE", p("salt")),
            (
                "CLAUDE_PLUGIN_ROOT",
                plugin_root().to_string_lossy().into_owned(),
            ),
        ]
    }

    fn run(&self, step: &Step, side: Side) -> String {
        // Files this step expects, then the hook
        if let Some((rel, text)) = &step.write {
            let path = self.path(rel);
            std::fs::create_dir_all(path.parent().expect("parent")).expect("dir");
            std::fs::write(
                path,
                text.replace("{sandbox}", &self.root.to_string_lossy()),
            )
            .expect("write");
        }
        let mut payload = step.payload.clone();
        let obj = payload.as_object_mut().expect("payload object");
        obj.entry("session_id").or_insert(json!("s1"));
        obj.entry("cwd")
            .or_insert(json!(self.path("proj").to_string_lossy()));
        let input = payload
            .to_string()
            .replace("{sandbox}", &self.root.to_string_lossy());

        let mut command = match side {
            Side::Rust => {
                let mut c = Command::new(env!("CARGO_BIN_EXE_qwreey-reply-language"));
                c.args(["hook", "reply-language"]);
                c
            }
            Side::Python => {
                let mut c = Command::new("python3");
                c.args(["-I", "-X", "utf8"])
                    .arg(plugin_root().join("hooks/reply_language.py"));
                c
            }
        };
        let mut child = command
            .env_clear()
            .envs(self.env())
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
            .expect("stdin write");
        let out = child.wait_with_output().expect("hook ends");
        assert_eq!(out.status.code(), Some(0), "the hook always exits 0");
        self.normalize(&String::from_utf8_lossy(&out.stdout))
    }

    // 시험 폴더 경로와 로그의 정수 초(`"ts": 17...`)
    fn normalize(&self, text: &str) -> String {
        let text = text.replace(&*self.root.to_string_lossy(), "<sandbox>");
        let mut out = String::new();
        let mut rest = text.as_str();
        while let Some(at) = rest.find("\"ts\": ") {
            let (head, tail) = rest.split_at(at + 6);
            out.push_str(head);
            out.push_str("<ts>");
            rest = tail.trim_start_matches(|c: char| c.is_ascii_digit());
        }
        out.push_str(rest);
        out
    }

    fn state_files(&self) -> BTreeMap<String, String> {
        let mut out = BTreeMap::new();
        for dir in ["tmp", "data"] {
            let Ok(walk) = walk(&self.path(dir)) else {
                continue;
            };
            for path in walk {
                let rel = path
                    .strip_prefix(&self.root)
                    .expect("under root")
                    .to_string_lossy()
                    .into_owned();
                let text =
                    String::from_utf8_lossy(&std::fs::read(&path).unwrap_or_default()).into_owned();
                out.insert(rel, self.normalize(&text));
            }
        }
        out
    }
}

impl Drop for Sandbox {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.root);
    }
}

fn walk(dir: &Path) -> std::io::Result<Vec<PathBuf>> {
    let mut out = Vec::new();
    for entry in std::fs::read_dir(dir)? {
        let path = entry?.path();
        if path.is_dir() {
            out.extend(walk(&path)?);
        } else {
            out.push(path);
        }
    }
    Ok(out)
}

const EN: &str =
    "I read the file and added the function. The tests pass and nothing else needs attention.";
const KO: &str = "파일을 읽고 함수를 추가했습니다. 테스트도 통과했고 따로 걸리는 점은 없습니다.";

fn line(kind: &str, text: &str) -> String {
    json!({"type": kind, "message": {"content": [{"type": "text", "text": text}]}}).to_string()
        + "\n"
}

fn steps() -> Vec<Step> {
    let batch = |n: usize, pid: &str| {
        json!({"hook_event_name": "PostToolBatch", "prompt_id": pid, "tool_calls": vec![json!({}); n],
                                             "transcript_path": "{sandbox}/t.jsonl"})
    };
    let plain = |payload: Value| Step {
        payload,
        write: None,
    };
    vec![
        plain(json!({"hook_event_name": "UserPromptSubmit", "prompt": "hi"})),
        plain(json!({"hook_event_name": "UserPromptSubmit", "prompt": "hi"})),
        Step {
            payload: batch(4, "p1"),
            write: Some((
                "proj/.claude/settings.json",
                r#"{"language": "Korean"}"#.to_owned(),
            )),
        },
        Step {
            payload: batch(7, "p1"),
            write: Some(("t.jsonl", line("user", "고쳐 줘") + &line("assistant", EN))),
        },
        plain(batch(2, "p1")),
        Step {
            payload: batch(1, "p1"),
            write: Some((
                "t.jsonl",
                line("user", "고쳐 줘")
                    + &line("assistant", EN)
                    + &line("assistant", KO)
                    + &line("assistant", EN),
            )),
        },
        plain(batch(16, "p1")),
        plain(batch(1, "p2")),
        plain(
            json!({"hook_event_name": "Stop", "last_assistant_message": EN, "transcript_path": "{sandbox}/t.jsonl"}),
        ),
        plain(
            json!({"hook_event_name": "Stop", "last_assistant_message": EN, "stop_hook_active": true}),
        ),
        Step {
            payload: json!({"hook_event_name": "Stop", "last_assistant_message": EN, "transcript_path": "{sandbox}/e.jsonl"}),
            write: Some(("e.jsonl", line("user", "please fix it"))),
        },
    ]
}

fn play(tag: &str, pick: impl Fn(usize) -> Side) -> (Vec<String>, BTreeMap<String, String>) {
    let sb = Sandbox::new(tag);
    let outputs = steps()
        .iter()
        .enumerate()
        .map(|(i, s)| sb.run(s, pick(i)))
        .collect();
    (outputs, sb.state_files())
}

/// 모두 python, 번갈아, 모두 Rust 가 같은 출력과 같은 상태 파일(세션 상태, drift.jsonl)을 남긴다.
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
    assert!(
        py_out[0].contains("No reply language is configured") && py_out[1].is_empty(),
        "asks once"
    );
    assert!(
        py_out[3].contains("Reply to the user in Korean."),
        "the tenth call reminds"
    );
    assert!(
        py_out[8].contains("\"decision\": \"block\""),
        "an English reply to a Korean prompt is blocked"
    );
    assert!(
        py_out[10].is_empty(),
        "an English prompt lets an English reply through"
    );
    assert!(
        py_files.keys().any(|k| k.ends_with("drift.jsonl")),
        "the log is written"
    );

    // Byte-identical outputs and state files
    for (i, ((py, alt), rs)) in py_out.iter().zip(&alt_out).zip(&rs_out).enumerate() {
        assert_eq!(py, alt, "step {} output, alternating", i + 1);
        assert_eq!(py, rs, "step {} output, all Rust", i + 1);
    }
    assert_eq!(py_files, alt_files, "state files, alternating");
    assert_eq!(py_files, rs_files, "state files, all Rust");
}
