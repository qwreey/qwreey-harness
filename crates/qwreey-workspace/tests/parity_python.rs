//! Bash 분류기와 형제 경로 찾기를 python 원본 함수(`wslib.classify_bash`, `sibling_notice.find_hits`)와 대조한다.
//!
//! 가짜 작업 폴더(이 저장소, 형제 저장소 둘, 홈 아래 저장소 하나, 홈의 symlink)를 만들고, 그 경로와 명령 조각을 이은
//! 글 수천 개를 양쪽에 넣어 결과(갈래와 저장소, 또는 python 이 예외로 끝나는가)가 같은지 본다.
#![cfg(unix)]

use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

use harness_hook::Env;
use harness_hook::testkit::corpus;
use qwreey_workspace::context::Context;
use qwreey_workspace::gate::bash::{Kind, classify};
use qwreey_workspace::scope::Scope;
use qwreey_workspace::sibling::hits::{Sibling, find_hits};
use serde_json::{Value, json};

const DRIVER: &str = r#"
import json, os, sys
req = json.load(sys.stdin)
os.environ.update(req["env"])
sys.path.insert(0, req["scripts"])
import wslib, sibling_notice as sn
out = {"classify": [], "hits": []}
for cmd in req["commands"]:
    try:
        out["classify"].append(list(wslib.classify_bash(cmd, req["repo"], wslib.Scope(req["repo"], load=lambda: {}))))
    except Exception:
        out["classify"].append("error")
sibs = dict(req["sibs"])
for text in req["texts"]:
    try:
        out["hits"].append(sn.find_hits(text, sibs, req["local_dirs"]))
    except Exception:
        out["hits"].append("error")
json.dump(out, sys.stdout)
"#;

/// 시험용 작업 폴더.
struct Layout {
    base: PathBuf,
}

impl Layout {
    fn new() -> Layout {
        let base = std::env::temp_dir().join(format!("qw-parity-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&base);
        for dir in [
            "ws/mine/.git",
            "ws/other/.git",
            "ws/x-kb/.git",
            "ws/test/.git",
            "home/proj/.git",
            "tmp",
            "cfg",
        ] {
            std::fs::create_dir_all(base.join(dir)).unwrap();
        }

        // Files the bare-name form checks for
        for (file, text) in [
            ("ws/other/src/engine.py", "x\n"),
            ("ws/x-kb/skills/a.md", "a\n"),
            ("ws/test/README.md", "t\n"),
            ("home/proj/lib/a.py", "a\n"),
        ] {
            let path = base.join(file);
            std::fs::create_dir_all(path.parent().unwrap()).unwrap();
            std::fs::write(path, text).unwrap();
        }
        std::fs::create_dir_all(base.join("ws/mine/test")).unwrap();
        std::fs::write(base.join("ws/mine/test/README.md"), "ours\n").unwrap();
        std::fs::create_dir_all(base.join("home/.claude/rules")).unwrap();
        std::os::unix::fs::symlink(
            base.join("ws/other/src/engine.py"),
            base.join("home/.claude/rules/e.py"),
        )
        .unwrap();
        Layout { base }
    }

    fn path(&self, rel: &str) -> String {
        self.base.join(rel).to_str().unwrap().to_owned()
    }

    fn env_pairs(&self) -> Vec<(String, String)> {
        vec![
            ("HOME".into(), self.path("home")),
            ("TMPDIR".into(), self.path("tmp")),
            ("CLAUDE_CONFIG_DIR".into(), self.path("cfg")),
            ("HARNESS_ENV".into(), "/nonexistent".into()),
        ]
    }
}

impl Drop for Layout {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.base);
    }
}

/// 명령 분류와 경로 찾기가 python 과 같다.
#[test]
fn classify_and_hits_match_python() {
    let layout = Layout::new();
    let (ws, repo, home) = (
        layout.path("ws"),
        layout.path("ws/mine"),
        layout.path("home"),
    );

    // Commands from shell pieces and the layout's paths
    let cmd_pieces: Vec<String> = [
        "rm ",
        "cp ",
        "cat ",
        "echo x",
        " > ",
        ">>",
        " 2>",
        "&>",
        ">&2",
        "cd ",
        "pushd ",
        " && ",
        "; ",
        " | ",
        " ",
        "-f ",
        "git ",
        "-C ",
        "commit ",
        "log ",
        "stash ",
        "sed -i ",
        "perl -pi -e ",
        "python3 -c \"open('a','w')\" ",
        "tee ",
        "'",
        "\"",
        "sudo ",
        "FOO=1 ",
        "5s ",
        "touch ",
        "~/proj/c",
        "$HOME/proj/d",
        "${HOME}/proj",
        "$HOMEX",
        "./x",
        "..",
        "/",
        "x-kb/z",
        "../other/b",
        "\u{663}>",
        "\n",
        "\u{e9}",
    ]
    .iter()
    .map(|s| (*s).to_owned())
    .chain([
        format!("{ws}/other/a"),
        format!("{ws}/x-kb/b "),
        format!("{repo}/y"),
        format!("{home}/.claude/rules/e.py "),
    ])
    .collect();
    let pieces: Vec<&str> = cmd_pieces.iter().map(String::as_str).collect();
    let commands = corpus(&pieces, 3000);

    // Texts from path pieces, written into a record
    let text_pieces: Vec<String> = [
        "../",
        "..\\",
        "other",
        "x-kb",
        "test",
        "proj",
        "/",
        "\\",
        "src",
        "engine.py",
        "~",
        "lib/a.py",
        ".",
        ",",
        " ",
        "`",
        ":12",
        "a",
        "-",
        "$",
        "\u{e9}",
        "Other",
        "skills/a.md",
        "README.md",
        "\n",
        "x",
        // Pieces that join into a real path
        " ../other/src/engine.py",
        " other/src/engine.py",
        " test/README.md",
        " x-kb/skills/a.md",
        " ~/proj/lib/a.py",
        " ..\\x-kb\\",
    ]
    .iter()
    .map(|s| (*s).to_owned())
    .chain([
        ws.clone(),
        format!("{home}/proj"),
        format!("{ws}\\other"),
        format!(" {ws}/other/"),
    ])
    .collect();
    let pieces: Vec<&str> = text_pieces.iter().map(String::as_str).collect();
    let texts = corpus(&pieces, 4000);

    let sibs = vec![
        Sibling {
            name: "other".into(),
            root: layout.path("ws/other"),
        },
        Sibling {
            name: "proj".into(),
            root: layout.path("home/proj"),
        },
        Sibling {
            name: "test".into(),
            root: layout.path("ws/test"),
        },
        Sibling {
            name: "x-kb".into(),
            root: layout.path("ws/x-kb"),
        },
    ];
    let local_dirs = vec![
        repo.clone(),
        format!("{repo}/.claude"),
        format!("{repo}/.claude/research"),
    ];

    // Rust side
    let ctx = Context::new(Env::from_pairs(layout.env_pairs()), None);
    let rust_classify: Vec<Value> = commands
        .iter()
        .map(|cmd| {
            let scope = Scope::new(&ctx, &repo, None).unwrap();
            match classify(&ctx, cmd, Some(&repo), &scope) {
                Ok(Some((kind, x))) => {
                    json!([if kind == Kind::Write { "write" } else { "read" }, x])
                }
                Ok(None) => json!([null, null]),
                Err(_) => json!("error"),
            }
        })
        .collect();
    let rust_hits: Vec<Value> = texts
        .iter()
        .map(|text| match find_hits(&ctx, text, &sibs, &local_dirs) {
            Ok(hits) => json!(hits),
            Err(_) => json!("error"),
        })
        .collect();

    // Python side
    let request = json!({
        "env": layout.env_pairs().into_iter().map(|(k, v)| (k, json!(v))).collect::<serde_json::Map<String, Value>>(),
        "scripts": scripts_dir(),
        "repo": repo,
        "commands": commands,
        "texts": texts,
        "sibs": sibs.iter().map(|s| json!([s.name, s.root])).collect::<Vec<_>>(),
        "local_dirs": local_dirs,
    });
    let Some(want) = python(&request) else {
        return;
    };

    for (i, cmd) in commands.iter().enumerate() {
        assert_eq!(
            rust_classify[i], want["classify"][i],
            "classify differs on {cmd:?}"
        );
    }
    for (i, text) in texts.iter().enumerate() {
        assert_eq!(
            rust_hits[i], want["hits"][i],
            "find_hits differs on {text:?}"
        );
    }

    // Check every kind is reached enough, so the comparison is not only empty answers
    let kinds = |k: Value| rust_classify.iter().filter(|v| v[0] == k).count();
    let found = rust_hits
        .iter()
        .filter(|h| h.as_object().is_some_and(|o| !o.is_empty()))
        .count();
    eprintln!(
        "write {}, read {}, none {}, texts with hits {found}",
        kinds(json!("write")),
        kinds(json!("read")),
        kinds(Value::Null)
    );
    assert!(kinds(json!("write")) > 300 && kinds(json!("read")) > 100 && kinds(Value::Null) > 100);
    assert!(found > 300);
}

fn scripts_dir() -> String {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../../plugins/qwreey-workspace/scripts")
        .canonicalize()
        .unwrap()
        .to_str()
        .unwrap()
        .to_owned()
}

// Skip only when the env switch is set and python3 is missing
fn python(request: &Value) -> Option<Value> {
    let spawned = Command::new("python3")
        .args(["-I", "-X", "utf8", "-c", DRIVER])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn();
    let mut child = match spawned {
        Ok(child) => child,
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
            assert!(
                std::env::var_os("HARNESS_HOOK_PARITY_SKIP").is_some_and(|v| v == "1"),
                "python3 not found (set HARNESS_HOOK_PARITY_SKIP=1 to skip)"
            );
            return None;
        }
        Err(e) => panic!("starting python3: {e}"),
    };

    child
        .stdin
        .take()
        .expect("stdin")
        .write_all(request.to_string().as_bytes())
        .expect("writing to python");
    let out = child.wait_with_output().expect("python3 output");
    assert!(out.status.success(), "python driver failed");
    Some(serde_json::from_slice(&out.stdout).expect("python output as JSON"))
}
