//! 패키지 경계(python reuse-check 의 `package_of`, `pkg_names`, `depends_on`, `importable`).
//!
//! 두 파일이 같은 언어이고 같은 패키지이거나 한쪽이 다른 쪽에 의존한다고 선언했으면 서로 import 할 수 있다.
//! 선언은 Cargo `path = "..."` 와 매니페스트 안의 패키지 이름(wally, pesde, npm, pyproject)으로 본다.

use std::collections::{BTreeSet, HashMap};
use std::sync::LazyLock;

use harness_hook::py::fs::{self, FsError};
use harness_hook::py::json_load::loads;
use harness_hook::py::path::{dirname, join, normpath};
use harness_hook::py::re::{Flags, Regex, escape};
use harness_hook::py::value::Value;

use crate::halt::{Halt, Result};
use crate::reuse::files::{ext_of, lang};

/// 패키지 루트를 알리는 매니페스트(python `MANIFESTS`).
const MANIFESTS: &[&str] = &[
    "Cargo.toml",
    "package.json",
    "pyproject.toml",
    "wally.toml",
    "pesde.toml",
    "default.project.json",
];
/// `name = "..."` 를 읽는 매니페스트(python `pkg_names` 의 차례).
const NAMED: &[&str] = &["Cargo.toml", "pesde.toml", "wally.toml", "pyproject.toml"];

static NAME_LINE: LazyLock<Regex> = LazyLock::new(|| {
    let flags = Flags {
        multiline: true,
        ..Flags::NONE
    };
    Regex::with_flags(r#"^name\s*=\s*"([^"]+)""#, flags).expect("constant pattern")
});
static PATH_DEP: LazyLock<Regex> =
    LazyLock::new(|| Regex::new(r#"path\s*=\s*"([^"]+)""#).expect("constant pattern"));

/// 폴더 -> 패키지 루트(python 의 `cache`). 한 번 실행하는 동안 쓴다.
#[derive(Debug, Default)]
pub struct Packages {
    root: String,
    of_dir: HashMap<String, String>,
}

impl Packages {
    /// 저장소 `root` 의 패키지 찾기.
    pub fn new(root: &str) -> Packages {
        Packages {
            root: root.to_owned(),
            of_dir: HashMap::new(),
        }
    }

    /// python `package_of(root, rel, cache)`: 파일이 든 가장 가까운 패키지 폴더(루트 기준, 루트면 빈 글).
    pub fn package_of(&mut self, rel: &str) -> String {
        let d = dirname(rel);
        if let Some(p) = self.of_dir.get(d) {
            return p.clone();
        }

        // Walk up to a manifest or the repo root
        let mut cur = d.to_owned();
        loop {
            let p = join(&self.root, &cur);
            let plugin = fs::exists(&join(&join(&p, ".claude-plugin"), "plugin.json"));
            if plugin || MANIFESTS.iter().any(|m| fs::exists(&join(&p, m))) || cur.is_empty() {
                break;
            }
            let up = dirname(&cur).to_owned();
            if up == cur {
                break;
            }
            cur = up;
        }

        self.of_dir.insert(d.to_owned(), cur.clone());
        cur
    }

    /// python `importable(root, ra, rb, cache)`: 같은 언어이고 같은 패키지이거나 의존을 선언했나.
    pub fn importable(&mut self, ra: &str, rb: &str) -> Result<bool> {
        if lang(&ext_of(ra)) != lang(&ext_of(rb)) {
            return Ok(false);
        }
        let pa = self.package_of(ra);
        let pb = self.package_of(rb);
        Ok(pa == pb || self.depends_on(&pa, &pb)? || self.depends_on(&pb, &pa)?)
    }

    /// python `depends_on(root, a, b)`: 패키지 a 의 매니페스트가 b 를 경로나 이름으로 가리키나.
    fn depends_on(&self, a: &str, b: &str) -> Result<bool> {
        let names = self.pkg_names(b)?;
        let want = normpath(if b.is_empty() { "." } else { b });
        for m in MANIFESTS {
            let Some(t) = read_manifest(&join(&join(&self.root, a), m))? else {
                continue;
            };

            // Cargo path dependencies
            for dep in PATH_DEP.find_iter(&t) {
                if normpath(&join(a, dep.text(&t, 1).unwrap_or(""))) == want {
                    return Ok(true);
                }
            }

            // The package name as a whole word
            for n in &names {
                let pattern = format!(r"(?<![\w-]){}(?![\w-])", escape(n));
                let re = Regex::new(&pattern)
                    .map_err(|_| Halt::Unported("a package name this port cannot match"))?;
                if re.is_match(&t) {
                    return Ok(true);
                }
            }
        }
        Ok(false)
    }

    /// python `pkg_names(root, pkg)`: 매니페스트의 이름들과 그 `/` 뒤 꼬리.
    fn pkg_names(&self, pkg: &str) -> Result<BTreeSet<String>> {
        let dir = join(&self.root, pkg);
        let mut out = BTreeSet::new();
        for m in NAMED {
            if let Some(t) = read_manifest(&join(&dir, m))?
                && let Some(found) = NAME_LINE.search(&t)
            {
                out.insert(found.text(&t, 1).unwrap_or("").to_owned());
            }
        }

        // package.json name; a name that is not a string ends python with a TypeError or AttributeError
        if let Some(name) = package_json_name(&join(&dir, "package.json"))? {
            out.insert(name);
        }
        out.remove("");
        let tails: Vec<String> = out
            .iter()
            .map(|n| n.rsplit('/').next().unwrap_or("").to_owned())
            .collect();
        out.extend(tails);
        Ok(out)
    }
}

// python `open(p, encoding="utf-8").read()` 을 `except OSError` 안에서: 없으면 None, UTF-8 이 아니면 python 은 예외로 끝난다
fn read_manifest(path: &str) -> Result<Option<String>> {
    match fs::read_text(path) {
        Ok(t) => Ok(Some(t)),
        Err(FsError::Os(_)) => Ok(None),
        Err(FsError::Value) => Err(Halt::PyError("a manifest that is not UTF-8")),
    }
}

// python `json.load(open(p)).get("name") or ""`(OSError, ValueError, AttributeError 는 잡는다)
fn package_json_name(path: &str) -> Result<Option<String>> {
    let Ok(text) = fs::read_text(path) else {
        return Ok(None);
    };
    let Ok(value) = loads(&text) else {
        return Ok(None);
    };
    let Value::Dict(d) = &value else {
        return Ok(None);
    };
    match d.get("name") {
        Some(Value::Str(s)) => Ok(Some(s.clone())),
        Some(v) if v.truthy() => Err(Halt::PyError("package.json name is not a string")),
        _ => Ok(None),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 선언한 경로 의존과 이름 의존은 import 할 수 있고, 다른 언어는 아니다.
    #[test]
    fn dependencies_like_python() {
        let base = std::env::temp_dir().join(format!("qc-pkg-{}", std::process::id()));
        let root = base.to_str().unwrap().to_owned();
        let put = |rel: &str, text: &str| {
            let p = base.join(rel);
            std::fs::create_dir_all(p.parent().unwrap()).unwrap();
            std::fs::write(p, text).unwrap();
        };
        put(
            "one/Cargo.toml",
            "[package]\nname = \"one\"\n[dependencies]\ntwo = { path = \"../two\" }\n",
        );
        put("two/Cargo.toml", "[package]\nname = \"two\"\n");
        put("three/Cargo.toml", "[package]\nname = \"three\"\n");
        put(
            "web/package.json",
            "{\"dependencies\": {\"@scope/two\": \"1\"}}",
        );

        // Paths and names
        let mut pk = Packages::new(&root);
        assert_eq!(pk.package_of("one/src/lib.rs"), "one");
        assert!(pk.importable("one/src/lib.rs", "two/src/lib.rs").unwrap());
        assert!(!pk.importable("three/src/lib.rs", "two/src/lib.rs").unwrap());

        // A name match needs the same language too
        assert!(!pk.importable("web/a.ts", "two/src/lib.rs").unwrap());
        std::fs::remove_dir_all(&base).unwrap();
    }
}
