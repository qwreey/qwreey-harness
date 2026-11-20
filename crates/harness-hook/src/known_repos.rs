//! 이 기기에서 Claude Code 로 일한 저장소 목록(정본 `lib/known_repos.py`).
//!
//! 출처는 python 과 같다: `<설정 디렉터리>/projects/*/` 마다 가장 최근 `*.jsonl` 앞부분의 첫 `"cwd"`, 옵션
//! `HARNESS_WORKSPACE_EXTRA`(저장소 또는 그 아래 자식 저장소), 옛 `HARNESS_WORKSPACE`(자식 저장소). 그 뒤
//! `HARNESS_WORKSPACE_EXCLUDE` 와 기본 제외(임시 폴더, `~/.cache`, `.claude/worktrees/`)로 뺀다. worktree 는 본 저장소로 합친다.
//!
//! 캐시 `$CLAUDE_PLUGIN_DATA/known_repos.json` 은 python 과 같은 꼴로 읽고 쓴다(두 판이 번갈아 써도 된다).
//! python 은 수집 중 예외가 나면 부르는 쪽이 "못 찾음"으로 본다. 여기서는 그 자리마다 [`Failed`] 를 돌려준다.
//!
//! python 과 달라지는 곳: UTF-8 이 아닌 경로 바이트(서로게이트 자리표)는 정렬 자리가 다르고, 세션 파일의 cwd 가
//! UTF-8 로 인코딩한 서로게이트(python `surrogatepass` 가 받는 바이트)면 여기서는 읽지 못한 cwd 로 본다.

use std::path::Path;

use crate::env::Env;
use crate::py::fnmatch::fnmatch;
use crate::py::fs::{self, FsError};
use crate::py::json::{EnsureAscii, dumps};
use crate::py::json_load::{Decode, from_bytes, loads};
use crate::py::path::{abspath, expanduser, join, normpath};
use crate::py::surrogate::unit_of;
use crate::py::tempfile::gettempdir;
use crate::py::text::strip;
use crate::py::value::{Dict, Value};
use crate::settings::{self, LoadRequest, Project};

/// 옵션을 가진 플러그인(qwreey-workspace 의 userConfig).
pub const OPTION_OWNER: &str = "qwreey-workspace";
/// 옵션 키와 기본값(python `KNOWN_REPOS_DEFAULTS`).
pub const DEFAULTS: &[(&str, &str)] = &[
    ("HARNESS_WORKSPACE_EXTRA", ""),
    ("HARNESS_WORKSPACE_EXCLUDE", ""),
];
/// 저장소 층이 바꾸지 못하는 키(python `KNOWN_REPOS_USER_ONLY`).
pub const USER_ONLY: &[&str] = &["HARNESS_WORKSPACE_EXTRA", "HARNESS_WORKSPACE_EXCLUDE"];
/// 캐시 파일 이름과 판.
pub const CACHE_FILE: &str = "known_repos.json";
pub const CACHE_VERSION: i128 = 1;
/// 세션 파일 앞부분에서 cwd 를 찾는 한도: 먼저 작게, 없으면 끝까지.
const HEAD_FIRST: usize = 32 * 1024;
const HEAD_BYTES: usize = 256 * 1024;

/// python 이 예외로 끝나는 수집(부르는 쪽은 "저장소 없음"으로 본다).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Failed(pub &'static str);

/// 세 옵션 값(python `options()`), 앞뒤 공백을 뗀 글.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct Options {
    pub extra: String,
    pub exclude: String,
    pub workspace: String,
}

/// python `options()`: 사용자 harness.env < qwreey-workspace 옵션 < 환경 변수. 읽지 못하면 환경 변수만.
///
/// `plugin_dir` 은 부르는 플러그인의 자리(python 은 `harness_env.py` 사본의 자리에서 자기 플러그인 옵션도 읽는다).
pub fn options(env: &Env, plugin_dir: Option<&Path>) -> Options {
    let owners: &[(&str, &[&str])] = &[(OPTION_OWNER, USER_ONLY)];
    let request = LoadRequest {
        project: Project::Skip,
        defaults: DEFAULTS,
        user_only: USER_ONLY,
        options: owners,
        plugin_dir,
        ..LoadRequest::default()
    };
    let layers = settings::load_layers(env, &request).ok();

    // 층을 읽지 못하면(홈을 모름) 환경 변수만 본다
    let get = |key: &str| -> String {
        let value = match &layers {
            Some(l) => l.get(key),
            None => env.get(key),
        };
        strip(value.unwrap_or("")).to_owned()
    };
    Options {
        extra: get("HARNESS_WORKSPACE_EXTRA"),
        exclude: get("HARNESS_WORKSPACE_EXCLUDE"),
        workspace: get("HARNESS_WORKSPACE"),
    }
}

/// python `config_dir()`: `$CLAUDE_CONFIG_DIR`, 없으면 `~/.claude`.
pub fn config_dir(env: &Env) -> String {
    match env.get_nonempty("CLAUDE_CONFIG_DIR") {
        Some(dir) => dir.to_owned(),
        None => join(&expanduser("~", env), ".claude"),
    }
}

// python _split: `;` 로 나눈 경로들, 빈 조각은 빼고 `~` 를 푼다
fn split_paths(value: &str, env: &Env) -> Vec<String> {
    value
        .split(';')
        .map(strip)
        .filter(|p| !p.is_empty())
        .map(|p| expanduser(p, env))
        .collect()
}

/// `d/.git` 의 꼴(python `_git_entry`).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum GitEntry {
    Dir,
    File,
}

fn git_entry(d: &str) -> Option<GitEntry> {
    let os = fs::os_path(&join(d, ".git"))?;
    let meta = std::fs::metadata(os).ok()?;
    Some(if meta.is_dir() {
        GitEntry::Dir
    } else {
        GitEntry::File
    })
}

/// python `_fold(d)`: `.git` 이 파일인 d 를 본 저장소로. 서브모듈 등은 d, 본 저장소가 없으면 `None`.
fn fold(d: &str) -> Option<String> {
    let text = fs::read_text_replace(&join(d, ".git")).ok()?;
    let line = strip(text.split('\n').next().unwrap_or(""));
    let Some(target) = line.strip_prefix("gitdir:") else {
        return Some(d.to_owned());
    };

    // <본>/.git/worktrees/<이름> 이면 <본>
    let gitdir = normpath(&join(d, strip(target)));
    let slashed = gitdir.replace('\\', "/");
    let parts: Vec<&str> = slashed.split('/').collect();
    for i in (1..parts.len().saturating_sub(1)).rev() {
        if parts[i] == ".git" && parts[i + 1] == "worktrees" {
            let joined = parts[..i].join("/");
            let main = normpath(if joined.is_empty() { "/" } else { &joined });
            return (git_entry(&main) == Some(GitEntry::Dir)).then_some(main);
        }
    }
    Some(d.to_owned())
}

/// python `repo_root(path)`: path 를 담은 저장소 루트. worktree 는 본 저장소로, 없으면 `None`.
pub fn repo_root(path: &str) -> Option<String> {
    let mut d = abspath(path)?;
    loop {
        match git_entry(&d) {
            Some(GitEntry::Dir) => return Some(d),
            Some(GitEntry::File) => return fold(&d),
            None => {}
        }
        let up = crate::py::path::dirname(&d).to_owned();
        if up == d {
            return None;
        }
        d = up;
    }
}

/// `"cwd"\s*:\s*"((?:[^"\\]|\\.)*)"` 의 첫 일치에서 따옴표 안 바이트(python 바이트 정규식 `_CWD`).
///
/// 괄호 안의 되풀이는 `"` 를 `\` 뒤에서만 먹으므로, 먹을 수 없는 첫 자리가 `"` 가 아니면 그 시작은 맞지 않는다.
fn find_cwd(head: &[u8]) -> Option<&[u8]> {
    const KEY: &[u8] = b"\"cwd\"";
    let space = |b: u8| matches!(b, b' ' | b'\t' | b'\n' | b'\r' | 0x0b | 0x0c);
    let mut from = 0;
    while let Some(at) = head[from..].windows(KEY.len()).position(|w| w == KEY) {
        let start = from + at;
        from = start + 1;

        // Separator and opening quote
        let mut i = start + KEY.len();
        while i < head.len() && space(head[i]) {
            i += 1;
        }
        if head.get(i) != Some(&b':') {
            continue;
        }
        i += 1;
        while i < head.len() && space(head[i]) {
            i += 1;
        }
        if head.get(i) != Some(&b'"') {
            continue;
        }

        // Body up to the closing quote
        let body = i + 1;
        let mut j = body;
        loop {
            match head.get(j) {
                Some(b'"') => return Some(&head[body..j]),
                Some(b'\\') if head.get(j + 1).is_some_and(|&b| b != b'\n') => j += 2,
                Some(b'\\') | None => break,
                Some(_) => j += 1,
            }
        }
    }
    None
}

// python _cwd_of: 가장 최근 jsonl 셋까지에서 첫 cwd
fn cwd_of(folder: &str) -> String {
    let Some(os) = fs::os_path(folder) else {
        return String::new();
    };
    let Ok(entries) = std::fs::read_dir(os) else {
        return String::new();
    };

    // Session files, newest first
    let mut files: Vec<(i128, String)> = Vec::new();
    for entry in entries {
        let Ok(entry) = entry else {
            return String::new();
        };
        let name = crate::py::surrogate::from_os(&entry.file_name());
        let path = join(folder, &name);
        if !name.ends_with(".jsonl") || !fs::is_file(&path) {
            continue;
        }
        match fs::stat(&path) {
            Ok(st) => files.push((st.mtime_ns, path)),
            Err(_) => return String::new(),
        }
    }
    files.sort_by(|a, b| b.cmp(a));

    // First cwd in the head of each
    for (_, path) in files.iter().take(3) {
        let Some(head) = read_head(path) else {
            continue;
        };
        let Some(raw) = find_cwd(&head) else { continue };
        let mut quoted = Vec::with_capacity(raw.len() + 2);
        quoted.push(b'"');
        quoted.extend_from_slice(raw);
        quoted.push(b'"');
        if let Ok(value) = from_bytes(&quoted, Decode::Strict)
            && let Some(cwd) = value.as_str()
        {
            return cwd.to_owned();
        }
    }
    String::new()
}

// 앞 32 KB, 그 안에 cwd 가 없고 파일이 더 길면 256 KB 까지
fn read_head(path: &str) -> Option<Vec<u8>> {
    use std::io::Read;
    let mut file = std::fs::File::open(fs::os_path(path)?).ok()?;
    let mut head = Vec::new();
    (&mut file)
        .take(HEAD_FIRST as u64)
        .read_to_end(&mut head)
        .ok()?;
    if find_cwd(&head).is_none() && head.len() == HEAD_FIRST {
        file.take((HEAD_BYTES - HEAD_FIRST) as u64)
            .read_to_end(&mut head)
            .ok()?;
    }
    Some(head)
}

// python _project_dirs: projects/ 아래 폴더(링크는 따라가지 않는다)와 그 mtime_ns, 디렉터리 순서
fn project_dirs(projects: &str) -> Vec<(String, i128)> {
    let mut out = Vec::new();
    let Some(entries) = fs::os_path(projects).and_then(|os| std::fs::read_dir(os).ok()) else {
        return out;
    };

    // 읽기가 중간에 실패하면 그때까지 모은 것
    for entry in entries {
        let Ok(entry) = entry else { break };
        if !entry.file_type().is_ok_and(|t| t.is_dir()) {
            continue;
        }
        if let Ok(meta) = entry.metadata() {
            out.push((
                crate::py::surrogate::from_os(&entry.file_name()),
                mtime_ns(&meta),
            ));
        }
    }
    out
}

#[cfg(unix)]
fn mtime_ns(meta: &std::fs::Metadata) -> i128 {
    use std::os::unix::fs::MetadataExt;
    i128::from(meta.mtime()) * 1_000_000_000 + i128::from(meta.mtime_nsec())
}

#[cfg(not(unix))]
fn mtime_ns(meta: &std::fs::Metadata) -> i128 {
    meta.modified()
        .ok()
        .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
        .map_or(0, |d| d.as_nanos() as i128)
}

// python _folder_repos: folder 가 저장소면(self_ok) 그것, 아니면 바로 아래 자식 저장소들
fn folder_repos(folder: &str, self_ok: bool) -> Vec<String> {
    if self_ok && git_entry(folder).is_some() {
        return repo_root(folder).into_iter().collect();
    }

    // Child folders, links followed
    let mut children = Vec::new();
    let Some(entries) = fs::os_path(folder).and_then(|os| std::fs::read_dir(os).ok()) else {
        return children;
    };
    for entry in entries {
        let Ok(entry) = entry else {
            return Vec::new();
        };
        let path = join(folder, &crate::py::surrogate::from_os(&entry.file_name()));
        if fs::is_dir(&path) {
            children.push(path);
        }
    }

    // Children that are repos or worktrees
    children
        .into_iter()
        .filter_map(|c| match git_entry(&c) {
            Some(GitEntry::Dir) => Some(c),
            Some(GitEntry::File) => fold(&c),
            None => None,
        })
        .collect()
}

/// python `default_exclude()`: 임시 폴더, `~/.cache`, `.claude/worktrees/` 아래.
pub fn default_exclude(env: &Env) -> Result<Vec<String>, Failed> {
    let temp = gettempdir(env).ok_or(Failed("no usable temporary directory"))?;
    Ok(vec![
        temp,
        join(&expanduser("~", env), ".cache"),
        "*/.claude/worktrees/*".to_owned(),
    ])
}

/// python `excluded(root, patterns)`: 경로는 그 아래까지, 글롭(`*?[`)은 경로 전체에 맞춘다.
pub fn excluded(root: &str, patterns: &[String]) -> Result<bool, Failed> {
    for pat in patterns {
        // A glob matches the whole path
        if pat.contains(['*', '?', '[']) {
            let slashed = (root.replace('\\', "/"), pat.replace('\\', "/"));
            let hit = glob(root, pat)? || glob(&slashed.0, &slashed.1)?;
            if hit {
                return Ok(true);
            }
            continue;
        }

        // A path matches itself and what is under it
        let Some(p) = abspath(pat) else {
            return Err(Failed("cannot read the current directory"));
        };
        if root == p || root.starts_with(&format!("{}/", p.trim_end_matches('/'))) {
            return Ok(true);
        }
    }
    Ok(false)
}

fn glob(name: &str, pat: &str) -> Result<bool, Failed> {
    fnmatch(name, pat).map_err(|_| Failed("a glob this port cannot translate"))
}

fn mtime_of(path: &str) -> Value {
    match fs::stat(path) {
        Ok(st) => Value::Int(st.mtime_ns),
        Err(_) => Value::Null,
    }
}

fn str_list(items: &[String]) -> Value {
    Value::List(items.iter().cloned().map(Value::Str).collect())
}

/// python `repos()`(인자 없이): 저장소 루트 절대 경로 목록, 정렬.
pub fn repos(env: &Env, plugin_dir: Option<&Path>) -> Result<Vec<String>, Failed> {
    let opts = options(env, plugin_dir);
    let projects = join(&config_dir(env), "projects");
    let mut folders: Vec<(String, bool)> = split_paths(&opts.extra, env)
        .into_iter()
        .map(|f| (f, true))
        .collect();
    if !opts.workspace.is_empty() {
        folders.push((expanduser(&opts.workspace, env), false));
    }
    let defaults = default_exclude(env)?;

    // Cache hit: the same key and folder times
    let key = cache_key(&projects, &opts, &defaults, &folders);
    let dirs = project_dirs(&projects);
    let path = env
        .get_nonempty("CLAUDE_PLUGIN_DATA")
        .map(|d| join(d, CACHE_FILE))
        .unwrap_or_default();
    let old = read_cache(&path);
    let empty = Dict::new();
    let prev = old
        .as_ref()
        .and_then(|o| o.get("dirs"))
        .and_then(Value::as_dict)
        .unwrap_or(&empty);
    if let Some(old) = &old
        && old.get("key").is_some_and(|k| k.same_content(&key))
        && prev.len() == dirs.len()
        && all_same_times(prev, &dirs)?
    {
        return cached_repos(old.get("repos"));
    }

    // Collect cwd per project folder; an unchanged folder keeps its cached cwd
    let mut seen: Vec<(String, Value)> = Vec::new();
    for (name, m) in &dirs {
        let cwd = match prev.get(name) {
            Some(Value::List(p)) if p.len() == 2 && int_eq(&p[0], *m) => p[1].clone(),
            _ => Value::Str(cwd_of(&join(&projects, name))),
        };
        seen.push((name.clone(), Value::List(vec![Value::Int(*m), cwd])));
    }

    // Roots from sessions and folders, then exclusions
    let mut found = session_roots(&seen)?;
    for (f, self_ok) in &folders {
        found.extend(folder_repos(f, *self_ok).into_iter().map(|r| (r, !self_ok)));
    }
    let out = kept_roots(found, &defaults, &split_paths(&opts.exclude, env))?;

    let data = Dict::from_pairs(vec![
        ("version".into(), Value::Int(CACHE_VERSION)),
        ("key".into(), key),
        ("dirs".into(), Value::Dict(Dict::from_pairs(seen))),
        ("repos".into(), str_list(&out)),
    ]);
    write_cache(&path, &Value::Dict(data))?;
    Ok(out)
}

// python 의 캐시 key dict(키 순서도 같다)
fn cache_key(
    projects: &str,
    opts: &Options,
    defaults: &[String],
    folders: &[(String, bool)],
) -> Value {
    let folders = folders
        .iter()
        .map(|(f, _)| Value::List(vec![Value::Str(f.clone()), mtime_of(f)]))
        .collect();
    Value::Dict(Dict::from_pairs(vec![
        ("projects".into(), Value::Str(projects.to_owned())),
        ("extra".into(), Value::Str(opts.extra.clone())),
        ("exclude".into(), Value::Str(opts.exclude.clone())),
        ("workspace".into(), Value::Str(opts.workspace.clone())),
        ("defaults".into(), str_list(defaults)),
        ("folders".into(), Value::List(folders)),
    ]))
}

// 세션 cwd 의 저장소 루트(자동 출처). 글이 아닌 참인 cwd 는 python 이 isdir 에서 끝나는 자리다
fn session_roots(seen: &[(String, Value)]) -> Result<Vec<(String, bool)>, Failed> {
    let mut found = Vec::new();
    for (_, pair) in seen {
        let Value::List(pair) = pair else { continue };
        match &pair[1] {
            Value::Str(cwd) if !cwd.is_empty() => {
                if fs::is_dir(cwd)
                    && let Some(r) = repo_root(cwd)
                {
                    found.push((r, true));
                }
            }
            v if v.truthy() => return Err(Failed("a cached cwd is not a string")),
            _ => {}
        }
    }
    Ok(found)
}

// 자동 출처에 기본 제외, 같은 경로는 처음 것만, 있는 폴더 가운데 사용자 제외에 걸리지 않는 것, 정렬
fn kept_roots(
    found: Vec<(String, bool)>,
    defaults: &[String],
    pats: &[String],
) -> Result<Vec<String>, Failed> {
    let mut roots: Vec<String> = Vec::new();
    for (r, auto) in found {
        let r = normpath(&r);
        if auto && excluded(&r, defaults)? {
            continue;
        }
        if !roots.contains(&r) {
            roots.push(r);
        }
    }

    let mut out = Vec::new();
    for r in roots {
        if fs::is_dir(&r) && !excluded(&r, pats)? {
            out.push(r);
        }
    }
    out.sort();
    Ok(out)
}

// python `prev.get(n, (None,))[0] == m` 를 모든 폴더에: 앞에서부터, 처음 다른 곳에서 멈춘다
fn all_same_times(prev: &Dict, dirs: &[(String, i128)]) -> Result<bool, Failed> {
    for (name, m) in dirs {
        // 첫 칸이 없는 값은 python 이 예외로 끝나는 자리다
        let same = match prev.get(name) {
            None => false,
            Some(Value::List(items)) => match items.first() {
                Some(first) => int_eq(first, *m),
                None => return Err(Failed("an empty cached folder entry")),
            },
            Some(Value::Str(s)) if !s.is_empty() => false,
            Some(_) => return Err(Failed("a cached folder entry without a first item")),
        };

        if !same {
            return Ok(false);
        }
    }
    Ok(true)
}

// python 의 `v == m`(정수 m): bool 과 float 도 같은 수면 같다
fn int_eq(v: &Value, m: i128) -> bool {
    match v {
        Value::Int(i) => *i == m,
        Value::Bool(b) => i128::from(*b) == m,
        Value::Float(f) => *f == m as f64 && f.fract() == 0.0 && (*f as i128) == m,
        _ => false,
    }
}

// python `[r for r in old.get("repos", []) if isinstance(r, str) and os.path.isdir(r)]`
fn cached_repos(repos: Option<&Value>) -> Result<Vec<String>, Failed> {
    let items: Vec<String> = match repos {
        None => Vec::new(),
        Some(Value::List(items)) => items
            .iter()
            .filter_map(|v| v.as_str().map(str::to_owned))
            .collect(),
        Some(Value::Str(s)) => s.chars().map(String::from).collect(),
        Some(Value::Dict(d)) => d.iter().map(|(k, _)| k.to_owned()).collect(),
        Some(_) => return Err(Failed("cached repos is not iterable")),
    };
    Ok(items.into_iter().filter(|r| fs::is_dir(r)).collect())
}

// 판이 맞는 dict 만(python `_read_cache`)
fn read_cache(path: &str) -> Option<Dict> {
    if path.is_empty() {
        return None;
    }
    let text = fs::read_text(path).ok()?;
    let data = loads(&text).ok()?.into_dict().ok()?;
    matches!(data.get("version"), Some(Value::Int(CACHE_VERSION))).then_some(data)
}

// python _write_cache: 임시 파일에 쓰고 바꿔 단다. 쓰기 실패는 넘기고, 인코딩하지 못하는 글은 python 처럼 실패다
fn write_cache(path: &str, data: &Value) -> Result<(), Failed> {
    if path.is_empty() {
        return Ok(());
    }

    // python json.dump 이 UnicodeEncodeError 로 끝나는 글
    let text = dumps(data, EnsureAscii::No, None);
    if text.chars().any(|c| unit_of(c).is_some()) {
        return Err(Failed("a path python cannot encode as UTF-8"));
    }

    // Write a temporary file, then rename it over
    let tmp = format!("{path}.{}.tmp", std::process::id());
    let dir = crate::py::path::dirname(path);
    let written = (|| -> Result<(), FsError> {
        let os_dir = fs::os_path(if dir.is_empty() { "." } else { dir }).ok_or(FsError::Value)?;
        std::fs::create_dir_all(os_dir).map_err(|e| FsError::Os(e.kind()))?;
        fs::write_text(&tmp, &text)?;
        let (from, to) = (fs::os_path(&tmp), fs::os_path(path));
        std::fs::rename(from.ok_or(FsError::Value)?, to.ok_or(FsError::Value)?)
            .map_err(|e| FsError::Os(e.kind()))
    })();

    // 실패하면 임시 파일을 지운다
    if written.is_err()
        && let Some(os) = fs::os_path(&tmp)
    {
        let _ = std::fs::remove_file(os);
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    /// cwd 찾기는 python 바이트 정규식처럼 escape 를 건너뛰고, 닫히지 않은 값은 다음 자리를 본다.
    #[test]
    fn finds_the_first_cwd_like_the_regex() {
        // Escaped quotes stay inside the value
        assert_eq!(
            find_cwd(br#"{"a":1,"cwd" : "C:\\x\"y","b":2}"#),
            Some(&br#"C:\\x\"y"#[..])
        );

        // A value cut by a backslash-newline fails, a later key can still match
        assert_eq!(
            find_cwd(b"\"cwd\":\"a\\\n\" \"cwd\":\"b\""),
            Some(&b"b"[..])
        );
        assert_eq!(find_cwd(b"\"cwd\": 5"), None);
    }

    /// 경로 제외는 그 아래까지, 글롭은 경로 전체다.
    #[test]
    fn excludes_paths_and_globs() {
        let pats = vec!["/tmp".to_owned(), "*/.claude/worktrees/*".to_owned()];
        assert_eq!(excluded("/tmp/x", &pats), Ok(true));

        // A sibling with the same prefix is not under /tmp
        assert_eq!(excluded("/tmpx", &pats), Ok(false));
        assert_eq!(excluded("/r/.claude/worktrees/w", &pats), Ok(true));
    }

    /// worktree 의 `.git` 파일은 본 저장소로 합친다.
    #[test]
    fn folds_worktrees_into_the_main_repo() {
        let base = std::env::temp_dir().join(format!("hh-known-{}", std::process::id()));
        let base = base.to_str().unwrap().to_owned();
        let main = join(&base, "main");
        let wt = join(&base, "wt");
        std::fs::create_dir_all(join(&main, ".git/worktrees/w1")).unwrap();
        std::fs::create_dir_all(&wt).unwrap();
        std::fs::write(
            join(&wt, ".git"),
            format!("gitdir: {main}/.git/worktrees/w1\n"),
        )
        .unwrap();

        // The worktree folds to main, a plain repo is itself
        assert_eq!(repo_root(&join(&wt, "src")).as_deref(), Some(main.as_str()));
        assert_eq!(repo_root(&main).as_deref(), Some(main.as_str()));
        std::fs::remove_dir_all(&base).unwrap();
    }
}
