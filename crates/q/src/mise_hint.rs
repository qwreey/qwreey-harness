//! `hook mise-hint`: Bash 출력에 mise 의 "No version is set for shim: <이름>" 이 있으면 설치된 실제 실행 파일 경로를 info 로
//! 알린다(python `scripts/mise-hint.py`, PostToolUseFailure:Bash).
//!
//! - 설치 폴더: harness.env 층의 `HARNESS_TOOL_INSTALLS`(기본 `~/.local/share/mise/installs`), 비면 `$MISE_DATA_DIR/installs`.
//! - `<설치 폴더>/<도구>/<버전>/` 바로 아래나 `bin/` 에 shim 과 같은 이름이 있으면 후보다. 별칭 버전 폴더(심볼릭 링크)는 건너뛴다.
//!   오류가 제안한 `mise use -g <도구>@<버전>` 의 도구와 버전을 앞에 둔다. 최대 셋.
//! - 어떤 실패든 아무것도 내지 않는다.

use std::sync::LazyLock;

use harness_hook::HookEnv;
use harness_hook::py::fs::{is_dir, is_file, listdir, os_path};
use harness_hook::py::json::{EnsureAscii, dumps_dict};
use harness_hook::py::path::{expanduser, join};
use harness_hook::py::surrogate::unit_of;
use harness_hook::py::value::{Dict, Value};
use harness_hook::rx::Regex;
use harness_hook::settings::{self, LoadRequest};

use crate::stop::{Result, Stop};

static SHIM: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"No version is set for shim: ([A-Za-z0-9._+-]+)"));
static SUGGEST: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r"mise use -g ([A-Za-z0-9._:/+-]+)@([A-Za-z0-9._+-]+)"));
/// shim 이름 뒤에 붙여 찾는 확장자(Windows 는 `.exe`, `.cmd`).
const EXTS: &[&str] = &["", ".exe", ".cmd"];
const MAX_PATHS: usize = 3;

/// 오류가 제안한 (도구, 버전).
struct Prefer {
    tool: String,
    version: String,
}

/// 훅 한 번. 낼 JSON 글(python `sys.stdout.write(json.dumps(out))`, 끝 줄바꿈 없음) 또는 `None`.
pub fn run(hook: &HookEnv, input: &Dict) -> Result<Option<String>> {
    match input.get("tool_name") {
        None | Some(Value::Null) => {}
        Some(Value::Str(name)) if name == "Bash" => {}
        Some(_) => return Ok(None),
    }

    // Only the mise shim error
    let text = output_text(input);
    let Some(shim) = SHIM
        .search(&text)
        .and_then(|m| m.text(&text, 1).map(str::to_owned))
    else {
        return Ok(None);
    };
    let prefer = SUGGEST.search(&text).map(|m| Prefer {
        tool: m.text(&text, 1).unwrap_or("").to_owned(),
        version: m.text(&text, 2).unwrap_or("").to_owned(),
    });

    // Installed copies and the message
    let paths = match installs_dir(hook, input.get("cwd")) {
        Some(root) => find_binaries(&root, &shim, prefer.as_ref())?,
        None => Vec::new(),
    };
    let attr = hook.nonce_attr(input.get("session_id")).unwrap_or_default();
    let event = match input.get("hook_event_name") {
        Some(v) if v.truthy() => v.clone(),
        _ => Value::Str("PostToolUse".to_owned()),
    };
    let inner = Dict::from_pairs(vec![
        ("hookEventName".to_owned(), event),
        (
            "additionalContext".to_owned(),
            Value::Str(message(&shim, &paths, prefer.as_ref(), &attr)),
        ),
    ]);
    let outer = Dict::from_pairs(vec![("hookSpecificOutput".to_owned(), Value::Dict(inner))]);
    Ok(Some(dumps_dict(&outer, EnsureAscii::Yes, None)))
}

/// python `output_text`: 훅 입력에서 명령 출력 글.
///
/// PostToolUseFailure 의 error, tool_response 의 stdout, stderr, output(dict 순서), 또는 글인 응답을 줄바꿈으로 잇는다.
fn output_text(input: &Dict) -> String {
    let mut parts: Vec<&str> = Vec::new();
    if let Some(Value::Str(err)) = input.get("error") {
        parts.push(err);
    }
    match input.get("tool_response") {
        Some(Value::Dict(resp)) => parts.extend(
            resp.iter()
                .filter(|(k, _)| matches!(*k, "stdout" | "stderr" | "output"))
                .filter_map(|(_, v)| v.as_str()),
        ),
        Some(Value::Str(resp)) => parts.push(resp),
        _ => {}
    }
    parts.join("\n")
}

/// python `installs_dir(cwd)`: mise 설치 폴더, 없으면 `None`. 설정 층을 읽지 못하면 그 층은 빈 값이다.
fn installs_dir(hook: &HookEnv, cwd: Option<&Value>) -> Option<String> {
    let mut path = layered_installs(hook, cwd).unwrap_or_default();
    if path.is_empty()
        && let Some(data_dir) = hook.var("MISE_DATA_DIR").filter(|d| !d.is_empty())
    {
        path = join(&data_dir, "installs");
    }
    if path.is_empty() {
        return None;
    }
    let path = expanduser(&path, &hook.env);
    is_dir(&path).then_some(path)
}

// harness.env 층의 HARNESS_TOOL_INSTALLS(python load_env(cwd), 예외면 None)
fn layered_installs(hook: &HookEnv, cwd: Option<&Value>) -> Option<String> {
    let request = LoadRequest {
        project: hook.project(cwd).ok()?,
        plugin_dir: hook.exe_dir.as_deref(),
        ..LoadRequest::default()
    };
    let layers = settings::load_layers(&hook.env, &request).ok()?;
    layers.get("HARNESS_TOOL_INSTALLS").map(str::to_owned)
}

/// python `find_binaries(root, shim, prefer)`: 제안된 (도구 꼬리, 버전)이 먼저, 그다음 이름순, 최대 [`MAX_PATHS`] 개.
///
/// 폴더를 읽지 못하면 python 은 예외로 끝나 아무것도 내지 않는다.
fn find_binaries(root: &str, shim: &str, prefer: Option<&Prefer>) -> Result<Vec<String>> {
    let unreadable = |_| Stop::Raises("os.listdir failed");
    let mut found: Vec<(String, String, String)> = Vec::new();
    for tool in sorted(listdir(root).map_err(unreadable)?) {
        let tool_dir = join(root, &tool);
        if !is_dir(&tool_dir) {
            continue;
        }

        // Newest version name first, aliases (symlinks) skipped
        let mut versions = sorted(listdir(&tool_dir).map_err(unreadable)?);
        versions.reverse();
        for version in versions {
            let version_dir = join(&tool_dir, &version);
            if is_link(&version_dir) || !is_dir(&version_dir) {
                continue;
            }
            if let Some(hit) = binary_in(&version_dir, shim) {
                found.push((tool.clone(), version, hit));
            }
        }
    }

    // Suggested tool and version first
    found.sort_by_key(|(tool, version, _)| rank(tool, version, prefer));
    Ok(found
        .into_iter()
        .take(MAX_PATHS)
        .map(|(_, _, path)| path)
        .collect())
}

// <버전 폴더>/<shim> 또는 bin/<shim>(확장자 차례)
fn binary_in(version_dir: &str, shim: &str) -> Option<String> {
    ["", "bin"].iter().find_map(|sub| {
        let dir = if sub.is_empty() {
            version_dir.to_owned()
        } else {
            join(version_dir, sub)
        };
        EXTS.iter()
            .map(|ext| join(&dir, &format!("{shim}{ext}")))
            .find(|p| is_file(p))
    })
}

fn rank(tool: &str, version: &str, prefer: Option<&Prefer>) -> (u8, u8) {
    let Some(prefer) = prefer else {
        return (1, 1);
    };
    let want_tool = tool_tail(&prefer.tool);
    (
        u8::from(!tool.to_lowercase().ends_with(&want_tool)),
        u8::from(version != prefer.version),
    )
}

// python re.sub(r"[^A-Za-z0-9]+", "-", name).strip("-").lower()
fn tool_tail(name: &str) -> String {
    let mut out = String::new();
    let mut in_gap = false;
    for c in name.chars() {
        if c.is_ascii_alphanumeric() {
            out.push(c.to_ascii_lowercase());
            in_gap = false;
        } else if !in_gap {
            out.push('-');
            in_gap = true;
        }
    }
    out.trim_matches('-').to_owned()
}

// python sorted(names): 코드 포인트 순서(서로게이트 자리표는 python 의 서로게이트 자리)
fn sorted(mut names: Vec<String>) -> Vec<String> {
    let key = |c: char| unit_of(c).unwrap_or(u32::from(c));
    names.sort_by(|a, b| a.chars().map(key).cmp(b.chars().map(key)));
    names
}

// python os.path.islink
fn is_link(path: &str) -> bool {
    os_path(path)
        .and_then(|p| std::fs::symlink_metadata(p).ok())
        .is_some_and(|m| m.file_type().is_symlink())
}

/// python `message`: info 태그 하나.
fn message(shim: &str, paths: &[String], prefer: Option<&Prefer>, attr: &str) -> String {
    let mut lines = vec![
        format!("<harness-hook name=\"mise-hint\" level=\"info\"{attr}>"),
        format!(
            "mise found no version for the shim `{shim}` here (no mise.toml or global default pins it)."
        ),
    ];

    // Where the installed copies are, or that there are none
    if paths.is_empty() {
        lines.push("No installed copy was found under the mise installs folder; `mise install` may be needed.".to_owned());
    } else {
        let listed: Vec<String> = paths.iter().map(|p| format!("`{p}`")).collect();
        lines.push(format!("Installed copies: {}.", listed.join(", ")));
        let exec = match prefer {
            Some(p) => format!(", or `mise exec {}@{} -- {shim} ...`.", p.tool, p.version),
            None => ".".to_owned(),
        };
        lines.push(format!(
            "Consider calling one of those paths directly{exec}"
        ));
    }

    lines.push(
        "`mise use -g` changes the user's global tool versions; ask before running it.".to_owned(),
    );
    lines.push("</harness-hook>".to_owned());
    lines.join("\n")
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 도구 이름의 꼬리는 영숫자 아닌 조각을 `-` 하나로 바꾸고 양끝 `-` 를 뗀 소문자다.
    #[test]
    fn tool_tail_like_python() {
        assert_eq!(
            tool_tail("aqua:BurntSushi/ripgrep"),
            "aqua-burntsushi-ripgrep"
        );
        assert_eq!(tool_tail("--node--"), "node");
        assert_eq!(tool_tail("\u{e9}"), "");
    }

    /// 제안이 없으면 목록에 경로 문장만, 있으면 mise exec 꼴을 덧붙인다.
    #[test]
    fn message_forms() {
        let none = message("rg", &[], None, "");
        assert!(none.contains("`mise install` may be needed."));
        let prefer = Prefer {
            tool: "rg".into(),
            version: "14".into(),
        };
        let some = message("rg", &["/i/rg".to_owned()], Some(&prefer), "");
        assert!(some.contains("Installed copies: `/i/rg`.\nConsider calling one of those paths directly, or `mise exec rg@14 -- rg ...`."));
    }
}
