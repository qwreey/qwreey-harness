//! harness.env 설정 층(python `home/.claude/lib/harness_env.py` 의 `load_layers`).
//!
//! 키마다 합치고 번호가 큰 층이 이긴다. 높은 층에 키가 있으면 빈 값이어도 그 값이다.
//! 1. 기본값: [`DEFAULTS`] 와 호출자 기본값(값의 `~`, `$NAME` 은 여기서 푼다)
//! 2. 사용자: `$HARNESS_ENV`, 없으면 호출자 후보, 없으면 `<설정 디렉터리>/harness.env`
//! 3. 플러그인 옵션: settings.json 의 `pluginConfigs` ([`options`])
//! 4. 저장소 공유: `<project>/.claude/harness.env`
//! 5. 저장소 개인: `<project>/.claude/harness.local.env`
//! 6. 환경 변수: 1~5 층에 나온 키만 덮는다(어느 층에도 없는 키는 환경 변수만으로 생기지 않는다).
//!
//! 4, 5 층은 사용자 전용 키(실행 경로, 기기 고유값, 보안 게이트)를 바꾸지 못한다: [`USER_ONLY`],
//! [`RETIRED_USER_ONLY`], [`LEGACY_USER_ONLY`] 와 호출자 `user_only`. 클론한 저장소가 커밋한 파일로
//! 남의 하네스를 바꾸면 안 되기 때문이다. 저장소 층이 값을 더 엄하게만 바꾸게 하는 규칙(문턱 등)은
//! 그 키를 읽는 플러그인이 [`Project::Skip`] 으로 사용자 쪽 값만 따로 읽어 비교한다.

pub mod envfile;
pub mod options;

use std::collections::BTreeSet;
use std::fs;
use std::path::{Path, PathBuf};

pub use envfile::Values;

use crate::env::Env;
use crate::py::path::{expanduser, pathlib, which};
use crate::py::text::{split_whitespace, strip};

/// 여러 플러그인이 읽는 키의 기본값. 한 플러그인만 읽는 키는 그 플러그인이 [`LoadRequest::defaults`] 로 넘긴다.
pub const DEFAULTS: &[(&str, &str)] = &[
    ("HARNESS_TOOL_INSTALLS", "~/.local/share/mise/installs"),
    ("HARNESS_HEAVY_WRAP", "auto"),
    ("HARNESS_TOOLKITS", ""),
    ("HARNESS_DELEGATE_UIDS", "61100-61115"),
    ("HARNESS_CODERAG", "coderag"),
];

/// 저장소 층이 바꾸지 못하는 키 가운데 여러 플러그인이 읽는 것.
pub const USER_ONLY: &[&str] = &[
    "HARNESS_TOOL_INSTALLS",
    "HARNESS_HEAVY_WRAP",
    "HARNESS_DELEGATE_UIDS",
    "HARNESS_CODERAG",
];

/// 기본값 없는 옛 위치 키. 환경 변수로 주면 결과에 있고, 저장소 층은 계속 막는다.
pub const RETIRED_USER_ONLY: &[&str] = &["HARNESS_WORKSPACE", "HARNESS_DOCTOR_ROOT"];

/// user_only 를 넘기지 않던 옛 플러그인 대신 막아 두는 키.
pub const LEGACY_USER_ONLY: &[&str] = &[
    "HARNESS_DELEGATE_REGISTRY",
    "HARNESS_AGENT_PUSH",
    "HARNESS_LUAU_KB",
    "HARNESS_ROBLOX_DOCS_CACHE",
    "HARNESS_WORKSPACE_GATE",
    "SESSION_LOG_HOME",
    "SESSION_LOG_CLAUDE",
    "HARNESS_DELEGATE_AGY_BIN",
    "HARNESS_DELEGATE_CODEX_BIN",
    "HARNESS_DELEGATE_AGY_HOME",
    "HARNESS_DELEGATE_CODEX_HOME",
    "HARNESS_DELEGATE_AGY_WORKTREE",
    "HARNESS_DELEGATE_AGY_UNISOLATED",
    "HARNESS_DELEGATE_CODEX_SANDBOX",
    "HARNESS_DELEGATE_KEEP_ENV",
    "HARNESS_DELEGATE_STATE",
    "HARNESS_DELEGATE_MAX_CONCURRENT",
    "HARNESS_DELEGATE_RUNS_DAYS",
];

/// 저장소 층 파일(뒤가 이긴다).
pub const PROJECT_FILES: &[&str] = &[".claude/harness.env", ".claude/harness.local.env"];

/// 저장소 층을 어디서 읽을지(python `load_layers(project=...)`).
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub enum Project {
    /// `$CLAUDE_PROJECT_DIR`, 비었으면 저장소 층 없음(python `project=None`).
    #[default]
    FromEnv,
    /// 이 디렉터리(python `Path` 값).
    Dir(String),
    /// 저장소 층 없음(python `project=""`). 사용자 쪽 값만 볼 때 쓴다.
    Skip,
}

/// 저장소 층의 루트: `$CLAUDE_PROJECT_DIR`, 없으면 훅 입력의 `cwd`(python `project_dir`).
pub fn project_dir(env: &Env, cwd: Option<&str>) -> Project {
    match env
        .get_nonempty("CLAUDE_PROJECT_DIR")
        .or(cwd.filter(|c| !c.is_empty()))
    {
        Some(dir) => Project::Dir(dir.to_owned()),
        None => Project::FromEnv,
    }
}

/// [`load_layers`] 에 넘길 것. python `load_layers` 의 인자와 같다.
#[derive(Clone, Debug, Default)]
pub struct LoadRequest<'a> {
    pub project: Project,
    /// 사용자 층 후보. `None` 이면 `<설정 디렉터리>/harness.env`.
    pub candidates: Option<Vec<PathBuf>>,
    /// 호출자 키의 기본값.
    pub defaults: &'a [(&'a str, &'a str)],
    /// 저장소 층이 바꾸지 못할 호출자 키([`USER_ONLY`] 등에 더해진다).
    pub user_only: &'a [&'a str],
    /// 자기 플러그인 말고 옵션을 더 읽을 플러그인과 그 키(환경 변수 이름). 순서대로 얹는다.
    pub options: &'a [(&'a str, &'a [&'a str])],
    /// 플러그인 이름을 찾기 시작할 절대 디렉터리(python 의 `__file__` 자리. 바이너리는 실행 파일의 디렉터리).
    /// `None` 이면 자기 플러그인의 옵션 층이 없다.
    pub plugin_dir: Option<&'a Path>,
}

/// 모든 층을 합친 값과, 무엇을 읽었는지.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct Layers {
    /// 키 -> 값.
    pub values: Values,
    /// 읽은 사용자 층 파일(python `_file`).
    pub user_file: Option<PathBuf>,
    /// 읽은 파일 전부, 낮은 층부터(python `_files`).
    pub files: Vec<PathBuf>,
    /// 옵션을 읽은 플러그인 id(`이름@마켓`, python `_options`).
    pub option_ids: Vec<String>,
}

impl Layers {
    /// 키의 값.
    pub fn get(&self, key: &str) -> Option<&str> {
        self.values.get(key).map(String::as_str)
    }
}

/// 홈 디렉터리를 알 수 없다(python `Path.home()` 의 RuntimeError). python 훅은 이때 설정 전체를 `{}` 로 본다.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct HomeUnknown;

impl std::fmt::Display for HomeUnknown {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str("could not determine home directory")
    }
}

impl std::error::Error for HomeUnknown {}

/// 설정 디렉터리: `$CLAUDE_CONFIG_DIR`, 없으면 `~/.claude`.
pub fn config_dir(env: &Env) -> Result<PathBuf, HomeUnknown> {
    if let Some(dir) = env.get_nonempty("CLAUDE_CONFIG_DIR") {
        return Ok(pathlib(dir));
    }
    let home = expanduser("~", env);
    if home == "~" {
        return Err(HomeUnknown);
    }
    Ok(pathlib(&format!("{home}/.claude")))
}

/// 사용자 층 파일: `$HARNESS_ENV`, 없으면 `candidates` 가운데 처음 있는 파일.
pub fn find_file(env: &Env, candidates: &[PathBuf]) -> Option<PathBuf> {
    let from_env = env.get_nonempty("HARNESS_ENV").map(str::to_owned);
    let listed = candidates.iter().map(|c| c.to_string_lossy().into_owned());
    from_env
        .into_iter()
        .chain(listed)
        .filter(|p| !p.is_empty())
        .map(|p| pathlib(&p))
        .find(|p| p.is_file())
}

/// (사용자 층 파일, 저장소 층 파일들 낮은 층부터). python `layer_files`.
///
/// 저장소가 설정 디렉터리의 부모(`~`)라 저장소 층이 사용자 파일과 같은 파일이면 두 번 읽지 않는다.
pub fn layer_files(
    env: &Env,
    project: &Project,
    candidates: Option<&[PathBuf]>,
) -> Result<(Option<PathBuf>, Vec<PathBuf>), HomeUnknown> {
    // python 은 HARNESS_ENV 가 있어도 기본 후보를 먼저 만든다(홈을 모르면 여기서 실패)
    let default_candidates;
    let candidates = match candidates {
        Some(list) => list,
        None => {
            default_candidates = [config_dir(env)?.join("harness.env")];
            &default_candidates[..]
        }
    };
    let user = find_file(env, candidates);

    let project = match project {
        Project::FromEnv => env.get_nonempty("CLAUDE_PROJECT_DIR"),
        Project::Dir(dir) => Some(dir.as_str()),
        Project::Skip => None,
    };
    let user_real = user.as_ref().and_then(|u| fs::canonicalize(u).ok());
    let repo = project
        .into_iter()
        .flat_map(|dir| PROJECT_FILES.iter().map(move |rel| project_file(dir, rel)))
        .filter(|p| p.is_file() && (user_real.is_none() || fs::canonicalize(p).ok() != user_real))
        .collect();
    Ok((user, repo))
}

// python Path(project) / rel. 빈 디렉터리는 Path("") 처럼 현재 디렉터리다
fn project_file(dir: &str, rel: &str) -> PathBuf {
    if dir.is_empty() {
        pathlib(rel)
    } else {
        pathlib(&format!("{dir}/{rel}"))
    }
}

/// 모든 층을 합친다(python `load_layers`).
pub fn load_layers(env: &Env, req: &LoadRequest<'_>) -> Result<Layers, HomeUnknown> {
    // 1. 기본값
    let mut values = base_values(env, req.defaults);
    let (user, repo) = layer_files(env, &req.project, req.candidates.as_deref())?;

    // 2. 사용자 층
    let user = user.filter(|file| read_layer(&mut values, file, env, &BTreeSet::new()));

    // 3. 플러그인 옵션
    let option_ids = options_layer(&mut values, env, req)?;

    // 4, 5. 저장소 층은 사용자 전용 키를 건너뛴다
    let skip: BTreeSet<&str> = USER_ONLY
        .iter()
        .chain(RETIRED_USER_ONLY)
        .chain(LEGACY_USER_ONLY)
        .chain(req.user_only)
        .copied()
        .collect();
    let mut files: Vec<PathBuf> = user.iter().cloned().collect();
    for file in repo {
        if read_layer(&mut values, &file, env, &skip) {
            files.push(file);
        }
    }

    Ok(Layers {
        values,
        user_file: user,
        files,
        option_ids,
    })
}

fn base_values(env: &Env, defaults: &[(&str, &str)]) -> Values {
    let empty = Values::new();
    let mut values: Values = DEFAULTS
        .iter()
        .chain(defaults)
        .map(|(k, v)| ((*k).to_owned(), envfile::expand(v, &empty, env)))
        .collect();

    // 옛 위치 키는 기본값이 없어도 환경 변수로 준 값은 결과에 있어야 한다
    let keys: Vec<String> = values
        .keys()
        .cloned()
        .chain(RETIRED_USER_ONLY.iter().map(|k| (*k).to_owned()))
        .collect();
    for key in keys {
        if let Some(v) = env.get(&key) {
            values.insert(key, v.to_owned());
        }
    }
    values
}

// 파일 하나를 values 에 얹는다. 읽지 못하거나 UTF-8 이 아니면 false(그 층은 없는 것)
fn read_layer(values: &mut Values, file: &Path, env: &Env, skip: &BTreeSet<&str>) -> bool {
    let Some(text) = fs::read(file)
        .ok()
        .and_then(|bytes| String::from_utf8(bytes).ok())
    else {
        return false;
    };
    for (key, value) in envfile::parse(&text, values, env) {
        if !skip.contains(key.as_str()) {
            values.insert(key, value);
        }
    }
    true
}

// 플러그인 옵션 층을 얹고 읽은 플러그인 id 들을 돌려준다. 자기 플러그인이 넘긴 목록보다 나중이라 겹치면 이긴다
fn options_layer(
    values: &mut Values,
    env: &Env,
    req: &LoadRequest<'_>,
) -> Result<Vec<String>, HomeUnknown> {
    let own = req.plugin_dir.and_then(options::plugin_manifest);
    let own_name = own.as_ref().map(|m| m.name.as_str());
    let extra_keys = |name: &str| -> BTreeSet<String> {
        req.options
            .iter()
            .find(|(n, _)| *n == name)
            .map(|(_, keys)| keys.iter().map(|k| (*k).to_owned()).collect())
            .unwrap_or_default()
    };

    // 넘긴 목록(자기 플러그인 빼고), 그다음 자기 플러그인(선언된 키와 넘긴 키를 합쳐 한 번)
    let mut want: Vec<(String, BTreeSet<String>)> = req
        .options
        .iter()
        .filter(|(name, _)| Some(*name) != own_name)
        .map(|(name, keys)| {
            (
                (*name).to_owned(),
                keys.iter().map(|k| (*k).to_owned()).collect(),
            )
        })
        .collect();
    if let Some(own) = &own {
        let keys: BTreeSet<String> = own
            .option_keys
            .union(&extra_keys(&own.name))
            .cloned()
            .collect();
        if !keys.is_empty() {
            want.push((own.name.clone(), keys));
        }
    }

    let mut ids = Vec::new();
    for (name, keys) in want {
        if keys.is_empty() {
            continue;
        }
        let (got, pid) = options::plugin_options(env, &name, &keys, &config_dir(env)?);
        if !pid.is_empty() {
            ids.push(pid);
        }
        for (key, value) in got {
            let value = env.get(&key).map_or(value, str::to_owned);
            values.insert(key, value);
        }
    }
    Ok(ids)
}

/// 무거운 실행 래퍼 argv(python `heavy_wrap`). 끔이거나 실행 파일이 없으면 빈 목록.
///
/// `HARNESS_HEAVY_WRAP` 이 없거나 `auto` 면 `choom` 이 PATH 에 있을 때 `choom -n 1000 --`.
pub fn heavy_wrap(layers: &Layers, env: &Env) -> Vec<String> {
    let mut wrap = strip(layers.get("HARNESS_HEAVY_WRAP").unwrap_or("auto")).to_owned();
    if wrap == "auto" {
        wrap = if which("choom", env).is_some() {
            "choom -n 1000 --".to_owned()
        } else {
            String::new()
        };
    }
    let argv: Vec<String> = split_whitespace(&wrap).map(str::to_owned).collect();
    match argv.first() {
        Some(program) if which(program, env).is_some() => argv,
        _ => Vec::new(),
    }
}
