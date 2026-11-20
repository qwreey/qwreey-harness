//! nonce, claim, 규칙 줄, 지우기를 python 정본(lib/harness_nonce.py)과 대조한다.

mod common;

use common::{TempDir, case, pairs, python};
use harness_hook::nonce::{self, Nonce};
use harness_hook::{Env, HookInput};
use serde_json::{Value, json};

const SIDS: [&str; 6] = [
    "abc",
    "\u{c138}\u{c158}-\u{1f600}",
    "",
    "a:b",
    " ",
    "0123456789abcdef0123456789abcdef-long",
];

fn salt_env(path: &str) -> Vec<(String, String)> {
    pairs(&[
        ("QWREEY_HARNESS_SALT_FILE", path),
        ("HOME", "/nonexistent-home"),
    ])
}

#[test]
fn nonce_and_salt_files_match_python() {
    let tmp = TempDir::new("nonce");
    let good = "0123456789abcdef".repeat(4);

    // 읽히는 salt, 망가진 salt, 만들 수 없는 자리
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

    // salt 경로 고르기: XDG_DATA_HOME, 그다음 HOME
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

    // Rust 쪽 같은 순서로
    let mut want: Vec<Value> = envs
        .iter()
        .map(|env| {
            let env = Env::from_pairs(env.clone());
            json!(
                SIDS.iter()
                    .map(|sid| Nonce::for_session(&env, Some(sid)).map(|n| n.as_str().to_owned()))
                    .collect::<Vec<_>>()
            )
        })
        .collect();
    for env in &envs[..2] {
        let env = Env::from_pairs(env.clone());
        want.push(json!(nonce::attr(
            Nonce::for_session(&env, Some("abc")).as_ref()
        )));
    }

    for (i, (g, w)) in got.iter().zip(&want).enumerate() {
        assert_eq!(g, w, "case {i}: {}", cases[i]);
    }
}

#[test]
fn created_salt_is_shared_with_python() {
    let tmp = TempDir::new("salt-create");
    let by_rust = tmp.text("rust/a/b/salt");
    let by_python = tmp.text("python/a/b/salt");

    // 서로 만든 salt 를 읽어 같은 nonce 를 내는지
    let rust_nonce = Nonce::for_session(&Env::from_pairs(salt_env(&by_rust)), Some("abc"))
        .expect("rust creates a salt");
    let cases = [
        case("nonce", &salt_env(&by_rust), json!({"sids": ["abc"]})),
        case("nonce", &salt_env(&by_python), json!({"sids": ["abc"]})),
    ];
    let Some(got) = python(&cases) else {
        return;
    };
    assert_eq!(got[0], json!([rust_nonce.as_str()]));
    let python_nonce = Nonce::for_session(&Env::from_pairs(salt_env(&by_python)), Some("abc"));
    assert_eq!(got[1], json!([python_nonce.map(|n| n.as_str().to_owned())]));

    // 같은 권한(파일 0600, 새 디렉터리 0700)
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

    // 양쪽이 서로의 claim 을 보지 않게 임시 폴더를 나눈다. blocked 는 claim 디렉터리 자리에 파일이 있는 경우
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

    // Rust 쪽은 자기 임시 폴더에서 같은 호출 순서로
    for (i, rs_dir) in ["rs", "rs-blocked"].iter().enumerate() {
        let env = Env::from_pairs(side(rs_dir));
        let mine: Vec<String> = calls
            .as_array()
            .unwrap()
            .iter()
            .map(|call| {
                let input = HookInput::from_slice(call[1].to_string().as_bytes()).unwrap();
                let n = Nonce::for_session(&env, input.session_id());
                nonce::rule_for(&env, call[0].as_str().unwrap(), &input, n.as_ref(), now)
            })
            .collect();
        assert_eq!(got[i], json!(mine), "case {i}");
    }
}

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
                Nonce::for_session(&rust_env, sid).as_ref()
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
