//! 바이트 대조 시험의 공용 조각: python 정본 부르기, 임시 디렉터리, 경우 만들기.

#![allow(dead_code)] // 시험 파일마다 쓰는 조각이 달라 안 쓰는 함수가 생긴다

use std::io::Write;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};

use serde_json::{Value, json};

/// 저장소 루트(crates/harness-hook 에서 두 단계 위).
pub fn repo_root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("../..")
        .canonicalize()
        .expect("repo root")
}

/// 경우 하나: python 쪽 `op` 이름, 그 경우의 환경, 인자.
pub fn case(op: &str, env: &[(String, String)], args: Value) -> Value {
    let env: serde_json::Map<String, Value> =
        env.iter().map(|(k, v)| (k.clone(), json!(v))).collect();
    json!({"op": op, "env": env, "args": args})
}

/// (이름, 값) 목록을 소유한 문자열로.
pub fn pairs(items: &[(&str, &str)]) -> Vec<(String, String)> {
    items
        .iter()
        .map(|(k, v)| ((*k).to_owned(), (*v).to_owned()))
        .collect()
}

/// python3 이 없을 때 대조 시험을 건너뛰게 하는 환경 변수. 값이 `1` 일 때만 건너뛴다.
pub const SKIP_ENV: &str = "HARNESS_HOOK_PARITY_SKIP";

/// 경우들을 python 정본에 넣고 결과 목록을 받는다.
///
/// python3 이 없으면 실패한다. 조용히 통과하면 대조하지 않은 것을 대조한 것으로 읽게 된다.
/// [`SKIP_ENV`]`=1` 이면 알리고 `None`(시험은 건너뛴다).
pub fn python(cases: &[Value]) -> Option<Vec<Value>> {
    let driver = Path::new(env!("CARGO_MANIFEST_DIR"))
        .join("tests")
        .join("parity_driver.py");
    let spawned = Command::new("python3")
        .args(["-I", "-X", "utf8"])
        .arg(&driver)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn();
    let mut child = match spawned {
        Ok(child) => child,
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => {
            assert!(
                std::env::var_os(SKIP_ENV).is_some_and(|v| v == "1"),
                "python3 not found: parity with the python hooks cannot be checked (set {SKIP_ENV}=1 to skip)"
            );
            eprintln!(
                "skip: python3 not found and {SKIP_ENV}=1, parity with the python hooks is not checked"
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
        .expect("writing to python");
    let out = child.wait_with_output().expect("python3 output");
    assert!(
        out.status.success(),
        "python driver failed:\n{}",
        String::from_utf8_lossy(&out.stderr)
    );

    let results: Vec<Value> =
        serde_json::from_slice(&out.stdout).expect("python driver writes a JSON list");
    assert_eq!(results.len(), cases.len());
    Some(results)
}

/// 시험마다 비우는 임시 디렉터리. 끝나면 지운다.
pub struct TempDir(PathBuf);

impl TempDir {
    /// `tag` 와 프로세스 id 로 이름 지은 빈 디렉터리.
    pub fn new(tag: &str) -> TempDir {
        let path = std::env::temp_dir().join(format!("harness-hook-{tag}-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&path);
        std::fs::create_dir_all(&path).expect("temp dir");
        TempDir(path)
    }

    /// 디렉터리 경로.
    pub fn path(&self) -> &Path {
        &self.0
    }

    /// `rel` 자리에 `bytes` 를 쓰고(부모 디렉터리도 만든다) 그 경로를 돌려준다.
    pub fn write(&self, rel: &str, bytes: impl AsRef<[u8]>) -> PathBuf {
        let path = self.0.join(rel);
        std::fs::create_dir_all(path.parent().expect("parent")).expect("parent dir");
        std::fs::write(&path, bytes).expect("fixture file");
        path
    }

    /// `rel` 자리의 디렉터리를 만들고 그 경로를 돌려준다.
    pub fn dir(&self, rel: &str) -> PathBuf {
        let path = self.0.join(rel);
        std::fs::create_dir_all(&path).expect("fixture dir");
        path
    }

    /// `rel` 의 문자열 경로.
    pub fn text(&self, rel: &str) -> String {
        self.0.join(rel).to_string_lossy().into_owned()
    }
}

impl Drop for TempDir {
    fn drop(&mut self) {
        let _ = std::fs::remove_dir_all(&self.0);
    }
}
