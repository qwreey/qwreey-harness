//! 영역 사본 표시를 읽고 정본 영역에서 사본 줄을 만든다(python `hooks/copy_regions.py`, 정본 `lib/copy_regions.py`).
//!
//! 표시는 한 줄에 혼자 있다: 들여쓰기, 줄 주석 머리(`#`, `//`, `///`, `//!`, `--`), 표시, 그 밖에 없음.
//! `@start-replace: <경로>#<이름> [키=값 ...]` 과 `@end-replace` 사이가 영역이고, 경로가 자기 파일을 가리키는 영역이 정본이다.
//! 경로는 표시가 든 파일의 저장소 루트 기준이다. `value=string` 은 정본 영역의 문자열 리터럴 하나를 `template` 에 넣는다.
//! 줄 번호는 0 기반 표시 줄([`Region::start`], [`Region::end`])과 1 기반 알림 줄([`Region::line`])이 있다.

mod literal;
mod pyliteral;

use std::sync::LazyLock;

use harness_hook::py::fs::{self, FsError};
use harness_hook::py::path::{abspath, dirname, join, normpath, splitext};
use harness_hook::py::repr::repr_ascii;
use harness_hook::py::shlex;
use harness_hook::py::text::{is_space, strip};
use harness_hook::rx::Regex;

use crate::halt::{Halt, Result};

pub use literal::quote;

/// 알 수 있는 옵션(python `OPTIONS`), 알림에 이 순서로 적는다.
const OPTIONS: &[&str] = &["template", "value"];

/// 표시 줄(python `MARK`): 1 들여쓰기, 2 종류, 3 나머지.
///
/// python 은 종류 뒤에 앞보기 `(?![\w-])` 를 두고 나머지를 `.*?` 로 읽는다. 여기서는 나머지를 "비었거나 `\w`, `-` 가 아닌
/// 글자로 시작"(`(?:[^\w-].*?)??`)으로 쓴다: 빈 나머지를 먼저 해 보는 차례도, 맞는 줄도, 잡는 글도 같다.
pub static MARK: LazyLock<Regex> = LazyLock::new(|| {
    Regex::new(
        r"^(?P<indent>[ \t]*)(?:#+|//[/!]?|--)[ \t]*@(?P<kind>start-replace|end-replace)(?P<rest>(?:[^\w-].*?)??)[ \t]*$",
    )
});

/// 닫힌 영역 하나(python 의 region dict).
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Region {
    pub name: String,
    pub path: String,
    /// 옵션, 적힌 순서(같은 키는 처음 자리에 마지막 값).
    pub opts: Vec<(String, String)>,
    /// 여는 표시 줄(0 기반).
    pub start: usize,
    /// 닫는 표시 줄(0 기반).
    pub end: usize,
    /// 여는 표시의 들여쓰기.
    pub indent: String,
    /// 여는 표시 줄(1 기반).
    pub line: usize,
}

impl Region {
    /// `opts.get(key)`.
    pub fn opt(&self, key: &str) -> Option<&str> {
        self.opts
            .iter()
            .find(|(k, _)| k == key)
            .map(|(_, v)| v.as_str())
    }
}

/// 짝이 없거나 틀린 표시 하나(python `(줄, 글)`).
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct MarkerError {
    /// 1 기반 줄.
    pub line: usize,
    // python `%r` 이 ASCII 밖 글자를 쓰는 글은 옮기지 않아 None 이다
    message: Option<String>,
}

impl MarkerError {
    fn new(line: usize, message: String) -> MarkerError {
        MarkerError {
            line,
            message: Some(message),
        }
    }

    /// 알림 글. python repr 을 옮기지 않은 글이면 [`Halt::Unported`].
    pub fn message(&self) -> Result<&str> {
        self.message
            .as_deref()
            .ok_or(Halt::Unported("a non-ASCII unknown region option"))
    }
}

/// [`parse_regions`] 의 결과.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct Parsed {
    pub regions: Vec<Region>,
    pub errors: Vec<MarkerError>,
}

/// 영역을 만들지 못한 까닭(python `MarkError`). 글은 알림에 그대로 들어간다.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct MarkError(pub String);

// 여는 표시를 읽은 뒤 닫는 표시를 기다리는 영역
struct Open {
    region: Region,
}

/// python `parse_regions(text)`: 닫힌 영역들과 표시 오류들(적힌 순서).
pub fn parse_regions(text: &str) -> Parsed {
    let mut out = Parsed::default();
    let mut open: Option<Open> = None;
    let mut seen: Vec<(String, usize)> = Vec::new();

    for (i, line) in text.split('\n').enumerate() {
        let Some(m) = MARK.match_start(line) else {
            continue;
        };

        // A closing marker ends the open region
        if m.text(line, 2) == Some("end-replace") {
            match open.take() {
                Some(mut o) => {
                    o.region.end = i;
                    out.regions.push(o.region);
                }
                None => out.errors.push(MarkerError::new(
                    i + 1,
                    "end-replace without a start-replace".to_owned(),
                )),
            }
            continue;
        }

        // An opening marker
        if let Some(o) = open.take() {
            out.errors.push(MarkerError::new(
                o.region.line,
                "start-replace without an end-replace before the next start-replace".to_owned(),
            ));
        }
        let indent = m.text(line, 1).unwrap_or("").to_owned();
        let rest = m.text(line, 3).unwrap_or("");
        if let Some(region) = open_region(i, indent, rest, &mut seen, &mut out.errors) {
            open = Some(Open { region });
        }
    }

    if let Some(o) = open {
        out.errors.push(MarkerError::new(
            o.region.line,
            "start-replace without an end-replace".to_owned(),
        ));
    }
    out
}

// 여는 표시의 나머지 글(`: <경로>#<이름> 옵션...`)을 읽는다. 읽지 못하면 오류를 더하고 None
fn open_region(
    i: usize,
    indent: String,
    rest: &str,
    seen: &mut Vec<(String, usize)>,
    errors: &mut Vec<MarkerError>,
) -> Option<Region> {
    let ln = i + 1;
    let Some(spec) = rest.strip_prefix(':') else {
        errors.push(MarkerError::new(
            ln,
            "start-replace needs `: <path>#<NAME>`".to_owned(),
        ));
        return None;
    };
    let words = match shlex::split(spec) {
        Ok(words) => words,
        Err(e) => {
            errors.push(MarkerError::new(
                ln,
                format!("cannot parse the options: {e}"),
            ));
            return None;
        }
    };
    let Some((path, name)) = words
        .first()
        .filter(|w| !w.ends_with('#'))
        .and_then(|w| w.rsplit_once('#'))
    else {
        errors.push(MarkerError::new(
            ln,
            "start-replace needs `<path>#<NAME>`".to_owned(),
        ));
        return None;
    };

    // Options; an unknown one is reported but still kept
    let mut opts: Vec<(String, String)> = Vec::new();
    for w in &words[1..] {
        let (k, v) = w.split_once('=').unwrap_or((w, ""));
        if !w.contains('=') || !OPTIONS.contains(&k) {
            errors.push(MarkerError {
                line: ln,
                message: repr_ascii(w)
                    .map(|r| format!("unknown option {r} (known: {})", OPTIONS.join(", "))),
            });
        }
        match opts.iter_mut().find(|(key, _)| key == k) {
            Some(slot) => slot.1 = v.to_owned(),
            None => opts.push((k.to_owned(), v.to_owned())),
        }
    }

    // Option combinations and duplicate names
    let value = opts
        .iter()
        .find(|(k, _)| k == "value")
        .map(|(_, v)| v.clone());
    if let Some(v) = &value
        && v != "string"
    {
        errors.push(MarkerError::new(
            ln,
            format!("value={v} is not supported (only value=string)"),
        ));
    }
    if opts.iter().any(|(k, _)| k == "template") && value.is_none() {
        errors.push(MarkerError::new(
            ln,
            "template needs value=string".to_owned(),
        ));
    }
    match seen.iter_mut().find(|(n, _)| n == name) {
        Some(slot) => {
            errors.push(MarkerError::new(
                ln,
                format!("duplicate region name {name} (first at line {})", slot.1),
            ));
            slot.1 = ln;
        }
        None => seen.push((name.to_owned(), ln)),
    }

    Some(Region {
        name: name.to_owned(),
        path: path.to_owned(),
        opts,
        start: i,
        end: i,
        indent,
        line: ln,
    })
}

/// python `body(lines, region)`: 두 표시 사이의 줄들.
pub fn body<'a, S: AsRef<str>>(lines: &'a [S], region: &Region) -> &'a [S] {
    &lines[region.start + 1..region.end]
}

/// python `repo_root(path, roots)`: 표시 경로의 기준. 파일을 담은 주어진 루트, 없으면 가장 가까운 `.git` 폴더.
pub fn repo_root(path: &str, roots: &[&str]) -> Result<String> {
    let path = absolute(path)?;
    for r in roots {
        let r = absolute(r)?;
        if path.starts_with(&format!("{}/", r.trim_end_matches('/'))) {
            return Ok(r);
        }
    }

    // Nearest folder with .git, else the file's folder
    let mut d = dirname(&path).to_owned();
    loop {
        if fs::exists(&join(&d, ".git")) {
            return Ok(d);
        }
        let up = dirname(&d).to_owned();
        if up == d {
            return Ok(dirname(&path).to_owned());
        }
        d = up;
    }
}

fn absolute(path: &str) -> Result<String> {
    abspath(path).ok_or(Halt::PyError("cannot read the current directory"))
}

fn resolve(root: &str, rel: &str) -> String {
    normpath(&join(root, rel))
}

/// python `is_canon(region, path, roots)`: 영역의 경로가 자기 파일인가.
pub fn is_canon(region: &Region, path: &str, roots: &[&str]) -> Result<bool> {
    Ok(resolve(&repo_root(path, roots)?, &region.path) == normpath(&absolute(path)?))
}

/// python `expected(region, path, roots)`: `path` 의 사본 영역이 가져야 할 줄들.
///
/// 정본 파일이나 영역이 없거나 정본 영역이 다시 사본이면 [`MarkError`].
pub fn expected(
    region: &Region,
    path: &str,
    roots: &[&str],
) -> Result<std::result::Result<Vec<String>, MarkError>> {
    let cpath = resolve(&repo_root(path, roots)?, &region.path);

    // Read the canon file; a path python cannot pass to open() raises there
    if fs::os_path(&cpath).is_none() {
        return Err(Halt::PyError("a canon path with NUL or a lone surrogate"));
    }
    let ctext = match fs::read_text(&cpath) {
        Ok(t) => t,
        Err(FsError::Os(_) | FsError::Value) => {
            return Ok(Err(MarkError(format!(
                "canon file {} not found",
                region.path
            ))));
        }
    };

    // Find the canon region
    let parsed = parse_regions(&ctext);
    if let Some(first) = parsed.errors.first() {
        return Ok(Err(MarkError(format!(
            "canon file {} has bad markers (line {}: {})",
            region.path,
            first.line,
            first.message()?
        ))));
    }
    let Some(canon) = parsed.regions.iter().find(|r| r.name == region.name) else {
        return Ok(Err(MarkError(format!(
            "canon region {}#{} not found",
            region.path, region.name
        ))));
    };
    if !is_canon(canon, &cpath, roots)? {
        return Ok(Err(MarkError(format!(
            "canon region {}#{} is itself a copy of {}",
            region.path, region.name, canon.path
        ))));
    }

    let canon_lines: Vec<&str> = ctext.split('\n').collect();
    render(
        region,
        &canon_lines,
        canon,
        &splitext(&cpath).1.to_lowercase(),
    )
}

/// python `render(region, canon_lines, canon_region, canon_suffix)`: 사본 영역이 가질 줄들.
pub fn render(
    region: &Region,
    canon_lines: &[&str],
    canon: &Region,
    suffix: &str,
) -> Result<std::result::Result<Vec<String>, MarkError>> {
    let src = body(canon_lines, canon);
    let ind = region.indent.as_str();

    // value=string: the one literal, quoted into the template
    if region.opt("value") == Some("string") {
        let value = match string_value(src, suffix)? {
            Ok(v) => v,
            Err(e) => return Ok(Err(e)),
        };
        let text = region
            .opt("template")
            .unwrap_or("{value}")
            .replace("{value}", &quote(&value));
        let lines = text
            .split('\n')
            .map(|x| {
                if strip(x).is_empty() {
                    x.to_owned()
                } else {
                    format!("{ind}{x}")
                }
            })
            .collect();
        return Ok(Ok(lines));
    }

    // Otherwise the canon lines, re-indented
    let cind = canon.indent.as_str();
    let lines = src
        .iter()
        .map(|x| {
            if strip(x).is_empty() {
                (*x).to_owned()
            } else {
                let tail = x
                    .strip_prefix(cind)
                    .unwrap_or_else(|| x.trim_start_matches(is_space));
                format!("{ind}{tail}")
            }
        })
        .collect();
    Ok(Ok(lines))
}

/// python 정본 영역을 [`pyliteral`] 이 읽지 못한 까닭. [`expected`] 를 부르는 쪽은 그 영역 하나만 판정하지 않는다.
pub const UNSURE_PY: &str = "a python canon region outside the literal subset";

/// python `string_value(lines, suffix)`: 정본 영역의 문자열 리터럴 하나.
///
/// `.py` 정본은 python 이 ast 로 읽는다(옆에 붙은 리터럴은 하나). 다른 언어는 C 꼴 escape 의 큰따옴표 리터럴이다.
fn string_value(lines: &[&str], suffix: &str) -> Result<std::result::Result<String, MarkError>> {
    let found = if suffix == ".py" {
        pyliteral::constants(lines).map_err(|_| Halt::Unported(UNSURE_PY))?
    } else {
        match literal::c_literals(lines)? {
            Ok(found) => found,
            Err(e) => {
                return Ok(Err(MarkError(format!(
                    "cannot read the string literal: {e}"
                ))));
            }
        }
    };
    if found.len() != 1 {
        return Ok(Err(MarkError(format!(
            "value=string needs exactly one string literal in the canon region, found {}",
            found.len()
        ))));
    }
    Ok(Ok(found.into_iter().next().unwrap_or_default()))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn messages(p: &Parsed) -> Vec<(usize, &str)> {
        p.errors
            .iter()
            .map(|e| (e.line, e.message().unwrap_or("?")))
            .collect()
    }

    /// 짝, 옵션, 이름 오류를 python 과 같은 글과 줄로 낸다.
    #[test]
    fn parses_markers_like_python() {
        // A good region with options
        let p = parse_regions(
            "# @start-replace: lib/a.py#OMIT value=string template=\"X = {value}\"\nX = 1\n# @end-replace\n",
        );
        assert!(p.errors.is_empty());
        assert_eq!(p.regions[0].opt("template"), Some("X = {value}"));
        assert_eq!(
            (p.regions[0].start, p.regions[0].end, p.regions[0].line),
            (0, 2, 1)
        );

        // Unpaired, nested and unknown options keep python's order and text
        let text = "// @end-replace\n// @start-replace: a#B\n// @start-replace: a#B k=1 'x\n-- @start-replace: a#C bad\n";
        assert_eq!(
            messages(&parse_regions(text)),
            [
                (1, "end-replace without a start-replace"),
                (
                    2,
                    "start-replace without an end-replace before the next start-replace"
                ),
                (3, "cannot parse the options: No closing quotation"),
                (4, "unknown option 'bad' (known: template, value)"),
                (4, "start-replace without an end-replace"),
            ]
        );

        // A duplicate name points at the first one
        let text = "# @start-replace: a#N\n# @end-replace\n# @start-replace: a#N\n# @end-replace\n";
        assert_eq!(
            messages(&parse_regions(text)),
            [(3, "duplicate region name N (first at line 1)")]
        );
    }

    /// 옵션 없는 사본은 정본 들여쓰기를 사본 들여쓰기로 바꾼다.
    #[test]
    fn renders_reindented_lines() {
        let canon =
            parse_regions("    # @start-replace: a#R\n    x = 1\n\n  y\n    # @end-replace")
                .regions;
        let copy = parse_regions("# @start-replace: a#R\n# @end-replace").regions;
        let lines: Vec<&str> = "    # @start-replace: a#R\n    x = 1\n\n  y\n    # @end-replace"
            .split('\n')
            .collect();

        // Lines without the canon indent are left-stripped
        let got = render(&copy[0], &lines, &canon[0], ".py").unwrap().unwrap();
        assert_eq!(got, ["x = 1", "", "y"]);
    }

    /// 이 모듈의 고정 패턴이 모두 regex crate 로 옮겨지고 엔진이 만들어진다.
    #[test]
    fn fixed_patterns_build() {
        MARK.check();
    }

    /// 앞보기 없이 쓴 표시 줄 패턴은 python 패턴과 같은 줄에 맞고 같은 괄호를 잡는다.
    #[test]
    fn mark_like_python() {
        crate::pat::assert_same(
            r"^(?P<indent>[ \t]*)(?:#+|//[/!]?|--)[ \t]*@(?P<kind>start-replace|end-replace)(?![\w-])(?P<rest>.*?)[ \t]*$",
            harness_hook::py::re::Flags::NONE,
            &*MARK,
            &[(1, 1), (2, 2), (3, 3)],
            &[
                "# @end-replace",
                "  // @start-replace: lib/a.py#X value=string  ",
                "-- @end-replace  \t",
                "# @end-replaced",
                "# @end-replace-x",
                "#@start-replace:x#Y",
                "/// @start-replace \t x \t",
                "# @end-replace\u{301}",
            ],
        );
    }
}
