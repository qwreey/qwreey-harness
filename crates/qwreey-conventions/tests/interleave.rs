//! python 판과 Rust 판을 같은 상태 위에서 번갈아 돌려도 python 만 돌린 것과 출력, 상태 파일이 같은지 본다.
//!
//! 한 사건 열(Bash 앞 알림과 스냅숏, 명령, Bash 뒤 검사와 rule 주입, Read 뒤 rule 주입, Edit 뒤 줄 검사, python 만 맡는
//! PreCompact)을 네 번 돌린다: 모두 python, 옮긴 훅을 python 부터 번갈아, Rust 부터 번갈아, 옮긴 훅은 모두 Rust.
//! 번갈아 돌리면 한 명령의 PreToolUse 스냅숏을 한 판이 적고 PostToolUse 에서 다른 판이 읽는다(세션이 다시 읽는 사이와 같다).
//! 저장소, HOME, 임시 폴더, salt, 플러그인 폴더(실제 폴더로 가는 링크와 바이너리 사본)는 모두 시험 폴더 안이다.

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

/// 사건 하나.
enum Act {
    /// 훅 하나(`ported` 가 거짓이면 늘 python).
    Hook {
        name: &'static str,
        ported: bool,
        payload: Value,
    },
    /// 저장소에서 돌리는 명령(모델의 Bash 자리).
    Sh(&'static str),
}

fn repo_root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .canonicalize()
        .expect("repo root")
}

/// 훅 이름 -> python 스크립트와 인자.
fn script(name: &str) -> (&'static str, &'static [&'static str]) {
    match name {
        "bash-bypass-reminder" => ("bash-bypass-reminder.py", &[]),
        "bash-writes" => ("bash_writes.py", &[]),
        "rules-inject" => ("rules_inject.py", &[]),
        "conventions-check" => ("conventions-check.py", &[]),
        "compact-epoch" => ("compact_epoch.py", &["qwreey-conventions"]),
        other => panic!("unknown hook {other}"),
    }
}

/// 한 번 돌릴 시험 폴더.
struct Sandbox {
    root: PathBuf,
}

impl Sandbox {
    fn new(tag: &str) -> Sandbox {
        let root = std::env::temp_dir().join(format!("qc-interleave-{tag}-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&root);
        for dir in ["home", "tmp", "cfg", "repo/src", "plugin/native"] {
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

    // 플러그인 폴더(python 은 hooks/ 링크로, Rust 는 native/ 의 사본으로 같은 플러그인 폴더를 본다), salt, 커밋한 저장소
    fn seed(&self) {
        let real = repo_root().join("plugins/qwreey-conventions");
        for part in ["hooks", "rules", "scripts", ".claude-plugin"] {
            std::os::unix::fs::symlink(real.join(part), self.path("plugin").join(part))
                .expect("link");
        }
        std::fs::copy(
            env!("CARGO_BIN_EXE_qwreey-conventions"),
            self.path("plugin/native/qwreey-conventions"),
        )
        .expect("binary copy");
        std::fs::write(self.path("salt"), "00".repeat(32)).expect("salt");

        std::fs::write(
            self.path("repo/src/old.py"),
            "def f():\n    # Keep the order stable.\n    x = 1\n    return x\n",
        )
        .expect("fixture");
        std::fs::write(self.path("repo/src/b.luau"), "local M = {}\nreturn M\n").expect("fixture");
        self.sh("git init -q . && git add -A && git commit -qm init");
    }

    fn env(&self) -> Vec<(String, String)> {
        let s = |rel: &str| self.path(rel).to_string_lossy().into_owned();
        vec![
            (
                "PATH".into(),
                std::env::var("PATH").unwrap_or_else(|_| "/usr/bin:/bin".to_owned()),
            ),
            ("LANG".into(), "C.UTF-8".into()),
            ("HOME".into(), s("home")),
            ("TMPDIR".into(), s("tmp")),
            ("CLAUDE_CONFIG_DIR".into(), s("cfg")),
            ("CLAUDE_PROJECT_DIR".into(), s("repo")),
            ("CLAUDE_PLUGIN_ROOT".into(), s("plugin")),
            ("QWREEY_HARNESS_SALT_FILE".into(), s("salt")),
            ("XDG_DATA_HOME".into(), s("home/.local/share")),
            ("HARNESS_ENV".into(), "/nonexistent".into()),
            ("GIT_AUTHOR_NAME".into(), "t".into()),
            ("GIT_AUTHOR_EMAIL".into(), "t@t".into()),
            ("GIT_COMMITTER_NAME".into(), "t".into()),
            ("GIT_COMMITTER_EMAIL".into(), "t@t".into()),
            ("GIT_CONFIG_GLOBAL".into(), "/dev/null".into()),
            ("GIT_CONFIG_NOSYSTEM".into(), "1".into()),
        ]
    }

    fn sh(&self, cmd: &str) {
        let status = Command::new("bash")
            .args(["-c", cmd])
            .env_clear()
            .envs(self.env())
            .current_dir(self.path("repo"))
            .stdout(Stdio::null())
            .stderr(Stdio::null())
            .status()
            .expect("bash");
        let _ = status;
    }

    fn run(&self, name: &str, side: Side, payload: &Value) -> (i32, String) {
        let mut payload = payload.clone();
        let map = payload.as_object_mut().expect("payload object");
        map.entry("cwd").or_insert(json!(self.path("repo")));
        map.entry("session_id").or_insert(json!("s1"));

        // Same plugin folder either way
        let (file, args) = script(name);
        let mut command = match side {
            Side::Python => {
                let mut c = Command::new("python3");
                c.args(["-I", "-X", "utf8"])
                    .arg(self.path("plugin/hooks").join(file))
                    .args(args);
                c
            }
            Side::Rust => {
                let mut c = Command::new(self.path("plugin/native/qwreey-conventions"));
                c.args(["hook", name]);
                c
            }
        };

        // Input in, stdout with the sandbox path replaced
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
            .write_all(payload.to_string().as_bytes())
            .expect("write input");
        let out = child.wait_with_output().expect("hook output");
        (
            out.status.code().unwrap_or(-1),
            self.normalize(&String::from_utf8_lossy(&out.stdout)),
        )
    }

    fn normalize(&self, text: &str) -> String {
        text.replace(&*self.root.to_string_lossy(), "<sandbox>")
    }

    /// 알림 중복과 rule 마커, 스냅숏 폴더의 상태: 상대 경로 -> 내용. Stop 보고용 기록(시각이 든다)과 잠금 파일은 뺀다.
    fn state_files(&self) -> BTreeMap<String, String> {
        let mut out = BTreeMap::new();
        collect(&self.path("tmp"), &self.root, &mut out);
        out.retain(|rel, _| {
            [
                "tmp/claude-conventions/",
                "tmp/claude-bypass-reminder/",
                "tmp/claude-qwreey-conventions-rules/",
            ]
            .iter()
            .any(|p| rel.starts_with(p))
                && !rel.ends_with(".lock")
                && !rel.contains("/left/")
        });
        out.into_iter()
            .map(|(rel, text)| (rel, self.normalize(&text)))
            .collect()
    }
}

impl Drop for Sandbox {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.root);
    }
}

fn collect(dir: &Path, root: &Path, out: &mut BTreeMap<String, String>) {
    let Ok(entries) = std::fs::read_dir(dir) else {
        return;
    };
    for entry in entries.flatten() {
        let path = entry.path();
        if path.is_dir() {
            collect(&path, root, out);
        } else {
            let rel = path
                .strip_prefix(root)
                .expect("under root")
                .to_string_lossy()
                .into_owned();
            out.insert(
                rel,
                std::fs::read_to_string(&path).unwrap_or_else(|_| "<binary>".into()),
            );
        }
    }
}

fn bash(event: &str, cmd: &str, tid: &str) -> Value {
    json!({"hook_event_name": event, "tool_name": "Bash", "tool_input": {"command": cmd}, "tool_use_id": tid})
}

fn file_event(tool: &str, rel: &str, extra: Value) -> Value {
    let mut v = json!({"hook_event_name": "PostToolUse", "tool_name": tool, "tool_input": {"file_path": format!("<repo>/{rel}")}});
    if let (Some(ti), Value::Object(more)) = (v["tool_input"].as_object_mut(), extra) {
        ti.extend(more);
    }
    v
}

/// 한 사건 열: 세 Bash 쓰기(heredoc 새 파일, sed -i, 쓰는 인터프리터), Read 와 Edit, compact, 스냅숏 없는 Post.
fn acts() -> Vec<Act> {
    let hook = |name, payload| Act::Hook {
        name,
        ported: name != "compact-epoch",
        payload,
    };
    let new_file = "cat > src/n.py <<'EOF'\nx = 1\n# first \u{b7} second\nEOF";
    let sed = "sed -i 's/x = 1/x = 2  # c \u{b7} d/' src/old.py";
    let script = "python3 -c \"open('src/q.luau','w').write('-- e \u{b7} f\\nreturn 1\\n')\"";
    vec![
        // A heredoc writes a new file; a Read afterwards
        hook("bash-bypass-reminder", bash("PreToolUse", new_file, "t1")),
        Act::Sh(new_file),
        hook("bash-writes", bash("PostToolUse", new_file, "t1")),
        hook("rules-inject", file_event("Read", "src/b.luau", json!({}))),
        // sed -i on a tracked file that fails, then an Edit of the same lines
        hook("bash-bypass-reminder", bash("PreToolUse", sed, "t2")),
        Act::Sh(sed),
        hook("bash-writes", bash("PostToolUseFailure", sed, "t2")),
        hook(
            "conventions-check",
            file_event(
                "Edit",
                "src/old.py",
                json!({"old_string": "x = 2", "new_string": "x = 2  # c \u{b7} d"}),
            ),
        ),
        // After compact: rules again, an interpreter write, a Post without a snapshot
        hook(
            "compact-epoch",
            json!({"hook_event_name": "PreCompact", "trigger": "auto"}),
        ),
        hook("rules-inject", file_event("Read", "src/old.py", json!({}))),
        hook("bash-bypass-reminder", bash("PreToolUse", script, "t3")),
        Act::Sh(script),
        hook("bash-writes", bash("PostToolUse", script, "t3")),
        hook("bash-writes", bash("PostToolUse", "ls", "t9")),
    ]
}

/// 옮긴 훅의 몇 번째 단계를 누가 돌리나.
type Pick = fn(usize) -> Side;

/// 한 번 돌린 결과: 훅 단계마다 (이름, 판, 종료 코드, stdout), 끝 상태.
struct Run {
    outputs: Vec<(String, Side, i32, String)>,
    state: BTreeMap<String, String>,
}

fn run_all(tag: &str, pick: impl Fn(usize) -> Side) -> Run {
    let sb = Sandbox::new(tag);
    let repo = sb.path("repo").to_string_lossy().into_owned();
    let mut outputs = Vec::new();
    let mut ported = 0;

    // Each act in order; ported hooks go to the side the mode picks
    for act in acts() {
        match act {
            Act::Sh(cmd) => sb.sh(cmd),
            Act::Hook {
                name,
                ported: is_ported,
                payload,
            } => {
                let side = if is_ported {
                    ported += 1;
                    pick(ported - 1)
                } else {
                    Side::Python
                };
                let payload: Value =
                    serde_json::from_str(&payload.to_string().replace("<repo>", &repo))
                        .expect("payload");
                let (code, out) = sb.run(name, side, &payload);
                outputs.push((name.to_owned(), side, code, out));
            }
        }
    }
    Run {
        outputs,
        state: sb.state_files(),
    }
}

/// 옮긴 훅을 번갈아 돌려도 출력과 상태가 python 만 돌린 것과 같다. 스냅숏은 한 판이 적고 다른 판이 읽는다.
#[test]
fn alternating_sides_match_python() {
    // Reference run, all python
    let python = run_all("py", |_| Side::Python);
    let notices = python
        .outputs
        .iter()
        .filter(|(_, _, _, out)| !out.is_empty())
        .count();
    assert!(
        notices >= 6,
        "the reference run should say something: {:#?}",
        python.outputs
    );
    for dir in [
        "claude-bypass-reminder/",
        "claude-qwreey-conventions-rules/",
        "claude-conventions/s1.",
    ] {
        let found = python
            .state
            .keys()
            .any(|k| k.starts_with(&format!("tmp/{dir}")));
        assert!(found, "no state under {dir}: {:#?}", python.state.keys());
    }

    // Mixed and all-Rust runs
    let modes: [(&str, Pick); 3] = [
        (
            "alt-py",
            |i| if i % 2 == 0 { Side::Python } else { Side::Rust },
        ),
        (
            "alt-rs",
            |i| if i % 2 == 0 { Side::Rust } else { Side::Python },
        ),
        ("rs", |_| Side::Rust),
    ];
    for (tag, pick) in modes {
        let got = run_all(tag, pick);
        for (want, have) in python.outputs.iter().zip(&got.outputs) {
            assert_eq!(
                (&want.0, want.2, &want.3),
                (&have.0, have.2, &have.3),
                "{tag}: {} on {:?}",
                have.0,
                have.1
            );
        }
        assert_eq!(python.state, got.state, "{tag}: state files");
    }
}
