//! 설치된 Claude Code 플러그인의 폴더 찾기(python `hooks/conv_plugins.py`): luau-kb 팩의 분리 계획기를 찾을 때 쓴다.
//!
//! Claude Code 자신의 파일만 본다: `<설정 디렉터리>/plugins/installed_plugins.json`(설치된 플러그인과 installPath),
//! `<설정 디렉터리>/plugins/known_marketplaces.json`(마켓 위치). 읽지 못한 파일은 `{}` 이다.

use harness_hook::Env;
use harness_hook::py::fs;
use harness_hook::py::json_load::loads;
use harness_hook::py::path::{expanduser, join, normpath};
use harness_hook::py::value::{Dict, Value};

use super::pyops::{items_or_empty, str_order};
use crate::halt::{Halt, Result};

/// python `config_dir()`: `$CLAUDE_CONFIG_DIR`, 없으면 `~/.claude`.
pub fn config_dir(env: &Env) -> String {
    match env.get_nonempty("CLAUDE_CONFIG_DIR") {
        Some(dir) => dir.to_owned(),
        None => expanduser("~/.claude", env),
    }
}

/// python `read_json(path)`: 읽지 못하거나 JSON 이 아니면 `{}`. dict 가 아닌 JSON 도 그대로 준다.
fn read_json(path: &str) -> Value {
    fs::read_text(path)
        .ok()
        .and_then(|text| loads(&text).ok())
        .unwrap_or_else(|| Value::Dict(Dict::new()))
}

fn plugins_file(cfg: &str, name: &str) -> String {
    join(&join(cfg, "plugins"), name)
}

/// python `market_dir(markets, market, name)`: 마켓 정의가 가리키는 플러그인 폴더.
///
/// marketplace.json 이 dict 가 아니면 python 은 `.get` 에서 끝난다.
fn market_dir(markets: &Dict, market: &str, name: &str) -> Result<Option<String>> {
    let Some(Value::Dict(def)) = markets.get(market) else {
        return Ok(None);
    };
    let Some(Value::Str(loc)) = def.get("installLocation") else {
        return Ok(None);
    };

    // The first entry with this name decides
    let manifest = read_json(&join(&join(loc, ".claude-plugin"), "marketplace.json"));
    let Ok(manifest) = manifest.into_dict() else {
        return Err(Halt::PyError("marketplace.json is not an object"));
    };
    for entry in items_or_empty(manifest.get("plugins"))? {
        let Some(e) = entry.as_dict() else { continue };
        let named = matches!(e.get("name"), Some(Value::Str(n)) if n == name);
        if let (true, Some(Value::Str(source))) = (named, e.get("source")) {
            let dir = normpath(&join(loc, source));
            return Ok(fs::is_dir(&dir).then_some(dir));
        }
    }
    Ok(None)
}

/// 설치 기록의 플러그인 하나(python `installed_roots` 의 원소).
struct Installed {
    name: String,
    market: String,
    root: String,
}

/// python `installed_roots(cfg)`: installed_plugins.json 순서. 폴더는 마켓 정의가 가리키는 곳, 없으면 첫 installPath.
fn installed_roots(cfg: &str) -> Result<Vec<Installed>> {
    let markets = read_json(&plugins_file(cfg, "known_marketplaces.json"))
        .into_dict()
        .unwrap_or_default();
    let Ok(file) = read_json(&plugins_file(cfg, "installed_plugins.json")).into_dict() else {
        return Ok(Vec::new());
    };
    let Some(Value::Dict(plugins)) = file.get("plugins") else {
        return Ok(Vec::new());
    };

    let mut out = Vec::new();
    for (key, entries) in plugins.iter() {
        let (name, market) = key.split_once('@').unwrap_or((key, ""));
        let root = match market_dir(&markets, market, name)? {
            Some(root) => Some(root),
            None => first_install_path(entries),
        };
        if let Some(root) = root {
            out.push(Installed {
                name: name.to_owned(),
                market: market.to_owned(),
                root,
            });
        }
    }
    Ok(out)
}

// 설치 항목들 가운데 폴더가 있는 첫 installPath
fn first_install_path(entries: &Value) -> Option<String> {
    let Value::List(entries) = entries else {
        return None;
    };
    entries
        .iter()
        .filter_map(|e| e.as_dict()?.get("installPath")?.as_str())
        .find(|p| fs::is_dir(p))
        .map(str::to_owned)
}

/// python `plugin_root(name)`: 플러그인 `name` 의 폴더. 여러 마켓에 있으면 마켓 이름순 첫째. 없으면 `None`.
///
/// 설치 기록이 없으면 아는 마켓의 정의에서 찾는다(로컬 폴더 마켓은 설치 없이 켜기만 해도 제자리에서 실린다).
pub fn plugin_root(name: &str, env: &Env) -> Result<Option<String>> {
    let cfg = config_dir(env);

    // Installed copies, by market then folder
    let mut hits: Vec<Installed> = installed_roots(&cfg)?
        .into_iter()
        .filter(|p| p.name == name)
        .collect();
    hits.sort_by(|a, b| str_order(&a.market, &b.market).then_with(|| str_order(&a.root, &b.root)));
    if let Some(first) = hits.into_iter().next() {
        return Ok(Some(first.root));
    }

    // Known marketplaces, by name
    let Ok(markets) = read_json(&plugins_file(&cfg, "known_marketplaces.json")).into_dict() else {
        return Ok(None);
    };
    let mut names: Vec<&str> = markets.iter().map(|(k, _)| k).collect();
    names.sort_by(|a, b| str_order(a, b));
    for market in names {
        if let Some(root) = market_dir(&markets, market, name)? {
            return Ok(Some(root));
        }
    }
    Ok(None)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 폴더 마켓의 정의가 설치 기록의 옛 installPath 보다 앞선다.
    #[test]
    fn market_definition_wins() {
        // A directory market that defines the plugin
        let tmp = std::env::temp_dir().join(format!("structrem-plugins-{}", std::process::id()));
        let t = tmp.to_str().unwrap().to_owned();
        let pack = format!("{t}/mkt/packs/kb");
        std::fs::create_dir_all(&pack).unwrap();
        std::fs::create_dir_all(format!("{t}/mkt/.claude-plugin")).unwrap();
        std::fs::create_dir_all(format!("{t}/cfg/plugins")).unwrap();
        std::fs::write(
            format!("{t}/mkt/.claude-plugin/marketplace.json"),
            r#"{"plugins": [{"name": "kb", "source": "./packs/kb"}]}"#,
        )
        .unwrap();

        // A config dir that knows the market and records a stale cache path
        std::fs::write(
            format!("{t}/cfg/plugins/known_marketplaces.json"),
            format!(r#"{{"m": {{"installLocation": "{t}/mkt"}}}}"#),
        )
        .unwrap();
        std::fs::write(
            format!("{t}/cfg/plugins/installed_plugins.json"),
            format!(r#"{{"plugins": {{"kb@m": [{{"installPath": "{t}/stale"}}]}}}}"#),
        )
        .unwrap();
        let env = Env::from_pairs([("CLAUDE_CONFIG_DIR", format!("{t}/cfg"))]);

        // The market's folder, then nothing for an unknown plugin
        assert_eq!(plugin_root("kb", &env).unwrap(), Some(pack));
        assert_eq!(plugin_root("other", &env).unwrap(), None);
        std::fs::remove_dir_all(&tmp).unwrap();
    }
}
