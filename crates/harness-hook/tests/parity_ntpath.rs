//! [`harness_hook::py::ntpath`] 를 python `ntpath`(Linux 에서도 순수 python 판을 불러 쓸 수 있다)와 대조한다.
//!
//! 드라이브, UNC, 장치 경로, 두 구분자, `.` 과 `..`, ASCII 밖 글자를 이은 글 수천 개에서 함수마다 결과가 같은지 본다.

mod common;

use common::SKIP_ENV;
use harness_hook::py::ntpath;
use harness_hook::testkit::corpus;
use serde_json::{Value, json};
use std::io::Write;
use std::process::{Command, Stdio};

const PIECES: &[&str] = &[
    "C:",
    "c:",
    "\\",
    "/",
    "\\\\",
    "//",
    "a",
    "B",
    "..",
    ".",
    "\\\\?\\UNC\\",
    "\\\\?\\unc\\",
    "srv",
    "\u{e9}",
    ":",
    "UNC",
    "x y",
    "\u{130}",
];

const DRIVER: &str = r#"
import json, ntpath, sys
out = []
for a, b in json.load(sys.stdin):
    rel = None
    if ntpath.isabs(a) and ntpath.isabs(b):
        try:
            rel = ntpath.relpath(a, b)
        except ValueError:
            rel = False
    out.append([ntpath.normcase(a), ntpath.isabs(a), list(ntpath.splitroot(a)), ntpath.join(a, b),
                list(ntpath.split(a)), ntpath.normpath(a), rel])
json.dump(out, sys.stdout)
"#;

/// 함수마다 python ntpath 와 같은 글을 낸다.
#[test]
fn ntpath_matches_python() {
    let texts = corpus(PIECES, 4000);
    let pairs: Vec<(String, String)> = texts
        .iter()
        .zip(texts.iter().rev())
        .map(|(a, b)| (a.clone(), b.clone()))
        .collect();
    let Some(expected) = python(&pairs) else {
        return;
    };

    for ((a, b), want) in pairs.iter().zip(expected) {
        // relpath 는 절대 경로끼리만 본다(abspath 는 OS 몫이다)
        let rel = if ntpath::isabs(a) && ntpath::isabs(b) {
            match ntpath::relpath_abs(&ntpath::normpath(a), &ntpath::normpath(b)) {
                Some(r) => json!(r),
                None => json!(false),
            }
        } else {
            Value::Null
        };

        let (drive, root, tail) = ntpath::splitroot(a);
        let (head, last) = ntpath::split(a);
        let got = json!([
            ntpath::normcase(a),
            ntpath::isabs(a),
            [drive, root, tail],
            ntpath::join(a, b),
            [head, last],
            ntpath::normpath(a),
            rel
        ]);
        assert_eq!(got, want, "ntpath differs on {a:?}, {b:?}");
    }
}

fn python(pairs: &[(String, String)]) -> Option<Vec<Value>> {
    let spawned = Command::new("python3")
        .args(["-I", "-X", "utf8", "-c", DRIVER])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn();
    let mut child = match spawned {
        Ok(child) => child,
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
            assert!(
                std::env::var_os(SKIP_ENV).is_some_and(|v| v == "1"),
                "python3 not found (set {SKIP_ENV}=1 to skip)"
            );
            return None;
        }
        Err(e) => panic!("starting python3: {e}"),
    };

    let request = serde_json::to_string(pairs).expect("pairs as JSON");
    child
        .stdin
        .take()
        .expect("stdin")
        .write_all(request.as_bytes())
        .expect("writing to python");
    let out = child.wait_with_output().expect("python3 output");
    assert!(out.status.success(), "python driver failed");
    Some(serde_json::from_slice(&out.stdout).expect("python output as JSON"))
}
