//! rule 파일 하나(python `rules_inject.parse_rule`, `load_rules`): 프론트매터의 `paths` 글롭과 `switch`, 그리고 본문.

use std::sync::LazyLock;

use harness_hook::py::fs::{self, FsError};
use harness_hook::py::path::join;
use harness_hook::py::re::{Flags, Regex as PyRegex};
use harness_hook::py::text::strip;
use harness_hook::rx::Regex;

use super::glob;
use crate::context::Context;
use crate::halt::{Halt, Result};
use crate::pyops::str_order;

/// 맨 앞의 `---` 프론트매터(python `re.match(r"---\n(.*?)\n---\n?", text, re.S)`).
static FRONT: LazyLock<Regex> = LazyLock::new(|| {
    Regex::with_flags(
        r"---\n(.*?)\n---\n?",
        Flags {
            dotall: true,
            ..Flags::NONE
        },
    )
});
/// 한 줄 꼴 `paths: [a, b]`.
static INLINE: LazyLock<Regex> =
    LazyLock::new(|| Regex::with_flags(r"^paths:\s*\[(.*)\]\s*$", MULTILINE));
/// 목록 꼴 `paths:` 아래 `- a` 줄들.
static BLOCK: LazyLock<Regex> =
    LazyLock::new(|| Regex::with_flags(r"^paths:\s*\n((?:\s+-\s*.*\n?)+)", MULTILINE));
static ITEM: LazyLock<Regex> = LazyLock::new(|| Regex::with_flags(r"^\s+-\s*(.*)$", MULTILINE));
static SWITCH: LazyLock<Regex> =
    LazyLock::new(|| Regex::with_flags(r"^switch:\s*(\S+)\s*$", MULTILINE));

const MULTILINE: Flags = Flags {
    multiline: true,
    ..Flags::NONE
};

/// rule 파일 하나의 프론트매터와 본문(python `parse_rule` 의 결과).
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct RuleText {
    pub globs: Vec<String>,
    /// 프론트매터를 뗀 본문(앞뒤 줄바꿈도 뗀다).
    pub body: String,
    /// `switch: KEY` 의 KEY. 이 키가 harness.env 층에서 `on` 일 때만 싣는다.
    pub switch: Option<String>,
}

impl RuleText {
    /// python `switch_on(key)`: 키가 없거나 빈 글이면 늘 켜짐, 있으면 층의 값이 `on` 일 때만.
    pub fn switch_on(&self, ctx: &Context) -> bool {
        match self.switch.as_deref() {
            None | Some("") => true,
            Some(key) => ctx.is_on(key),
        }
    }

    /// `paths` 글롭들을 py::re 로(python `[glob_to_regex(g) for g in globs]`).
    pub fn compile(&self) -> Result<Vec<PyRegex>> {
        self.globs.iter().map(|g| glob::compile(g)).collect()
    }
}

/// 이 플러그인의 rule 하나(python `load_rules` 의 원소).
#[derive(Clone, Debug)]
pub struct Rule {
    /// 파일 이름에서 `.md` 를 뗀 것.
    pub name: String,
    pub regexes: Vec<PyRegex>,
    pub text: RuleText,
}

/// python `parse_rule(path)`: 프론트매터에 `paths` 가 있으면 그 rule, 아니면 `None`.
///
/// 열지 못한 파일과 일반 파일이 아닌 것(FIFO 는 쓰는 쪽을 기다리지 않는다)은 `None` 이다. UTF-8 이 아닌 파일은 python 이 잡지 않는
/// 예외라 [`Halt::PyError`].
pub fn parse_rule(path: &str) -> Result<Option<RuleText>> {
    let text = match fs::read_regular_text(path) {
        Ok(text) => text,
        Err(FsError::Os(_)) => return Ok(None),
        Err(FsError::Value) => return Err(Halt::PyError("a rule file is not UTF-8")),
    };
    let Some(m) = FRONT.match_start(&text) else {
        return Ok(None);
    };
    let fm = m.text(&text, 1).unwrap_or("");

    // Globs from either form, quotes and blanks dropped
    let globs: Vec<String> = raw_globs(fm)
        .iter()
        .filter(|g| !strip(g).is_empty())
        .map(|g| strip(g).trim_matches(['\'', '"']).to_owned())
        .collect();
    if globs.is_empty() {
        return Ok(None);
    }

    let switch = SWITCH
        .search(fm)
        .and_then(|s| s.text(fm, 1))
        .map(|k| k.trim_matches(['\'', '"']).to_owned());
    Ok(Some(RuleText {
        globs,
        body: text[m.end()..].trim_matches('\n').to_owned(),
        switch,
    }))
}

// 한 줄 꼴이 있으면 그것을 쉼표로(중괄호 안의 쉼표는 나누지 않는다), 없으면 목록 꼴의 줄들
fn raw_globs(fm: &str) -> Vec<String> {
    if let Some(m) = INLINE.search(fm) {
        let inner = m.text(fm, 1).unwrap_or("");
        let mut out = Vec::new();
        let (mut buf, mut depth) = (String::new(), 0i64);
        for ch in inner.chars() {
            match ch {
                '{' => depth += 1,
                '}' => depth -= 1,
                _ => {}
            }
            if ch == ',' && depth == 0 {
                out.push(std::mem::take(&mut buf));
            } else {
                buf.push(ch);
            }
        }
        out.push(buf);
        return out;
    }

    let block_src = format!("{fm}\n");
    let Some(block) = BLOCK.search(&block_src) else {
        return Vec::new();
    };
    let lines = block.text(&block_src, 1).unwrap_or("");
    ITEM.find_iter(lines)
        .iter()
        .filter_map(|m| m.text(lines, 1).map(str::to_owned))
        .collect()
}

/// python `load_rules()`: `dir` 의 `*.md` 를 이름순으로 읽은 rule 들. 폴더를 읽지 못하면 빈 목록.
///
/// 글롭이 python 에서 re.error 인 rule 이 하나라도 있으면 python 은 그 자리에서 예외로 끝난다(오류로 돌려준다).
pub fn load_dir(dir: &str) -> Result<Vec<Rule>> {
    let mut names: Vec<String> = fs::listdir(dir)
        .unwrap_or_default()
        .into_iter()
        .filter(|f| f.ends_with(".md"))
        .collect();
    names.sort_by(|a, b| str_order(a, b));

    let mut rules = Vec::new();
    for f in names {
        let Some(text) = parse_rule(&join(dir, &f))? else {
            continue;
        };
        rules.push(Rule {
            name: f[..f.len() - 3].to_owned(),
            regexes: text.compile()?,
            text,
        });
    }
    Ok(rules)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn write(dir: &str, name: &str, text: &str) -> String {
        let path = join(dir, name);
        std::fs::write(&path, text).unwrap();
        path
    }

    /// 두 꼴의 `paths`, 따옴표, 중괄호 안 쉼표, switch, 본문 앞뒤 줄바꿈.
    #[test]
    fn reads_both_frontmatter_forms() {
        let tmp = std::env::temp_dir().join(format!("conv-rule-{}", std::process::id()));
        std::fs::create_dir_all(&tmp).unwrap();
        let dir = tmp.to_str().unwrap();

        // Inline list with a brace group, and a switch
        let a = write(
            dir,
            "a.md",
            "---\npaths: [\"**/*.{ts,js}\", 'b/*']\nswitch: 'K'\n---\n\n# A\nbody\n\n",
        );
        let got = parse_rule(&a).unwrap().unwrap();
        assert_eq!(got.globs, vec!["**/*.{ts,js}", "b/*"]);
        assert_eq!(got.body, "# A\nbody");
        assert_eq!(got.switch.as_deref(), Some("K"));

        // Block list; no paths means no rule
        let b = write(
            dir,
            "b.md",
            "---\nx: 1\npaths:\n  - \"*.py\"\n  - c/**\n---\nB",
        );
        assert_eq!(parse_rule(&b).unwrap().unwrap().globs, vec!["*.py", "c/**"]);
        let c = write(dir, "c.md", "---\nx: 1\n---\nC");
        assert_eq!(parse_rule(&c).unwrap(), None);
        std::fs::remove_dir_all(&tmp).unwrap();
    }

    /// FIFO 인 rule 파일은 쓰는 쪽을 기다리지 않고 rule 이 아니다(python 도 같다).
    #[cfg(unix)]
    #[test]
    fn fifo_is_not_a_rule() {
        let tmp = std::env::temp_dir().join(format!("conv-rule-fifo-{}", std::process::id()));
        std::fs::create_dir_all(&tmp).unwrap();
        let fifo = tmp.join("p.md");
        let made = std::process::Command::new("mkfifo").arg(&fifo).status();
        assert!(made.is_ok_and(|s| s.success()), "mkfifo");
        assert_eq!(parse_rule(fifo.to_str().unwrap()).unwrap(), None);
        std::fs::remove_dir_all(&tmp).unwrap();
    }

    /// 고정 패턴이 regex crate 와 py::re 에서 같게 맞는다.
    #[test]
    fn fixed_patterns_agree_with_python() {
        let pieces = [
            "---", "\n", "paths:", " ", "[", "]", "- ", "a", "\"*.ts\"", ",", "switch:", "K", "\t",
            "\u{1c}",
        ];
        harness_hook::testkit::assert_agree(
            &[
                ("FRONT", &*FRONT),
                ("INLINE", &*INLINE),
                ("BLOCK", &*BLOCK),
                ("ITEM", &*ITEM),
                ("SWITCH", &*SWITCH),
            ],
            &pieces,
        );
    }
}
