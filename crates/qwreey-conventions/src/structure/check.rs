//! 파일 하나의 길이, 성장, 폴더를 보고 알릴 문장을 만든다(python `check_file`).
//!
//! 길이 알림(warn, hard, grow, 예외)은 파일마다, 폴더 알림(flat, family)은 폴더마다 회차당 한 번이다.
//! 테스트 파일은 기준을 두 배로 보고, 머리 6줄에 생성물 표시가 있으면 보지 않는다.

use std::sync::LazyLock;

use harness_hook::py::fs;
use harness_hook::py::path::{abspath, basename, dirname, join, relpath, splitext};
use harness_hook::py::re::{Flags, Regex};
use harness_hook::py::value::{Dict, Value};

use super::Run;
use super::config::Config;
use super::exempt::{Exemption, exemption};
use super::note::{Level, Note};
use super::num::{Limit, Num};
use super::pyops::{append, contains, fnmatch, items, items_or_empty, str_order};
use super::state::Ledger;
use super::toolkit::{Table, Toolkit, first_comment};
use crate::edit::{generated, project_root};
use crate::halt::{Halt, Result};
use crate::pyval;

/// 경로에 이 폴더가 있으면 보지 않는다(python `SKIP_PARTS`, 툴킷의 `skip_parts` 와 합친다).
const SKIP_PARTS: &[&str] = &[
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
    "media",
    "fixtures",
];

/// 같은 꼴의 파일이 모이는 폴더(소문자). 폴더 알림을 하지 않는다(python `HOMOGENEOUS`).
const HOMOGENEOUS: &[&str] = &[
    "test", "tests", "spec", "specs", "stories", "spikes", "meshes", "assets", "examples",
    "gallery",
];

/// 머리에서 생성물 표시를 찾는 줄 수.
const GEN_LINES: usize = 6;
/// 예외 표식을 찾는 머리 줄 수.
const HEAD_LINES: usize = 10;
/// 이 앞 바이트에 NUL 이 있으면 바이너리 파일로 본다.
const BINARY_PROBE: usize = 1024;

static TEST_PATH: LazyLock<Regex> = LazyLock::new(|| {
    Regex::with_flags(
        r"(^|/)(tests?|specs?|spikes?|bench|__tests__)(/|$)|\.(spec|test|story)\.|_test\.(go|rs)$",
        Flags::IGNORECASE,
    )
    .expect("constant pattern")
});
static PASCAL_PREFIX: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"^([A-Z][a-z0-9]+)(?=[A-Z])").expect("constant pattern"));

/// 새 파일인가(Write 만). `Sure` 면 성장 기준점을 0 으로 둔다.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Created {
    /// `tool_response.type` 이 `create`.
    Sure,
    /// 그 값이 없고 이 회차에 처음 쓴 파일.
    Guess,
}

/// 길이를 잰 소스 파일(python check_file 의 앞부분이 모으는 값).
struct Measured {
    path: String,
    root: String,
    rel: String,
    cfg: Config,
    table: Table,
    toolkit: Toolkit,
    lines: usize,
    head: String,
}

/// python `check_file(path, ...)`: 이 파일에 대해 알릴 문장들.
pub fn check_file(
    run: &Run,
    ledger: &mut Ledger,
    path: &str,
    created: Option<Created>,
) -> Result<Vec<Note>> {
    let path = abspath(path).ok_or(Halt::PyError("os.getcwd failed"))?;
    if !fs::is_file(&path) {
        return Ok(Vec::new());
    }
    let Some(file) = measure(run, path)? else {
        return Ok(Vec::new());
    };

    // The entry and its growth baseline
    let n = file.lines;
    ledger.open_entry(&file.path, || {
        let add = added_lines(run.tool, run.ti)?;
        Ok(match (created, add) {
            (Some(Created::Sure), _) => 0,
            (_, Some(add)) => n as i128 - add,
            (_, None) => n as i128,
        })
    })?;

    // Limits, doubled for tests
    let is_test = TEST_PATH.is_match(&file.rel) || file.toolkit.spec_test(&file.rel)?;
    let k = if is_test { 2 } else { 1 };
    let limits = Limits::of(&file.toolkit, &file.cfg, k)?;

    let mut notes = length_notes(run, ledger, &file, &limits)?;
    if created.is_some() && !is_test && !homogeneous(&file.path) {
        notes.extend(folder_notes(ledger, &file)?);
    }
    Ok(notes)
}

// 툴킷과 줄 수를 재고, 보지 않을 파일(툴킷 밖, 건너뛸 폴더, ignore, 바이너리, 생성물)이면 None
fn measure(run: &Run, path: String) -> Result<Option<Measured>> {
    // Root, config and toolkit
    let root = match project_root(&path, run.input.get("cwd"), &run.ctx.env) {
        Err(Halt::Unported(why)) => return Err(Halt::Unported(why)),
        // 글이 아닌 cwd 는 load_cfg 가 잡고 relpath 에서 끝난다
        other => other,
    };
    let cfg = root
        .as_ref()
        .map_or_else(|_| Config::defaults(), |r| Config::load(r));
    let table = Table::new(&cfg, run.toolkits());
    let Some(toolkit) = table.of(basename(&path))?.cloned() else {
        return Ok(None);
    };
    let root = root?;
    let rel = relpath(&path, &root).ok_or(Halt::PyError("os.path.relpath failed"))?;

    // Folders and globs that are not measured
    let skip = toolkit.skip_parts()?;
    let mut parts: Vec<&str> = rel.split('/').collect();
    parts.pop();
    if parts
        .iter()
        .any(|p| SKIP_PARTS.contains(p) || skip.iter().any(|s| s == p))
    {
        return Ok(None);
    }
    for glob in items(cfg.item("ignore"))? {
        let glob = glob
            .as_str()
            .ok_or(Halt::PyError("fnmatch with a non-string pattern"))?;
        if fnmatch(&rel, glob)? {
            return Ok(None);
        }
    }

    // Line count and head
    let Ok(raw) = fs::read_bytes(&path) else {
        return Ok(None);
    };
    if raw[..raw.len().min(BINARY_PROBE)].contains(&0) {
        return Ok(None);
    }
    let text = String::from_utf8_lossy(&raw);
    let lines = text.matches('\n').count() + usize::from(!text.is_empty() && !text.ends_with('\n'));
    let head = text
        .splitn(HEAD_LINES + 1, '\n')
        .take(HEAD_LINES)
        .collect::<Vec<_>>()
        .join("\n");
    if generated(&head, GEN_LINES) {
        return Ok(None);
    }

    Ok(Some(Measured {
        path,
        root,
        rel,
        cfg,
        table,
        toolkit,
        lines,
        head,
    }))
}

/// 이 파일의 세 기준(python `warn, hard, grow = (spec.get(x, cfg[x]) * k for x in ...)`).
struct Limits {
    warn: Limit,
    hard: Limit,
    grow: Limit,
}

impl Limits {
    // python 은 셋을 차례로 곱하다 처음 예외에서 끝난다. 이 판이 옮기지 않은 값은 그 뒤의 예외보다 뒤로 미룬다
    fn of(toolkit: &Toolkit, cfg: &Config, k: i128) -> Result<Limits> {
        let got = ["warn", "hard", "grow"].map(|key| toolkit.limit(key, cfg, k));
        if let Some(Err(e @ Halt::PyError(_))) =
            got.iter().find(|r| matches!(r, Err(Halt::PyError(_))))
        {
            return Err(*e);
        }
        let [warn, hard, grow] = got;
        Ok(Limits {
            warn: warn?,
            hard: hard?,
            grow: grow?,
        })
    }
}

// 길이 알림: 예외 사유, hard, warn, 무효한 예외, 성장
fn length_notes(
    run: &Run,
    ledger: &mut Ledger,
    file: &Measured,
    limits: &Limits,
) -> Result<Vec<Note>> {
    let (rel, n) = (file.rel.as_str(), Num::Int(file.lines as i128));
    let comments = file.toolkit.comments();
    let mut said = ledger.said(&file.path)?;
    let ex = exemption(&file.head, rel, &file.cfg, &comments)?;
    let exempt = ex.as_ref().is_some_and(|e| e.valid);
    let mut notes = Vec::new();

    // A valid exemption says its reason once
    if exempt && limits.warn.reached_by(n)? && !contains(&said, "exempt")? {
        append(&mut said, "exempt")?;
        let e = ex
            .as_ref()
            .map_or(("", ""), |e| (e.reason.as_str(), e.source));
        notes.push(Note::new(
            Level::Info,
            format!(
                "`{rel}` ({} lines) has a structure exemption. Reason: {} ({})",
                file.lines, e.0, e.1
            ),
        ));
    }

    // Hard, else warn
    if exempt {
    } else if limits.hard.reached_by(n)? && !contains(&said, "hard")? {
        extend(&mut said, &["hard", "warn"])?;
        notes.push(hard_note(run, file, &limits.hard, &comments)?);
    } else if limits.warn.reached_by(n)? && !contains(&said, "warn")? {
        append(&mut said, "warn")?;
        notes.push(Note::new(
            Level::Warn,
            format!(
                "`{rel}` is {} lines (warn limit {}). Before adding more, check for a responsibility group to split out; \
                 if there is one, name the split candidate in one line in your report.",
                file.lines,
                limits.warn.text()
            ),
        ));
    }

    // An invalid exemption is named
    if let Some(Exemption {
        reason,
        valid: false,
        source,
    }) = &ex
        && limits.warn.reached_by(n)?
        && !contains(&said, "exempt-bad")?
        && said.truthy()
    {
        append(&mut said, "exempt-bad")?;
        notes.push(Note::new(
            Level::Warn,
            format!(
                "The structure exemption on `{rel}` ({source}) is invalid: the reason is empty or not a reason (\"{reason}\"). \
                 Give a real reason or remove the mark."
            ),
        ));
    }

    // Growth this session
    if !exempt {
        let (base, base_text) = ledger.base(&file.path)?;
        let grew = n.sub(base)?;
        if limits.grow.reached_by(grew)? && limits.warn.reached_by(n)? && !contains(&said, "grow")?
        {
            append(&mut said, "grow")?;
            notes.push(Note::new(
                Level::Warn,
                format!(
                    "`{rel}` grew {base_text} -> {} lines (+{}) this session. If you keep appending new code \
                     to one file, first see whether it can become a new module.",
                    file.lines,
                    grew.text()
                ),
            ));
        }
    }

    ledger.set_said(&file.path, said)?;
    Ok(notes)
}

// python `said += [...]`: 목록만 늘릴 수 있다
fn extend(said: &mut Value, kinds: &[&str]) -> Result<()> {
    if !matches!(said, Value::List(_)) {
        return Err(Halt::PyError("+= on a said value that is not a list"));
    }
    kinds.iter().try_for_each(|k| append(said, k))
}

// 강제 기준 알림. luau 면 분리 계획기 명령을 붙인다
fn hard_note(run: &Run, file: &Measured, hard: &Limit, comments: &Value) -> Result<Note> {
    let planner = if file.toolkit.name == "luau" {
        run.find_planner()?
    } else {
        None
    };
    let plan = planner.map_or_else(String::new, |p| {
        format!(
            " First extract candidate groups with `python3 -I {p} {}` (read-only).",
            file.path
        )
    });
    let first = first_comment(comments)?;

    Ok(Note::new(
        Level::Action,
        format!(
            "`{}` is {} lines, over the hard limit ({}). Finish the current edit, but before adding more features \
             to this file, propose a split to the user (which groups go where; a move-only commit first) and wait for an answer.{plan} \
             If the file must stay whole for a solid reason (type limits, generated, pure data), put \
             `{first}@structure-exempt: <reason>` in its header.",
            file.rel,
            file.lines,
            hard.text()
        ),
    ))
}

// 새 파일의 폴더가 같은 꼴의 파일을 모으는 곳인가(test, assets 등)
fn homogeneous(path: &str) -> bool {
    let folder = basename(dirname(path)).to_lowercase();
    HOMOGENEOUS.contains(&folder.as_str())
}

// 폴더 알림: 소스가 많은 평평한 폴더, 같은 PascalCase 접두의 파일 묶음
fn folder_notes(ledger: &mut Ledger, file: &Measured) -> Result<Vec<Note>> {
    let dir = dirname(&file.path);
    let names = fs::listdir(dir).unwrap_or_default();

    // Sources and visible subfolders here
    let mut srcs: Vec<&str> = Vec::new();
    for name in &names {
        if file.table.of(name)?.is_some() && fs::is_file(&join(dir, name)) {
            srcs.push(name);
        }
    }
    let subdirs: Vec<&str> = names
        .iter()
        .filter(|x| fs::is_dir(&join(dir, x)) && !x.starts_with('.'))
        .map(String::as_str)
        .collect();

    // Where the folder sits and what its entry file is
    let drel = relpath(dir, &file.root).ok_or(Halt::PyError("os.path.relpath failed"))?;
    let entry_name = if file.toolkit.name == "luau" {
        "init.luau"
    } else {
        "an index file"
    };
    let mut notes = Vec::new();

    // A flat folder
    let flat = Limit::of(file.cfg.item("flat"), 1)?;
    if flat.reached_by(Num::Int(srcs.len() as i128))?
        && subdirs.len() <= 2
        && !contains(ledger.seen_dirs()?, &drel)?
    {
        ledger.see_dir(&drel)?;
        notes.push(Note::new(
            Level::Info,
            format!(
                "`{drel}/` has {} source files and {} subfolders. \
                 If related files form groups, consider proposing folders ({entry_name}); a flat layout by design needs nothing.",
                srcs.len(),
                subdirs.len()
            ),
        ));
    }

    // A family of files with one prefix
    let prefix = prefix_of(splitext(basename(&file.path)).0);
    let mut family: Vec<&str> = srcs
        .iter()
        .map(|x| splitext(x).0)
        .filter(|stem| prefix_of(stem) == prefix)
        .collect();
    family.sort_by(|a, b| str_order(a, b));
    family.dedup();
    let key = format!("{drel}::{prefix}");
    if family.len() >= 3 && !subdirs.contains(&prefix) && !contains(ledger.seen_dirs()?, &key)? {
        ledger.see_dir(&key)?;
        notes.push(Note::new(
            Level::Info,
            format!(
                "`{drel}/` has {} files starting with `{prefix}` ({}). Consider grouping them into a `{prefix}/` folder ({entry_name}).",
                family.len(),
                family.join(", ")
            ),
        ));
    }
    Ok(notes)
}

/// python `prefix_of(stem)`: 앞의 PascalCase 낱말(`ItemView` 의 `Item`), 없으면 이름 그대로.
fn prefix_of(stem: &str) -> &str {
    PASCAL_PREFIX
        .match_start(stem)
        .and_then(|m| m.text(stem, 1))
        .unwrap_or(stem)
}

/// python `added_lines(tool, ti)`: 편집이 늘린 줄 수(Edit, MultiEdit). Write 와 Bash 는 `None`.
fn added_lines(tool: &str, ti: Option<&Dict>) -> Result<Option<i128>> {
    match tool {
        "Edit" => Ok(Some(delta(ti)?)),
        "MultiEdit" => {
            let mut sum = 0;
            for e in items_or_empty(pyval::get(ti, "edits"))? {
                sum += delta(Some(
                    e.as_dict()
                        .ok_or(Halt::PyError("an edit that is not a dict"))?,
                ))?;
            }
            Ok(Some(sum))
        }
        _ => Ok(None),
    }
}

// python (e.get("new_string") or "").count("\n") - (e.get("old_string") or "").count("\n")
fn delta(edit: Option<&Dict>) -> Result<i128> {
    Ok(newlines(pyval::get(edit, "new_string"))? - newlines(pyval::get(edit, "old_string"))?)
}

// python `x.count("\n")`: 글은 줄바꿈 수, 목록은 "\n" 원소 수, 다른 참인 값에는 count 가 없다
fn newlines(value: Option<&Value>) -> Result<i128> {
    Ok(match value {
        None => 0,
        Some(v) if !v.truthy() => 0,
        Some(Value::Str(s)) => s.matches('\n').count() as i128,
        Some(Value::List(items)) => items
            .iter()
            .filter(|x| matches!(x, Value::Str(s) if s == "\n"))
            .count() as i128,
        Some(_) => return Err(Halt::PyError("count() on a value that has none")),
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use harness_hook::py::json_load::loads;

    /// 늘린 줄 수는 python 의 `count` 처럼 값의 꼴마다 센다.
    #[test]
    fn added_lines_like_python() {
        // Edit and MultiEdit count newline differences
        let edit = loads(r#"{"old_string": "a", "new_string": "a\n\n"}"#).unwrap();
        assert_eq!(added_lines("Edit", edit.as_dict()).unwrap(), Some(2));
        let multi = loads(r#"{"edits": [{"new_string": "\n"}, {"old_string": "\n\n"}]}"#).unwrap();
        assert_eq!(added_lines("MultiEdit", multi.as_dict()).unwrap(), Some(-1));
        assert_eq!(added_lines("Write", None).unwrap(), None);

        // A list new_string counts "\n" elements; a number has no count
        let list = loads(r#"{"new_string": ["\n", "a", "\n"]}"#).unwrap();
        assert_eq!(added_lines("Edit", list.as_dict()).unwrap(), Some(2));
        assert!(added_lines("Edit", loads(r#"{"new_string": 5}"#).unwrap().as_dict()).is_err());
    }

    /// PascalCase 접두는 다음 대문자 앞까지다.
    #[test]
    fn pascal_prefix() {
        // Only an uppercase letter after the word makes a prefix
        assert_eq!(prefix_of("ItemZoneView"), "Item");
        assert_eq!(prefix_of("Item"), "Item");
        assert_eq!(prefix_of("item_view"), "item_view");
    }
}
