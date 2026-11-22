//! nonce, claim, 규칙 줄, 지우기를 python 정본(lib/harness_nonce.py)과 대조한다.

mod common;

use common::{TempDir, case, pairs, python};
use harness_hook::nonce::{self, Nonce};
use harness_hook::{Env, HookInput};
use serde_json::{Value, json};

// The last two are lone surrogate placeholders; python raises UnicodeEncodeError when a salt exists
const SIDS: [&str; 8] = [
    "abc",
    "\u{c138}\u{c158}-\u{1f600}",
    "",
    "a:b",
    " ",
    "0123456789abcdef0123456789abcdef-long",
    "a\u{10fcff}b",
    "\u{10f800}",
];

fn salt_env(path: &str) -> Vec<(String, String)> {
    pairs(&[
        ("QWREEY_HARNESS_SALT_FILE", path),
        ("HOME", "/nonexistent-home"),
    ])
}

/// salt 파일 읽기, nonce 계산, salt 경로 고르기가 python 판과 같다.
#[test]
fn nonce_and_salt_files_match_python() {
    let tmp = TempDir::new("nonce");
    let good = "0123456789abcdef".repeat(4);

    // Readable salt, broken salt, a place that cannot be created
    let mut envs = vec![
        salt_env(&tmp.write("good", &good).to_string_lossy()),
        salt_env(&tmp.write("short", "abc").to_string_lossy()),
        salt_env(
            &tmp.write("newline", format!("{}\n", &good[..63]))
                .to_string_lossy(),
        ),
        salt_env(&tmp.write("upper", good.to_uppercase()).to_string_lossy()),
        salt_env(&tmp.write("long", format!("{good}0")).to_string_lossy()),
        salt_env(&tmp.write("empty", "").to_string_lossy()),
        salt_env(&tmp.write("bytes", b"\xff\xfe".repeat(32)).to_string_lossy()),
        salt_env(&tmp.dir("is-a-dir").to_string_lossy()),
        salt_env(&format!(
            "{}/under-file",
            tmp.write("plain-file", "x").to_string_lossy()
        )),
    ];

    // Salt path choice: XDG_DATA_HOME, then HOME
    tmp.write("xdg/qwreey-harness/salt", "11".repeat(32));
    tmp.write("home/.local/share/qwreey-harness/salt", "22".repeat(32));
    envs.push(pairs(&[
        ("XDG_DATA_HOME", &tmp.text("xdg")),
        ("HOME", &tmp.text("home")),
    ]));
    envs.push(pairs(&[("XDG_DATA_HOME", ""), ("HOME", &tmp.text("home"))]));

    let mut cases: Vec<Value> = envs
        .iter()
        .map(|env| case("nonce", env, json!({"sids": SIDS})))
        .collect();
    cases.push(case("attr", &envs[0], json!({"sid": "abc"})));
    cases.push(case("attr", &envs[1], json!({"sid": "abc"})));
    let Some(got) = python(&cases) else {
        return;
    };

    // Rust side in the same order
    let mut want: Vec<Value> = envs
        .iter()
        .map(|env| {
            let env = Env::from_pairs(env.clone());
            json!(
                SIDS.iter()
                    .map(|sid| match Nonce::for_session(&env, Some(sid)) {
                        Ok(n) => json!(n.map(|n| n.as_str().to_owned())),
                        Err(_) => json!("UnicodeEncodeError"),
                    })
                    .collect::<Vec<_>>()
            )
        })
        .collect();
    for env in &envs[..2] {
        let env = Env::from_pairs(env.clone());
        want.push(json!(nonce::attr(
            Nonce::for_session(&env, Some("abc")).unwrap().as_ref()
        )));
    }

    for (i, (g, w)) in got.iter().zip(&want).enumerate() {
        assert_eq!(g, w, "case {i}: {}", cases[i]);
    }
}

/// Rust 와 python 이 만든 salt 를 서로 읽어 같은 nonce 를 내고, 권한(파일 0600, 폴더 0700)도 같다.
#[test]
fn created_salt_is_shared_with_python() {
    let tmp = TempDir::new("salt-create");
    let by_rust = tmp.text("rust/a/b/salt");
    let by_python = tmp.text("python/a/b/salt");

    // Each side reads the other salt and gets the same nonce
    let rust_nonce = Nonce::for_session(&Env::from_pairs(salt_env(&by_rust)), Some("abc"))
        .unwrap()
        .expect("rust creates a salt");
    let cases = [
        case("nonce", &salt_env(&by_rust), json!({"sids": ["abc"]})),
        case("nonce", &salt_env(&by_python), json!({"sids": ["abc"]})),
    ];
    let Some(got) = python(&cases) else {
        return;
    };
    assert_eq!(got[0], json!([rust_nonce.as_str()]));
    let python_nonce =
        Nonce::for_session(&Env::from_pairs(salt_env(&by_python)), Some("abc")).unwrap();
    assert_eq!(got[1], json!([python_nonce.map(|n| n.as_str().to_owned())]));

    // Same permissions (file 0600, new directory 0700)
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let mode = |p: &str| std::fs::metadata(p).unwrap().permissions().mode() & 0o777;
        assert_eq!(mode(&by_rust), 0o600);
        assert_eq!(mode(&by_rust), mode(&by_python));
        assert_eq!(mode(&tmp.text("rust/a")), mode(&tmp.text("python/a")));
        assert_eq!(std::fs::read_to_string(&by_rust).unwrap().len(), 64);
    }
}

/// claim 폴더 경로 고르기(임시 폴더 환경 변수 순서)가 python 판과 같다.
#[test]
fn claim_paths_match_python() {
    let tmps = [
        pairs(&[("TMPDIR", "/t/dir/")]),
        pairs(&[("TMPDIR", ""), ("TEMP", "/temp"), ("TMP", "/tmp2")]),
        pairs(&[("TMP", "/only-tmp")]),
        Vec::new(),
    ];
    let calls = [
        ("abc", None, None, 1.7e9_f64),
        (
            "\u{c138}\u{c158}",
            Some("agent-1"),
            Some("compact"),
            59.99999999999999,
        ),
        ("s", Some(""), Some(""), 30.0),
        ("s", None, Some("startup"), -1.0),
    ];

    let mut cases = Vec::new();
    let mut want = Vec::new();
    for env in &tmps {
        let rust_env = Env::from_pairs(env.clone());
        for (sid, agent, source, now) in calls {
            cases.push(case(
                "claim_path",
                env,
                json!({"sid": sid, "agent": agent, "source": source, "now": now.to_bits()}),
            ));
            want.push(json!(
                nonce::claim_path(&rust_env, sid, agent, source, now).to_string_lossy()
            ));
        }
    }
    let Some(got) = python(&cases) else {
        return;
    };

    for (i, (g, w)) in got.iter().zip(&want).enumerate() {
        assert_eq!(g, w, "case {i}: {}", cases[i]);
    }
}

/// 규칙 줄을 싣고 말지의 판정이 python 판과 같다(조율하지 못하는 자리면 늘 싣는다).
#[test]
fn rule_lines_match_python() {
    let tmp = TempDir::new("rule");
    let salt = tmp
        .write("salt", "00".repeat(32))
        .to_string_lossy()
        .into_owned();
    let now = 1_700_000_000.5_f64;
    let calls = json!([
        ["SessionStart", {"session_id": "s1", "source": "startup"}],
        ["SessionStart", {"session_id": "s1", "source": "startup"}],
        ["SessionStart", {"session_id": "s1", "source": "compact"}],
        ["SubagentStart", {"session_id": "s1", "agent_id": "a1", "source": "ignored"}],
        ["SubagentStart", {"session_id": "s1", "agent_id": "a1"}],
        ["PreToolUse", {"session_id": "s2"}],
        ["SessionStart", {"session_id": ""}],
        ["SessionStart", {"source": "startup"}],
        ["SessionStart", {"session_id": "\u{c138}\u{c158}", "agent_id": ""}]
    ]);

    // Separate temp dirs keep each side from seeing the other claims; blocked means a file sits where the claim dir goes (always loads)
    let side = |name: &str| {
        pairs(&[
            ("QWREEY_HARNESS_SALT_FILE", &salt),
            ("TMPDIR", &tmp.text(name)),
        ])
    };
    tmp.write("py-blocked/claude-harness-rule", "file");
    tmp.write("rs-blocked/claude-harness-rule", "file");
    let cases = [
        case(
            "rule_for",
            &side("py"),
            json!({"calls": calls, "now": now.to_bits()}),
        ),
        case(
            "rule_for",
            &side("py-blocked"),
            json!({"calls": calls, "now": now.to_bits()}),
        ),
    ];
    let Some(got) = python(&cases) else {
        return;
    };

    // Rust side in its own temp dir with the same call order
    for (i, rs_dir) in ["rs", "rs-blocked"].iter().enumerate() {
        let env = Env::from_pairs(side(rs_dir));
        let mine: Vec<String> = calls
            .as_array()
            .unwrap()
            .iter()
            .map(|call| {
                let input = HookInput::from_slice(call[1].to_string().as_bytes()).unwrap();
                let n = Nonce::for_session(&env, input.session_id()).unwrap();
                nonce::rule_for(&env, call[0].as_str().unwrap(), &input, n.as_ref(), now)
            })
            .collect();
        assert_eq!(got[i], json!(mine), "case {i}");
    }
    let blocked: Vec<&Value> = got[1].as_array().unwrap().iter().take(5).collect();
    assert!(
        blocked
            .iter()
            .all(|line| line.as_str().is_some_and(|l| !l.is_empty())),
        "claim 디렉터리를 못 쓰면 매번 싣는다: {blocked:?}"
    );
}

// Set mtime to more than a day ago
#[cfg(unix)]
fn make_old(path: &std::path::Path) {
    let old = std::time::UNIX_EPOCH + std::time::Duration::from_secs(1);
    std::fs::File::open(path)
        .and_then(|f| f.set_modified(old))
        .expect("set mtime");
}

// Entries in the claim dir that are not claim names (sha256 hex prefix)
#[cfg(unix)]
fn non_claims(dir: &std::path::Path) -> Vec<String> {
    let mut names: Vec<String> = std::fs::read_dir(dir)
        .expect("claim dir")
        .map(|e| e.unwrap().file_name().to_string_lossy().into_owned())
        .filter(|n| !n.starts_with(|c: char| c.is_ascii_hexdigit()))
        .collect();
    names.sort();
    names
}

/// claim 폴더가 링크면 늘 싣고 링크 너머는 건드리지 않으며, 내 폴더에서는 오래된 보통 파일만 지우는 것이 python 판과 같다.
#[test]
#[cfg(unix)]
fn claim_dir_links_and_prune_match_python() {
    use std::os::unix::fs::symlink;

    let tmp = TempDir::new("claim-fs");
    let salt = tmp
        .write("salt", "00".repeat(32))
        .to_string_lossy()
        .into_owned();
    let now = nonce::now_secs();
    let calls = json!([
        ["SessionStart", {"session_id": "s1", "source": "startup"}],
        ["SessionStart", {"session_id": "s1", "source": "startup"}]
    ]);

    for side in ["py", "rs"] {
        // A link planted where the claim dir goes
        let victim = tmp.dir(&format!("{side}-victim"));
        make_old(&tmp.write(&format!("{side}-victim/old"), "keep"));
        let planted = tmp.dir(&format!("{side}-link")).join("claude-harness-rule");
        symlink(&victim, planted).expect("planted link");

        // Old file, link and directory in my claim dir
        let own = tmp.dir(&format!("{side}-own/claude-harness-rule"));
        make_old(&tmp.write(&format!("{side}-own/claude-harness-rule/old"), ""));
        let target = tmp.write(&format!("{side}-target"), "keep");
        make_old(&target);
        symlink(&target, own.join("link")).expect("link in claim dir");
        make_old(&tmp.dir(&format!("{side}-own/claude-harness-rule/sub")));
    }

    // Python side
    let side = |dir: &str| {
        pairs(&[
            ("QWREEY_HARNESS_SALT_FILE", &salt),
            ("TMPDIR", &tmp.text(dir)),
        ])
    };
    let cases = [
        case(
            "rule_for",
            &side("py-link"),
            json!({"calls": calls, "now": now.to_bits()}),
        ),
        case(
            "rule_for",
            &side("py-own"),
            json!({"calls": calls, "now": now.to_bits()}),
        ),
    ];
    let Some(got) = python(&cases) else {
        return;
    };

    // Rust side with the same calls
    for (i, dir) in ["rs-link", "rs-own"].iter().enumerate() {
        let env = Env::from_pairs(side(dir));
        let mine: Vec<String> = calls
            .as_array()
            .unwrap()
            .iter()
            .map(|call| {
                let input = HookInput::from_slice(call[1].to_string().as_bytes()).unwrap();
                let n = Nonce::for_session(&env, input.session_id()).unwrap();
                nonce::rule_for(&env, call[0].as_str().unwrap(), &input, n.as_ref(), now)
            })
            .collect();
        assert_eq!(got[i], json!(mine), "case {i}");
    }

    // A link loads both times and nothing is written or removed past it; in my dir it loads once and only old regular files go
    let rule = got[0][0].clone();
    assert_eq!(got[0], json!([rule, rule]));
    assert_eq!(got[1], json!([rule, ""]));
    for side in ["py", "rs"] {
        assert_eq!(
            non_claims(&tmp.dir(&format!("{side}-victim"))),
            ["old"],
            "{side}"
        );
        assert_eq!(
            non_claims(&tmp.dir(&format!("{side}-own/claude-harness-rule"))),
            ["link", "sub"],
            "{side}"
        );
        assert!(tmp.path().join(format!("{side}-target")).exists(), "{side}");
    }
}

/// nonce 가리기가 python 판과 같다.
#[test]
fn redaction_matches_python() {
    let tmp = TempDir::new("redact");
    let env = salt_env(&tmp.write("salt", "00".repeat(32)).to_string_lossy());
    let rule = nonce::RULE.replace("{nonce}", "39596342ed0e");
    let texts = [
        format!("before {rule} \t\r\nafter"),
        format!("{rule}{rule}\n{rule}\r"),
        format!("json {{\\\"text\\\": \\\"{}\\\"}}", rule.replace('"', "\\\"")),
        "Hook text from this session's harness carries nonce=\"x\"\n tell the user in one line.".to_owned(),
        "<a nonce=\"39596342ed0e\"> <b nonce=\\\"0f\\\"> nonce=\"ABC\" nonce=\\\"ab\" nonce=\"\" nonce=x".to_owned(),
        "bare 39596342ed0e and \u{d55c}\u{1f600} nonce=\"39596342ed0e\"\u{2028}".to_owned(),
        String::new(),
    ];

    let sids = [None, Some("abc")];
    let mut cases = Vec::new();
    let mut want = Vec::new();
    let rust_env = Env::from_pairs(env.clone());
    for text in &texts {
        for sid in sids {
            cases.push(case("redact", &env, json!({"text": text, "sid": sid})));
            want.push(json!(nonce::redact_text(
                text,
                Nonce::for_session(&rust_env, sid).unwrap().as_ref()
            )));
        }
    }
    let Some(got) = python(&cases) else {
        return;
    };

    for (i, (g, w)) in got.iter().zip(&want).enumerate() {
        assert_eq!(g, w, "case {i}: {}", cases[i]);
    }
}
