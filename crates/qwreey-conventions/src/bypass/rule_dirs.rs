//! 셸 명령이 건드리는 파일에 맞는 rule 찾기(python `bash-bypass-reminder.py` 의 `plugin_rule_dirs`, `load_rules`, `describe`).
//!
//! 프로젝트와 사용자의 `.claude/rules`, 이 플러그인과 설치된 플러그인의 `rules/`(도메인 팩 제외), 그리고 프로젝트 `coderag.toml`
//! 의 `[[packs]]` 에 적힌 팩의 `rules/` 를 본다. 팩 rule 은 coderag 가 목록에 있을 때만 넣기 때문이다.

use harness_hook::Env;
use harness_hook::py::fs;
use harness_hook::py::path::{expanduser, join, relpath};
use harness_hook::py::re::Regex as PyRegex;
use harness_hook::py::surrogate::from_os;
use harness_hook::py::toml::{self, Item, Table};

use crate::context::Context;
use crate::halt::{Halt, Result};
use crate::plugins::{config_dir, installed_roots};
use crate::pyops::str_order;
use crate::rules::parse_rule;

/// 이 플러그인의 이름(python 은 글로 적어 둔다: 설치본이 이 폴더와 이름이 같다).
const OWN: &str = "qwreey-conventions";

/// rule 폴더와 그 주인 플러그인, 넣은 순서(python dict).
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct RuleDirs(Vec<(String, String)>);

impl RuleDirs {
    // python `out[dir] = name`: 있던 폴더는 자리를 지키고 이름만 바뀐다
    fn set(&mut self, dir: String, name: String) {
        match self.0.iter_mut().find(|(d, _)| *d == dir) {
            Some(slot) => slot.1 = name,
            None => self.0.push((dir, name)),
        }
    }

    /// 폴더들, 넣은 순서로.
    pub fn dirs(&self) -> impl Iterator<Item = &str> {
        self.0.iter().map(|(d, _)| d.as_str())
    }
}

/// python `plugin_rule_dirs(proj)`: 이 플러그인 것, 설치된 플러그인의 `rules/`(도메인 팩 제외), 프로젝트가 목록에 적은 팩의 `rules/`.
///
/// 이 플러그인은 지금 도는 사본이 이긴다(설치된 옛 버전과 겹쳐 나오지 않게).
pub fn plugin_rule_dirs(ctx: &Context, own_rules: &str, proj: &str) -> Result<RuleDirs> {
    let mut out = RuleDirs(vec![(own_rules.to_owned(), OWN.to_owned())]);
    for p in installed_roots(&config_dir(&ctx.env))? {
        if out.0.iter().any(|(_, n)| *n == p.name) || fs::is_file(&join(&p.root, "coderag.toml")) {
            continue;
        }
        out.set(join(&p.root, "rules"), p.name);
    }
    if !proj.is_empty() {
        for (dir, name) in listed_pack_dirs(&ctx.env, proj)? {
            out.set(dir, name);
        }
    }
    Ok(out)
}

// python _read_toml(path): 없거나 깨진 설정은 빈 표다
fn read_toml(path: &str) -> Table {
    fs::read_bytes(path)
        .ok()
        .and_then(|b| toml::loads_bytes(&b).ok())
        .unwrap_or_default()
}

// python `[p for p in doc.get("packs") or [] if isinstance(p, dict)]`. 돌 수 없는 참값(수, 날짜)은 TypeError
fn packs(doc: &Table) -> Result<Vec<&Table>> {
    match doc.get("packs") {
        Some(Item::Array(items)) => Ok(items.iter().filter_map(Item::as_table).collect()),
        Some(Item::Table(_) | Item::Str(_)) | None => Ok(Vec::new()),
        Some(v) if !v.truthy() => Ok(Vec::new()),
        Some(_) => Err(Halt::PyError("iterating packs that are not a list")),
    }
}

// 목록이나 표는 python dict 키가 될 수 없다(TypeError)
fn hashable(v: Option<&Item>) -> Result<()> {
    match v {
        Some(Item::Array(_) | Item::Table(_)) => Err(Halt::PyError("an unhashable pack name")),
        _ => Ok(()),
    }
}

/// python `_listed_pack_dirs(proj)`: (팩 rules 폴더, 팩 이름). 경로는 목록의 `path`, 없으면 coderag 사용자 설정의 같은 이름 팩.
fn listed_pack_dirs(env: &Env, proj: &str) -> Result<Vec<(String, String)>> {
    let project = read_toml(&join(proj, "coderag.toml"));
    let listed = packs(&project)?;
    if listed.is_empty() {
        return Ok(Vec::new());
    }

    // The user's registry: the last path of each name
    let home = match env.get_nonempty("CODERAG_HOME") {
        Some(h) => h.to_owned(),
        None => join(&expanduser("~", env), ".coderag"),
    };
    let user = read_toml(&join(&home, "coderag.toml"));
    let mut registry: Vec<(&str, Option<&Item>)> = Vec::new();
    for p in packs(&user)? {
        hashable(p.get("name"))?;
        if let Some(name) = p.get("name").and_then(Item::as_str) {
            registry.retain(|(n, _)| *n != name);
            registry.push((name, p.get("path")));
        }
    }

    // Each listed pack with a path and a name
    let mut out = Vec::new();
    for p in listed {
        let path = match p.get("path") {
            Some(v) if v.truthy() => Some(v),
            _ => {
                hashable(p.get("name"))?;
                let name = p.get("name").and_then(Item::as_str);
                registry
                    .iter()
                    .find(|(n, _)| Some(*n) == name)
                    .and_then(|(_, v)| *v)
            }
        };
        if let (Some(Item::Str(path)), Some(Item::Str(name))) = (path, p.get("name")) {
            out.push((join(path, "rules"), name.clone()));
        }
    }
    Ok(out)
}

/// rule 파일 하나: 경로와 `paths` 정규식.
pub struct FoundRule {
    pub path: String,
    pub regexes: Vec<PyRegex>,
}

/// python `load_rules(dirs)`: 폴더마다 아래로 걸으며 `*.md` 를 이름순으로. 꺼진 rule(`switch`)은 주입도 안 되므로 뺀다.
pub fn load_rules(ctx: &Context, dirs: &[String]) -> Result<Vec<FoundRule>> {
    let mut rules = Vec::new();
    for d in dirs {
        if !fs::is_dir(d) {
            continue;
        }
        for (root, mut files) in walk(d) {
            files.sort_by(|a, b| str_order(a, b));
            for f in files.iter().filter(|f| f.ends_with(".md")) {
                let path = join(&root, f);
                if let Some(text) = parse_rule(&path)?
                    && text.switch_on(ctx)
                {
                    rules.push(FoundRule {
                        regexes: text.compile()?,
                        path,
                    });
                }
            }
        }
    }
    Ok(rules)
}

// python os.walk(top): 위에서부터 (폴더, 폴더가 아닌 이름들). 폴더 링크는 목록에 들되 따라가지 않고, 읽지 못한 폴더는 건너뛴다
fn walk(top: &str) -> Vec<(String, Vec<String>)> {
    let mut out = Vec::new();
    let mut stack = vec![top.to_owned()];
    while let Some(dir) = stack.pop() {
        let Some(entries) = fs::os_path(&dir).and_then(|os| std::fs::read_dir(os).ok()) else {
            continue;
        };
        let (mut dirs, mut files) = (Vec::new(), Vec::new());
        let mut failed = false;
        for entry in entries {
            let Ok(entry) = entry else {
                failed = true;
                break;
            };
            let name = from_os(&entry.file_name());
            let is_dir = std::fs::metadata(entry.path()).is_ok_and(|m| m.is_dir());
            if is_dir { &mut dirs } else { &mut files }.push(name);
        }
        if failed {
            continue;
        }

        // Children in listing order, links not followed
        for name in dirs.iter().rev() {
            let path = join(&dir, name);
            let is_link = fs::os_path(&path)
                .and_then(|os| std::fs::symlink_metadata(os).ok())
                .is_some_and(|m| m.file_type().is_symlink());
            if !is_link {
                stack.push(path);
            }
        }
        out.push((dir, files));
    }
    out
}

/// python `describe(path, plugin_dirs, proj)`: 플러그인 rule 은 `이름 (플러그인 rule: 경로)`, 아니면 프로젝트 기준이나 `~` 경로.
pub fn describe(path: &str, dirs: &RuleDirs, proj: &str, env: &Env) -> String {
    for (d, plugin) in &dirs.0 {
        if let Some(rest) = path.strip_prefix(&format!("{d}/")) {
            let name: String = {
                let chars: Vec<char> = rest.chars().collect();
                chars[..chars.len().saturating_sub(3)].iter().collect()
            };
            return format!("{name} ({plugin} rule: {path})");
        }
    }
    if path.starts_with(proj) {
        return relpath(path, proj).unwrap_or_else(|| path.to_owned());
    }
    path.replace(&expanduser("~", env), "~")
}
