//! qwreey-sessions 조각(설정 기본값, 기록 폴더 표, 날짜, 경로 풀기, 저장소 루트, 모델에게 가는 글)을 python 판과 대조한다.
//!
//! python 쪽은 `tests/parity_driver.py` 가 `plugins/qwreey-sessions/scripts/sllib` 을 그대로 불러 부른다.
//! python3 이 없으면 실패한다(`HARNESS_HOOK_PARITY_SKIP=1` 이면 건너뛴다, harness-hook 시험과 같은 약속).

use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

use harness_hook::py::json::{EnsureAscii, dumps};
use harness_hook::py::json_load::loads;
use harness_hook::py::num::parse_int;
use harness_hook::py::path::{join, pathlib_join, splitext};
use harness_hook::py::value::Value as PyValue;
use qwreey_sessions::config::{Key, USER_ONLY};
use qwreey_sessions::date::Date;
use qwreey_sessions::messages::{self, Trigger};
use qwreey_sessions::paths::{project_root, resolve};
use qwreey_sessions::pyval::Num;
use qwreey_sessions::records_home::{is_snapshot, is_under};
use serde_json::{Value, json};

fn repo_root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .canonicalize()
        .expect("repo root")
}

/// 경우들을 python 에 넣고 결과 목록을 받는다.
fn python(cases: &[Value]) -> Option<Vec<Value>> {
    let driver = Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/parity_driver.py");
    let spawned = Command::new("python3")
        .args(["-I", "-X", "utf8"])
        .arg(driver)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn();
    let mut child = match spawned {
        Ok(child) => child,
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
            assert!(
                std::env::var_os("HARNESS_HOOK_PARITY_SKIP").is_some_and(|v| v == "1"),
                "python3 not found: parity cannot be checked (set HARNESS_HOOK_PARITY_SKIP=1 to skip)"
            );
            return None;
        }
        Err(e) => panic!("starting python3: {e}"),
    };

    let request = json!({"repo": repo_root(), "cases": cases});
    child
        .stdin
        .take()
        .expect("stdin")
        .write_all(request.to_string().as_bytes())
        .expect("request");
    let out = child.wait_with_output().expect("python output");
    assert!(
        out.status.success(),
        "driver failed:\n{}",
        String::from_utf8_lossy(&out.stderr)
    );
    let results: Vec<Value> = serde_json::from_slice(&out.stdout).expect("JSON list");
    assert_eq!(results.len(), cases.len());
    Some(results)
}

fn case(op: &str, args: Value) -> Value {
    json!({"op": op, "args": args})
}

/// 시험마다 비우는 폴더.
struct Fixture(PathBuf);

impl Fixture {
    fn new(tag: &str) -> Fixture {
        let path = std::env::temp_dir().join(format!("qs-parity-{tag}-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&path);
        std::fs::create_dir_all(&path).expect("fixture");
        Fixture(path.canonicalize().expect("fixture path"))
    }

    fn p(&self, rel: &str) -> String {
        self.0.join(rel).to_string_lossy().into_owned()
    }
}

impl Drop for Fixture {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}

#[test]
fn tables_and_text_helpers_match_python() {
    let dates = [
        "2026-11-10",
        "20261110",
        "20261110T1",
        "2026-W01-1",
        "2026W011",
        "2026-W01",
        "2026W01",
        "2026-W53-1",
        "2025-W53-1",
        "2020-W53-7",
        "9999-W52-7",
        "9999-12-31",
        "0001-01-01",
        "0001-W01-1",
        "2024-02-29",
        "2023-02-29",
        "2026-13-01",
        "2026-00-10",
        "2026-11-1",
        "2026-1-10",
        "2026-11-10T",
        "2026-11-10 ",
        "2026/11/10",
        "+026-11-10",
        "2026-W00-1",
        "2026-W01-0",
        "2026-W01-8",
        "2026-W1-1",
        "2026W01-1",
        "2026-W011",
        "20261-10",
        "abcd-ef-gh",
        "",
        "2026",
        "2026-11",
        "2026-110",
        "\u{663}026-11-10",
    ];
    let paths = [
        "/a/b.c", "/a/.b", "/a/..b", "/a.b/c", "x.tar.gz", "/a/b.", "/a/...", "/a/b.PNG", "",
    ];
    let joins = [
        ("/a", "b"),
        ("/a/", "b"),
        ("", "b"),
        ("/a", "/b"),
        ("a", ""),
        ("//", "k"),
        (".", "k"),
        ("/a", "b//c/./d"),
    ];
    let ints = [
        " 12 ", "-3", "+0", "1_000", "1__0", "_1", "1_", "", " ", "0x10", "1.0", "\u{663}", "007",
    ];
    let snapshots = json!([
        ["/r/.claude/audit/1/a.md", []],
        ["/r/.claude/audit", []],
        ["/r/.claude/scopes/a/b/handoff/x.md", []],
        ["/r/.claude/packs/k/plan/x.md", []],
        ["/h/.claude/sessions/s.md", ["/h/.claude/"]],
        ["/h/.claude/sessions/s.md", ["/h/.claude"]],
        ["/w/.claude/worktrees/w/.claude/session/a.md", []],
        ["/r/.claude//audit/./1/a.md", []],
    ]);
    let unders = [
        ("/a/b", "/a"),
        ("/a", "/a/"),
        ("/ab", "/a"),
        ("/x", "/"),
        ("//x", "/"),
        ("/a/../b", "/b"),
    ];
    let dump = json!({"notice_seq": 3, "reminded": ["a@0", "\u{d55c}"], "last_spawn": 1763600000.1234567, "e": {}, "l": []});

    let cases = vec![
        case("defaults", Value::Null),
        case("kinds", Value::Null),
        case("fromisoformat", json!(dates.to_vec())),
        case("splitext", json!(paths)),
        case("join", json!(joins)),
        case("pathlib_join", json!(joins)),
        case("int", json!(ints)),
        case("snapshot", snapshots.clone()),
        case("under", json!(unders)),
        case("dumps_indent", dump.clone()),
    ];
    let Some(py) = python(&cases) else { return };

    // 설정 기본값과 사용자 전용 키
    for key in Key::ALL {
        assert_eq!(
            py[0]["defaults"][key.name()],
            json!(key.default_value()),
            "{key:?}"
        );
    }
    let mut user_only: Vec<&str> = USER_ONLY.to_vec();
    user_only.sort_unstable();
    assert_eq!(py[0]["user_only"], json!(user_only));

    // 기록 폴더 표: 판정 결과로 대조한다(Rust 표는 비공개)
    let kinds = py[1]["kinds"].as_object().expect("kinds");
    for (name, kind) in kinds {
        let path = format!("/r/.claude/{name}/x/a.md");
        assert_eq!(is_snapshot(&path, &[]), kind == "snapshot", "{name}");
    }

    // 날짜, 경로 조각, 정수
    let got: Vec<Value> = dates
        .iter()
        .map(|d| {
            json!(Date::fromisoformat(d).map(|x| x.days_since(Date::new(1, 1, 1).unwrap()) + 1))
        })
        .collect();
    assert_eq!(py[2], json!(got));
    let got: Vec<&str> = paths.iter().map(|p| splitext(p).1).collect();
    assert_eq!(py[3], json!(got));
    let got: Vec<String> = joins.iter().map(|(a, b)| join(a, b)).collect();
    assert_eq!(py[4], json!(got));
    let got: Vec<String> = joins.iter().map(|(a, b)| pathlib_join(a, b)).collect();
    assert_eq!(py[5], json!(got));
    let got: Vec<Option<String>> = ints
        .iter()
        .map(|s| parse_int(s).map(|i| i.to_string()))
        .collect();
    assert_eq!(py[6], json!(got));

    // 기록 경로 판정, 훅 상태 꼴
    let got: Vec<bool> = snapshots
        .as_array()
        .expect("list")
        .iter()
        .map(|c| {
            let skips: Vec<String> = c[1]
                .as_array()
                .expect("skips")
                .iter()
                .map(|s| s.as_str().expect("str").to_owned())
                .collect();
            is_snapshot(c[0].as_str().expect("path"), &skips)
        })
        .collect();
    assert_eq!(py[7], json!(got));
    let got: Vec<bool> = unders.iter().map(|(p, d)| is_under(p, d)).collect();
    assert_eq!(py[8], json!(got));
    let value: PyValue = loads(&dump.to_string()).expect("py value");
    assert_eq!(py[9], json!(dumps(&value, EnsureAscii::No, Some(1))));
}

#[test]
fn resolve_and_project_root_match_python() {
    let fx = Fixture::new("root");
    let mk = |rel: &str| std::fs::create_dir_all(fx.0.join(rel)).expect("dir");
    let link = |target: &str, rel: &str| {
        std::os::unix::fs::symlink(target, fx.0.join(rel)).expect("symlink")
    };

    // 본 저장소, worktree(상대, 절대 gitdir), 서브모듈 꼴, 링크, 고리
    mk("main/.git/worktrees/wt");
    mk("main/sub/deep");
    std::fs::write(fx.0.join("main/.git/worktrees/wt/commondir"), "../..\n").expect("commondir");
    mk("wt/x");
    std::fs::write(
        fx.0.join("wt/.git"),
        format!("gitdir: {}\n", fx.p("main/.git/worktrees/wt")),
    )
    .expect(".git file");
    mk("wt2");
    std::fs::write(
        fx.0.join("wt2/.git"),
        "gitdir: ../main/.git/worktrees/wt\r\n",
    )
    .expect(".git file");
    mk("modlike");
    std::fs::write(
        fx.0.join("modlike/.git"),
        "gitdir: ../main/.git/modules/m\n",
    )
    .expect(".git file");
    mk("absc/.git/worktrees/w");
    std::fs::write(
        fx.0.join("absc/.git/worktrees/w/commondir"),
        format!("{}//\n", fx.p("main/.git")),
    )
    .expect("commondir");
    mk("wt3");
    std::fs::write(
        fx.0.join("wt3/.git"),
        format!("gitdir:{}", fx.p("absc/.git/worktrees/w")),
    )
    .expect(".git file");
    link("main/sub", "lsub");
    link(&fx.p("main"), "labs");
    link("loop2", "loop1");
    link("loop1", "loop2");
    link("missing/target", "dangling");
    mk("plain/a");

    let starts: Vec<String> = [
        "main",
        "main/sub/deep",
        "wt/x",
        "wt2",
        "modlike",
        "wt3",
        "lsub/deep",
        "labs/sub/../sub",
        "loop1/x",
        "dangling/y",
        "plain/a",
        "plain/a/../../main/./sub",
        "nope/x/..",
        "lsub/..",
    ]
    .iter()
    .map(|r| fx.p(r))
    .chain(["/", "//", "/../x", "relative/x"].map(str::to_owned))
    .collect();
    let cases = vec![
        case("resolve", json!(starts)),
        case("project_root", json!(starts)),
    ];
    let Some(py) = python(&cases) else { return };

    let resolved: Vec<String> = starts
        .iter()
        .map(|s| resolve(s).expect("resolve"))
        .collect();
    assert_eq!(py[0], json!(resolved));
    let roots: Vec<String> = starts
        .iter()
        .map(|s| project_root(s).expect("root"))
        .collect();
    assert_eq!(py[1], json!(roots));
}

#[test]
fn model_facing_text_matches_python() {
    let pending = json!([
        [1, "2026-11-10", 0, "commit", false, "docs/sessions/"],
        [2, "2026-01-02", 1, "handover", true, null],
        [5, "", -3, "session_start", false, null],
        [3, "x", 7, "precompact", false, "a/"],
    ]);
    let propose = json!([
        [3, "2026-11-01", 19, []],
        [1, "d", 1, ["handoff/", ".claude/audit/"]]
    ]);
    let gate = json!([
        [40, 32, "/r/.claude/audit/a.md", true],
        [1, 0, "/s/rec.md", false]
    ]);
    let started = json!([["periodic", 42, null], ["periodic", 1.5, 7]]);
    let saved = json!([
        [3, ["~/a.md"], 0, 0],
        [1, ["/a.md", "/b.md", "/c.md"], 2, 1],
        [1.0, ["x"], 1, 0.0],
        [2.5, ["x", "y"], 0, 1.0],
        [2, [], 3, 1],
        [1, ["x"], 0, 2],
    ]);
    let cases = vec![case(
        "messages",
        json!({"pending": pending, "propose": propose, "gate": gate, "started": started, "saved": saved}),
    )];
    let Some(py) = python(&cases) else { return };
    let py = &py[0];

    let trigger = |t: &str| match t {
        "commit" => Trigger::Commit,
        "handover" => Trigger::Handover,
        "precompact" => Trigger::PreCompact,
        _ => Trigger::SessionStart,
    };
    let num = |v: &Value| match v.as_i64() {
        Some(i) => Num::Int(i128::from(i)),
        None => Num::Float(v.as_f64().expect("number")),
    };
    let strs = |v: &Value| -> Vec<String> {
        v.as_array()
            .expect("list")
            .iter()
            .map(|s| s.as_str().expect("str").to_owned())
            .collect()
    };

    for (i, a) in pending.as_array().expect("list").iter().enumerate() {
        let got = messages::pending(
            a[0].as_u64().expect("count") as usize,
            a[1].as_str().expect("date"),
            a[2].as_i64().expect("days"),
            trigger(a[3].as_str().expect("trigger")),
            a[5].as_str(),
        );
        assert_eq!(py["pending"][i], json!(got), "pending {i}");
    }
    for (i, a) in propose.as_array().expect("list").iter().enumerate() {
        let got = messages::pending_propose(
            a[0].as_u64().expect("count") as usize,
            a[1].as_str().expect("date"),
            a[2].as_i64().expect("days"),
            &strs(&a[3]),
        );
        assert_eq!(py["propose"][i], json!(got), "propose {i}");
    }
    for (i, a) in gate.as_array().expect("list").iter().enumerate() {
        let got = messages::record_read_gate(
            a[0].as_u64().expect("kb"),
            &a[1].to_string(),
            a[2].as_str().expect("path"),
            a[3].as_bool().expect("bool"),
        );
        assert_eq!(py["gate"][i], json!(got), "gate {i}");
    }
    for (i, a) in started.as_array().expect("list").iter().enumerate() {
        let to = (!a[2].is_null()).then(|| num(&a[2]).text());
        let got = messages::started(
            a[0].as_str().expect("trigger"),
            &num(&a[1]).text(),
            to.as_deref(),
        );
        assert_eq!(py["started"][i], json!(got), "started {i}");
    }
    for (i, a) in saved.as_array().expect("list").iter().enumerate() {
        let got = messages::saved(
            num(&a[0]),
            &strs(&a[1]),
            a[2].as_u64().expect("pending") as usize,
            num(&a[3]),
        );
        assert_eq!(py["saved"][i], json!(got), "saved {i}");
    }
    assert_eq!(py["record_read"], json!(messages::RECORD_READ));
}
