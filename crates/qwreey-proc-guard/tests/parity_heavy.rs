//! heavy-proc-guard 의 변수 펼침 검사([`expands_any`])를 python 정규식과 대조한다.
//!
//! python 판은 `re.compile(r"\$\{?(?:" + "|".join(names) + r")(?![A-Za-z0-9_])").search(text)` 로 본다. Rust 판은
//! 정규식 없이 같은 답을 내야 한다(아주 긴 이름에서 py::re 의 크기 한도를 넘지 않게). 작은 글자 모음에서 만든 경우 수천 개를 견준다.

use std::collections::HashSet;
use std::io::Write;
use std::process::{Command, Stdio};

use qwreey_proc_guard::heavy::expands_any;
use serde_json::{Value, json};

const NAMES: &[&str] = &["A", "AB", "A_1", "B2", "_x", "x", "VVVVVVVV", "a1b"];
const PIECES: &[&str] = &[
    "$", "$", "{", "}", "A", "B", "_", "1", "2", " ", "x", "a", "b", "V", "VVVV", "\u{e9}", "-",
    "/", "$A", "${AB", "$_x", "$$", ";", "\n", "\u{663}",
];

const DRIVER: &str = r#"
import json, re, sys
out = []
for names, text in json.load(sys.stdin):
    rx = re.compile(r"\$\{?(?:" + "|".join(names) + r")(?![A-Za-z0-9_])")
    out.append(bool(rx.search(text)))
json.dump(out, sys.stdout)
"#;

// Small fixed-seed random generator (LCG)
fn lcg() -> impl FnMut() -> usize {
    let mut state: u64 = 0x2545_f491_4f6c_dd1d;
    move || {
        state = state
            .wrapping_mul(6_364_136_223_846_793_005)
            .wrapping_add(1_442_695_040_888_963_407);
        (state >> 33) as usize
    }
}

fn cases(count: usize) -> Vec<(Vec<&'static str>, String)> {
    let mut next = lcg();
    (0..count)
        .map(|_| {
            let names = (0..1 + next() % 3)
                .map(|_| NAMES[next() % NAMES.len()])
                .collect();
            let text = (0..1 + next() % 8)
                .map(|_| PIECES[next() % PIECES.len()])
                .collect();
            (names, text)
        })
        .collect()
}

fn python(cases: &[(Vec<&str>, String)]) -> Option<Vec<bool>> {
    // Skip only when the env switch is set and python3 is missing
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
        Err(e) => panic!("python3: {e}"),
    };

    // Send the cases and read the answers
    let input: Vec<Value> = cases.iter().map(|(n, t)| json!([n, t])).collect();
    child
        .stdin
        .take()
        .expect("stdin")
        .write_all(json!(input).to_string().as_bytes())
        .expect("write cases");

    let out = child.wait_with_output().expect("python3 runs");
    assert!(out.status.success(), "python3 failed");
    Some(serde_json::from_slice(&out.stdout).expect("list of bools"))
}

/// 무작위 5000 경우에서 변수 펼침 판정이 python 정규식과 같다.
#[test]
fn variable_expansion_matches_python_regex() {
    let cases = cases(5000);
    let Some(want) = python(&cases) else {
        return;
    };

    let mut bad = Vec::new();
    let mut hits = 0;
    for ((names, text), want) in cases.iter().zip(want) {
        let set: HashSet<&str> = names.iter().copied().collect();
        let got = expands_any(&set, text);
        hits += usize::from(got);
        if got != want {
            bad.push(format!("{names:?} {text:?}: python {want}, rust {got}"));
        }
    }
    assert!(
        hits > 300,
        "too few matching cases to mean anything: {hits}"
    );
    assert!(
        bad.is_empty(),
        "{} differences:\n{}",
        bad.len(),
        bad[..bad.len().min(20)].join("\n")
    );
}
