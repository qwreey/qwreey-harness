//! 훅 입력 읽기(python `hooks/conv_edit.py`): 프로젝트 루트, 이번 편집이 추가한 줄, 건너뛸 경로.
//!
//! 줄 번호는 0 기반이다. 추가한 줄은 정렬된 집합([`Added`])으로 둔다(python `set`, 쓰는 곳은 `in` 과 `sorted`).

use std::collections::{BTreeSet, HashMap};
use std::sync::LazyLock;

use harness_hook::Env;
use harness_hook::py::fs;
use harness_hook::py::num::parse_int;
use harness_hook::py::path::{dirname, join};
use harness_hook::py::re::{Flags, Regex};
use harness_hook::py::text::strip;
use harness_hook::py::value::{Dict, Value};

use crate::halt::{Halt, Result};

/// 이보다 큰 파일은 읽지 않는다(python `MAX_BYTES`).
pub const MAX_BYTES: u64 = 1_000_000;

/// 경로에 이 조각이 있으면 보지 않는다(python `SKIP_PARTS`).
pub const SKIP_PARTS: &[&str] = &[
    "node_modules",
    ".git",
    "luau_packages",
    "roblox_packages",
    "lune_packages",
    "Packages",
    "vendor",
    "third_party",
    "build",
    "dist",
    "refs",
    "typedefs",
    "testdata",
    "fixtures",
    "__snapshots__",
    "snapshots",
    "__pycache__",
    ".venv",
    "venv",
    "target",
];

/// 생성 파일과 타입 선언의 접미사(python `SKIP_SUFFIX`).
pub const SKIP_SUFFIX: &[&str] = &[
    ".d.luau",
    ".d.ts",
    ".d.mts",
    ".min.js",
    ".gen.ts",
    ".pb.go",
    "_pb2.py",
    "_pb2_grpc.py",
];

/// 생성 파일 표시(python `GEN_MARK`). 머리 몇 줄에서 찾는다.
pub const GEN_MARK_PATTERN: &str =
    r"generated|do not edit|@generated|손으로 고치지 않는다|만든 것:";

static GEN_MARK: LazyLock<Regex> = LazyLock::new(|| {
    Regex::with_flags(GEN_MARK_PATTERN, Flags::IGNORECASE).expect("constant pattern")
});

/// 머리 `lines` 줄 안에 생성 파일 표시가 있는가(python `any(GEN_MARK.search(l) for l in text.split("\n", n)[:n])`).
pub fn generated(text: &str, lines: usize) -> bool {
    text.splitn(lines + 1, '\n')
        .take(lines)
        .any(|l| GEN_MARK.is_match(l))
}

/// 추가한 줄 번호(0 기반).
pub type Added = BTreeSet<usize>;

/// python `project_root(path, data)`: 편집한 파일이 든 프로젝트의 루트.
///
/// `$CLAUDE_PROJECT_DIR` 안이면 그것, 아니면 위로 `.git` 이나 `.claude` 폴더가 있는 폴더,
/// 없으면 입력의 `cwd`, 그것도 없으면 파일의 폴더.
///
/// python 은 `//` 로 시작하는 경로에서 `dirname` 이 줄지 않아 멈추지 않는다. 여기서는 줄지 않으면 멈춘다.
pub fn project_root(path: &str, cwd: Option<&Value>, env: &Env) -> Result<String> {
    if let Some(dir) = env.get_nonempty("CLAUDE_PROJECT_DIR")
        && path.starts_with(&format!("{}/", dir.trim_end_matches('/')))
    {
        return Ok(dir.to_owned());
    }

    // Walk up to a repo marker
    let mut d = dirname(path);
    while !d.is_empty() && d != "/" {
        if fs::exists(&join(d, ".git")) || fs::is_dir(&join(d, ".claude")) {
            return Ok(d.to_owned());
        }
        let up = dirname(d);
        if up == d {
            return Err(Halt::Unported("a path whose dirname does not shrink"));
        }
        d = up;
    }

    match cwd {
        Some(Value::Str(c)) if !c.is_empty() => Ok(c.clone()),
        Some(v) if v.truthy() => Err(Halt::PyError("cwd is not a string")),
        _ => Ok(dirname(path).to_owned()),
    }
}

/// python `added_set(old, new, base_line)`: `new` 의 줄 가운데 `old` 에 없던 줄의 파일 줄 번호.
///
/// 줄은 앞뒤 공백을 떼고 견준다. 같은 줄이 `old` 에 여러 번 있으면 그만큼만 지운다. 빈 줄은 세지 않는다.
pub fn added_set(old: &str, new: &str, base_line: usize) -> Added {
    let mut have: HashMap<&str, usize> = HashMap::new();
    if !old.is_empty() {
        for l in old.split('\n') {
            *have.entry(strip(l)).or_insert(0) += 1;
        }
    }

    let mut res = Added::new();
    for (idx, l) in new.split('\n').enumerate() {
        let t = strip(l);
        if t.is_empty() {
            continue;
        }
        match have.get_mut(t) {
            Some(n) if *n > 0 => *n -= 1,
            _ => {
                res.insert(base_line + idx);
            }
        }
    }
    res
}

/// python `patch_added(sp)`: `structuredPatch`(훈크 목록)에서 새 파일 기준 추가 줄. 꼴이 틀리면 `Ok(None)`.
///
/// python 이 잡지 않는 예외(반복할 수 없는 값, 글이 아닌 줄, 무한대 `newStart`)는 [`Halt::PyError`] 다.
pub fn patch_added(sp: Option<&Value>) -> Result<Option<Added>> {
    let mut res = Added::new();

    // Which values python iterates
    let hunks = match sp {
        None => return Ok(Some(res)),
        Some(v) if !v.truthy() => return Ok(Some(res)),
        Some(Value::List(items)) => items,
        // dict 는 키(글)를, 글은 글자를 돌며 `h["newStart"]` 에서 TypeError(잡힌다)
        Some(Value::Dict(_) | Value::Str(_)) => return Ok(None),
        Some(_) => return Err(Halt::PyError("structuredPatch is not iterable")),
    };

    // Count added lines hunk by hunk
    for h in hunks {
        let Value::Dict(h) = h else { return Ok(None) };
        let Some(start) = h.get("newStart").map(py_int).transpose()?.flatten() else {
            return Ok(None);
        };
        let mut cur = start - 1;
        let lines = match h.get("lines") {
            Some(v) if v.truthy() => v,
            _ => continue,
        };
        for l in hunk_lines(lines)? {
            let Some(l) = l else { return Ok(None) };
            if l.starts_with('+') {
                // 음수 줄은 python 이 목록 끝에서 세는 자리라 옮기지 않는다
                let line =
                    usize::try_from(cur).map_err(|_| Halt::Unported("a negative patch line"))?;
                res.insert(line);
                cur += 1;
            } else if !l.starts_with('-') {
                cur += 1;
            }
        }
    }
    Ok(Some(res))
}

// `h.get("lines") or []` 를 도는 값: 목록은 원소, dict 는 키, 글은 글자. 원소가 글이 아니면 python 은 startswith 에서 끝난다.
// 숫자처럼 돌 수 없는 값은 TypeError(잡힌다): None 하나로 알린다
fn hunk_lines(lines: &Value) -> Result<Vec<Option<String>>> {
    Ok(match lines {
        Value::List(items) => items
            .iter()
            .map(|l| match l {
                Value::Str(s) => Ok(Some(s.clone())),
                _ => Err(Halt::PyError("a patch line is not a string")),
            })
            .collect::<Result<_>>()?,
        Value::Dict(d) => d.iter().map(|(k, _)| Some(k.to_owned())).collect(),
        Value::Str(s) => s.chars().map(|c| Some(c.to_string())).collect(),
        _ => vec![None],
    })
}

// python int(v): 잡히는 실패(TypeError, ValueError)는 Ok(None), 잡히지 않는 실패(무한대의 OverflowError)는 Err
fn py_int(v: &Value) -> Result<Option<i128>> {
    Ok(match v {
        Value::Bool(b) => Some(i128::from(*b)),
        Value::Int(i) => Some(*i),
        Value::Float(f) if f.is_nan() => None,
        Value::Float(f) if f.is_infinite() => {
            return Err(Halt::PyError("int() of an infinite float"));
        }
        Value::Float(f) => Some(f.trunc() as i128),
        Value::Str(s) => parse_int(s),
        Value::BigInt(_) => return Err(Halt::Unported("a huge patch line number")),
        _ => None,
    })
}

/// python `locate(text, new_string)`: `text` 안에서 `new` 가 시작하는 줄(0 기반). 없으면 `None`.
pub fn locate(text: &str, new: &str) -> Option<usize> {
    if new.is_empty() {
        return None;
    }
    let k = text.find(new)?;
    Some(text[..k].bytes().filter(|&b| b == b'\n').count())
}

/// python `collect(tool, ti, resp, text)`: (검사할 글, 추가한 줄). 볼 것이 없으면 `None`.
///
/// Write 는 `content` 가 글이고, 새 파일이면 전체, 덮어쓰기면 `originalFile` 과의 차이(없으면 `structuredPatch`)다.
/// Edit, MultiEdit 는 디스크 글 `text` 에서 `new_string` 이 놓인 자리의 줄 가운데 `old_string` 에 없던 줄이다.
pub fn collect(
    tool: &str,
    ti: Option<&Dict>,
    resp: Option<&Dict>,
    text: Option<&str>,
) -> Result<Option<(String, Added)>> {
    if tool == "Write" {
        let Some(Value::Str(content)) = crate::pyval::get(ti, "content") else {
            return Ok(None);
        };
        if let Some(Value::Str(t)) = crate::pyval::get(resp, "type")
            && t == "create"
        {
            return Ok(Some((content.clone(), added_set("", content, 0))));
        }
        if let Some(Value::Str(orig)) = crate::pyval::get(resp, "originalFile") {
            return Ok(Some((content.clone(), added_set(orig, content, 0))));
        }
        return Ok(patch_added(crate::pyval::get(resp, "structuredPatch"))?
            .map(|sp| (content.clone(), sp)));
    }

    // Edit and MultiEdit
    let edits: Vec<&Dict> = if tool == "Edit" {
        ti.into_iter().collect()
    } else {
        match crate::pyval::get(ti, "edits") {
            Some(Value::List(items)) => items.iter().filter_map(Value::as_dict).collect(),
            Some(Value::Dict(_) | Value::Str(_)) | None => Vec::new(),
            Some(v) if !v.truthy() => Vec::new(),
            Some(_) => return Err(Halt::PyError("edits is not iterable")),
        }
    };
    let Some(text) = text else { return Ok(None) };
    let mut added = Added::new();
    for e in edits {
        let new = match e.get("new_string") {
            Some(Value::Str(s)) if !s.is_empty() => s,
            _ => continue,
        };
        let Some(base) = locate(text, new) else {
            continue;
        };
        let old = crate::pyval::str_or_empty(e.get("old_string"))?;
        added.extend(added_set(old, new, base));
    }
    Ok(Some((text.to_owned(), added)))
}

#[cfg(test)]
mod tests {
    use super::*;
    use harness_hook::py::json_load::loads;

    /// old 에 있던 줄(공백 무시, 빈 줄 제외)을 뺀 new 의 줄을 파일 줄 번호로 센다.
    #[test]
    fn added_lines_like_python() {
        // Only the second b is new
        let got = added_set("a\n b\n", "a\nb\nc\n\nb", 10);
        assert_eq!(got.into_iter().collect::<Vec<_>>(), vec![12, 14]);

        // locate gives the 0-based line where new_string starts
        assert_eq!(locate("x\ny\nz", "y\nz"), Some(1));
        assert_eq!(locate("x", ""), None);
    }

    /// structuredPatch 의 꼴마다 python 과 같은 결과(줄, 볼 것 없음, 예외)를 낸다.
    #[test]
    fn structured_patch_shapes() {
        // `+` lines count from newStart, `-` lines do not move the cursor
        let sp = loads(r#"[{"newStart": 3, "lines": [" a", "-b", "+c", "+d", " e"]}]"#).unwrap();
        let got = patch_added(Some(&sp)).unwrap().unwrap();
        assert_eq!(got.into_iter().collect::<Vec<_>>(), vec![3, 4]);

        // Odd shapes: nothing to check, or a python error
        assert_eq!(
            patch_added(Some(&loads(r#"{"a": 1}"#).unwrap())).unwrap(),
            None
        );
        assert!(patch_added(Some(&loads("5").unwrap())).is_err());
        assert_eq!(
            patch_added(Some(&loads(r#"[{"lines": []}]"#).unwrap())).unwrap(),
            None
        );
    }
}
