//! 명령 전후로 묻는 git(python `bash_writes._git`, `repo`, `porcelain`, `blobs`, `in_git`).
//!
//! 모두 `git --no-optional-locks -C <root> ...` 이고 3 초 한도다. 실패는 python 처럼 "모름"(`None`)이다.

use std::collections::{BTreeMap, HashMap};
use std::ffi::OsString;
use std::time::Duration;

use harness_hook::py::num::parse_int;
use harness_hook::py::surrogate::{decode_os, encode_os};
use harness_hook::py::text::{split_whitespace, splitlines, strip};

use crate::git::{os_arg, output};
use crate::halt::{Halt, Result};

/// git 한 번의 한도(python `GIT_TIMEOUT_S`).
const GIT_TIMEOUT: Duration = Duration::from_secs(3);

/// python `_git(root, *args, stdin=None)`: 0 으로 끝나면 stdout.
pub fn git(root: &str, args: &[&str], stdin: Option<Vec<u8>>) -> Result<Option<Vec<u8>>> {
    let mut argv: Vec<OsString> = vec!["--no-optional-locks".into(), "-C".into(), os_arg(root)?];
    for a in args {
        argv.push(os_arg(a)?);
    }
    Ok(output(&argv, stdin, GIT_TIMEOUT))
}

// python bytes.decode(): UTF-8 이 아니면 UnicodeDecodeError(잡지 않는다)
fn decode_strict(bytes: Vec<u8>) -> Result<String> {
    String::from_utf8(bytes).map_err(|_| Halt::PyError("git printed bytes that are not UTF-8"))
}

/// python `git rev-parse -q --verify HEAD` 의 sha(없으면 `None`).
pub fn head(root: &str) -> Result<Option<String>> {
    match git(root, &["rev-parse", "-q", "--verify", "HEAD"], None)? {
        Some(out) if !out.is_empty() => Ok(Some(strip(&decode_strict(out)?).to_owned())),
        _ => Ok(None),
    }
}

/// python `repo(cwd)`: (git 최상위, HEAD). git 저장소가 아니면 `None`.
pub fn repo(cwd: &str) -> Result<Option<(String, Option<String>)>> {
    let Some(top) = git(cwd, &["rev-parse", "--show-toplevel"], None)? else {
        return Ok(None);
    };
    let top = decode_strict(top)?;
    if top.is_empty() {
        return Ok(None);
    }
    Ok(Some((strip(&top).to_owned(), head(cwd)?)))
}

/// porcelain 항목들(python `{경로: XY}`, 나온 순서).
pub type Porcelain = Vec<(String, String)>;

/// python `porcelain(root)`: `git status --porcelain=v1 -z` 의 (경로, XY), 추적 안 하는 파일 모두, 서브모듈 빼고.
///
/// 줄바꿈이 든 경로는 뺀다(`cat-file --batch` 의 줄 맞춤이 깨진다). 실패하면 `None`.
pub fn porcelain(root: &str) -> Result<Option<Porcelain>> {
    let args = [
        "status",
        "--porcelain=v1",
        "-z",
        "--untracked-files=all",
        "--ignore-submodules",
    ];
    let Some(out) = git(root, &args, None)? else {
        return Ok(None);
    };
    let text = decode_os(&out);
    let items: Vec<&str> = text.split('\0').collect();

    // A rename or copy carries its old path as one more item
    let mut res: Porcelain = Vec::new();
    let mut seen: HashMap<String, usize> = HashMap::new();
    let mut i = 0;
    while i < items.len() {
        let e = items[i];
        i += 1;
        let chars: Vec<char> = e.chars().collect();
        if chars.len() < 4 {
            continue;
        }
        if matches!(chars[0], 'R' | 'C') {
            i += 1;
        }
        if !e.contains('\n') {
            let rel: String = chars[3..].iter().collect();
            let xy: String = chars[..2].iter().collect();
            match seen.get(&rel) {
                Some(&at) => res[at].1 = xy,
                None => {
                    seen.insert(rel.clone(), res.len());
                    res.push((rel, xy));
                }
            }
        }
    }
    Ok(Some(res))
}

/// python `blobs(root, rev, rels)`: 경로마다 `rev` 에서의 글(없으면 `None`). git 이 실패하면 `Ok(None)`.
///
/// 줄바꿈이 든 경로는 묻지 않는다. 글은 UTF-8 이 아닌 바이트를 U+FFFD 로 바꾼다(python `decode("utf-8", "replace")`).
pub fn blobs(
    root: &str,
    rev: Option<&str>,
    rels: &[String],
) -> Result<Option<BTreeMap<String, Option<String>>>> {
    let mut out: BTreeMap<String, Option<String>> =
        rels.iter().map(|r| (r.clone(), None)).collect();
    let ask: Vec<&String> = rels.iter().filter(|r| !r.contains('\n')).collect();
    let Some(rev) = rev.filter(|r| !r.is_empty()) else {
        return Ok(Some(out));
    };
    if ask.is_empty() {
        return Ok(Some(out));
    }

    // One request line per path
    let request: String = ask.iter().map(|r| format!("{rev}:{r}\n")).collect();
    let stdin = encode_os(&request).ok_or(Halt::PyError("a path python cannot encode"))?;
    let Some(raw) = git(root, &["cat-file", "--batch"], Some(stdin))? else {
        return Ok(None);
    };

    // Headers "<sha> blob <size>" then the content; other headers have no content read
    let mut pos = 0;
    for r in ask {
        let Some(nl) = raw[pos..].iter().position(|&b| b == b'\n').map(|k| pos + k) else {
            break;
        };
        let hdr: Vec<&[u8]> = raw[pos..nl]
            .split(|&b| is_py_space(b))
            .filter(|f| !f.is_empty())
            .collect();
        pos = nl + 1;
        if hdr.len() == 3 && hdr[1] == b"blob" {
            let size = std::str::from_utf8(hdr[2])
                .ok()
                .and_then(parse_int)
                .and_then(|n| usize::try_from(n).ok())
                .ok_or(Halt::PyError("int() of a git size"))?;
            let end = (pos + size).min(raw.len());
            out.insert(
                r.clone(),
                Some(String::from_utf8_lossy(&raw[pos.min(end)..end]).into_owned()),
            );
            pos += size + 1;
        }
        if pos > raw.len() {
            pos = raw.len();
        }
    }
    Ok(Some(out))
}

// python bytes.split() 의 공백(ASCII 공백, 탭, 줄바꿈, \r, \x0b, \x0c)
fn is_py_space(b: u8) -> bool {
    matches!(b, b' ' | b'\t' | b'\n' | b'\r' | 0x0b | 0x0c)
}

/// python `in_git(root, paths)`: 지금 내용이 이미 git 객체로 있는 경로들(git 이 되돌리거나 꺼낸 파일). 객체를 쓰지 않는다.
pub fn in_git(root: &str, paths: &[String]) -> Result<Vec<String>> {
    let ps: Vec<&String> = paths.iter().filter(|p| !p.contains('\n')).collect();
    if ps.is_empty() {
        return Ok(Vec::new());
    }

    // Hash each file as git would
    let joined: Vec<&str> = ps.iter().map(|p| p.as_str()).collect();
    let stdin = encode_os(&format!("{}\n", joined.join("\n")))
        .ok_or(Halt::PyError("a path python cannot encode"))?;
    let hashes = match git(root, &["hash-object", "--stdin-paths"], Some(stdin))? {
        Some(out) if !out.is_empty() => decode_strict(out)?,
        _ => String::new(),
    };
    let hashes: Vec<&str> = split_whitespace(&hashes).collect();
    if hashes.len() != ps.len() {
        return Ok(Vec::new());
    }

    // Which of them git already has
    let check = git(
        root,
        &["cat-file", "--batch-check"],
        Some(format!("{}\n", hashes.join("\n")).into_bytes()),
    )?;
    let check = match check {
        Some(out) if !out.is_empty() => decode_strict(out)?,
        _ => String::new(),
    };
    let lines = splitlines(&check);
    if lines.len() != ps.len() {
        return Ok(Vec::new());
    }
    Ok(ps
        .into_iter()
        .zip(lines)
        .filter(|(_, l)| !l.ends_with(" missing"))
        .map(|(p, _)| p.clone())
        .collect())
}

/// python `git diff --name-only -z <a> <b>` 의 경로들(surrogateescape). 실패하면 빈 목록.
pub fn diff_names(root: &str, a: &str, b: &str) -> Result<Vec<String>> {
    let out = git(root, &["diff", "--name-only", "-z", a, b], None)?.unwrap_or_default();
    Ok(decode_os(&out).split('\0').map(str::to_owned).collect())
}
