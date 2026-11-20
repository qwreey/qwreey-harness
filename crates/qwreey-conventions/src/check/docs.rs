//! 모델용 문서(CLAUDE.md, SKILL.md, agents, rules, skills 아래 .md) 검사(python `hooks/conv_docs.py`).
//!
//! 문서 종류, 검사할 줄(frontmatter 와 코드 펜스 밖), 이력 표지, 스킬 description 의 꼴, 본문 언어, 원장 id 옆 경로.

use std::sync::LazyLock;

use harness_hook::py::fs;
use harness_hook::py::path::{abspath, basename, dirname, join, normpath, relpath};
use harness_hook::py::re::{Flags, Match};
use harness_hook::py::text::{is_space, strip};
use harness_hook::rx::Regex;

use super::Category;
use super::config::{Patterns, pathlib_parts};
use crate::edit::Added;
use crate::halt::{Halt, Result};
use crate::pat::{Look, Pat, before, is_word};

fn constant(pattern: &str, flags: Flags) -> Regex {
    Regex::with_flags(pattern, flags)
}

/// 인라인 코드(python `INLINE_CODE`).
pub static INLINE_CODE: LazyLock<Regex> = LazyLock::new(|| constant(r"`[^`]*`", Flags::NONE));
/// 웹 주소(python 의 `URL` 패턴).
pub static URL: LazyLock<Regex> = LazyLock::new(|| constant(r"https?://\S+", Flags::NONE));
static PATH_TOKEN: LazyLock<Regex> =
    LazyLock::new(|| constant(r"\S*/\S*|\S+\.\w{1,5}\b", Flags::NONE));
static HAS_MD_PATH: LazyLock<Regex> = LazyLock::new(|| constant(r"\S+\.md\b", Flags::NONE));
static DOC_STATUS: LazyLock<Regex> =
    LazyLock::new(|| constant(r"^\s*(?:[-*>]\s*)?\**status\**\s*:", Flags::IGNORECASE));
static FENCE: LazyLock<Regex> = LazyLock::new(|| constant(r"^\s*(`{3,}|~{3,})", Flags::NONE));
static HANGUL_WORD: LazyLock<Regex> = LazyLock::new(|| constant(r"[가-힣]{2,}", Flags::NONE));
static LATIN_WORD: LazyLock<Regex> = LazyLock::new(|| constant(r"[A-Za-z]{2,}", Flags::NONE));
static QUOTED: LazyLock<Regex> = LazyLock::new(|| {
    constant(
        "`[^`]*`|\"[^\"]*\"|\u{201c}[^\u{201d}]*\u{201d}",
        Flags::NONE,
    )
});
static DESC_WHEN: LazyLock<Regex> = LazyLock::new(|| {
    constant(
        r"\b(?:when|whenever|before|after|while)\b|\buse (?:it |this(?: skill)? )?(?:for|on|to|in|with)\b|\breach for\b",
        Flags::IGNORECASE,
    )
});
// python `(?<![\w'])(?:I (?:can|...)|...)\b`: 뒤보기는 앞 글자 검사로(갈래와 상관없이 같은 검사다)
static DESC_PERSON: LazyLock<Look> = LazyLock::new(|| {
    Look::with_flags(
        r"(?:I (?:can|will|help|am)|I'll|I'm|you can|we can|we will|let me)\b",
        Flags::IGNORECASE,
        |t, m| before(t, m.start()).is_none_or(|c| !is_word(c) && c != '\''),
        None,
    )
});
static MD_PATH: LazyLock<Regex> =
    LazyLock::new(|| constant(r#"[^\s`'"()<>\[\]]+\.md\b"#, Flags::NONE));
// python `(?<=[.!?])\s+`: 뒤보기는 앞 글자 검사로. 거른 공백 줄 안의 자리는 앞이 공백이라 늘 걸러져 건너뛴다
static SENTENCE_GAP: LazyLock<Look> = LazyLock::new(|| {
    Look::new(
        r"\s+",
        |t, m| matches!(before(t, m.start()), Some('.' | '!' | '?')),
        None,
    )
    .skipping(is_space)
});
static DMI: LazyLock<Regex> =
    LazyLock::new(|| constant(r"disable-model-invocation:\s*true\b", Flags::NONE));
static DESCRIPTION: LazyLock<Regex> =
    LazyLock::new(|| constant(r"description:[ \t]*(.*)$", Flags::NONE));

/// 문서 패턴(python `DOC_PATTERNS`): (이름, 패턴, IGNORECASE).
const DOC_PATTERNS: &[(&str, &str, bool)] = &[
    (
        "decision",
        r"사용자\s*(?:결정|합의)|\bper (?:the )?user\b|\bas (?:the user )?(?:discussed|decided|agreed)\b|\bthe user decided\b|사용자\s*20\d\d",
        true,
    ),
    (
        "path",
        r"(?<![\w-])(?:audit|session|handoff)/|\.claude/(?:plan|base|research|audit|handoff|archive)/",
        false,
    ),
    ("ref_path", r"(?<![\w-])audit/\d+", false),
    (
        "tag",
        r"\[(?:실측|측정|추정|추론|measured|estimated?|inferred)[^\]]*\]",
        true,
    ),
    (
        "narration",
        r"\b(?:previously|recently)\b|\bas of\b(?!\s+(?:v?\d|luau|version))|현재 기준|지난\s?(?:주|번)|요즘|사실 정정|\bfact fix\b",
        true,
    ),
    (
        "banner",
        r"사실 정정|\bfact fix\b|정정\s*:|\bcorrection\s*:",
        true,
    ),
    ("ledger", r"\b[A-Z]{1,2}-\d{2,4}\b", false),
];
const DOC_ENTRY: &[&str] = &[
    "date",
    "path",
    "round",
    "decision",
    "tag",
    "narration",
    "ledger",
];
const DOC_REFERENCE: &[&str] = &["decision", "round", "ref_path", "tag", "banner"];
/// 기존 줄 중 한국어 줄이 이보다 많으면(3줄 이상) 그 문서의 언어를 따른다.
const DOC_KO_SHARE: f64 = 0.1;

// `as of` 뒤가 판 번호나 이름이면 서술이 아니다(python narration 의 `(?!\s+(?:v?\d|luau|version))`)
static AS_OF_TAIL: LazyLock<Regex> =
    LazyLock::new(|| constant(r"\s+(?:v?\d|luau|version)", Flags::IGNORECASE));

// 앞에 `\w` 나 `-` 가 없는가(python `(?<![\w-])`)
fn path_start(t: &str, m: &Match) -> bool {
    before(t, m.start()).is_none_or(|c| !is_word(c) && c != '-')
}

// 문서 패턴 하나. 앞뒤 보기가 있는 셋은 [`Look`] 으로: 갈래마다 첫 글자가 달라 거른 자리에 다른 갈래가 맞는 일이 없다
fn doc_pat(name: &str, pattern: &str, icase: bool) -> Box<dyn Pat> {
    let flags = if icase {
        Flags::IGNORECASE
    } else {
        Flags::NONE
    };
    match name {
        "path" => Box::new(Look::new(
            r"((?:audit|session|handoff)/)|\.claude/(?:plan|base|research|audit|handoff|archive)/",
            |t, m| m.group(1).is_none() || path_start(t, m),
            None,
        )),
        "ref_path" => Box::new(Look::new(r"audit/\d+", path_start, None)),
        "narration" => Box::new(Look::with_flags(
            r"\b(?:previously|recently)\b|(\bas of\b)|현재 기준|지난\s?(?:주|번)|요즘|사실 정정|\bfact fix\b",
            Flags::IGNORECASE,
            |t, m| m.group(1).is_none() || AS_OF_TAIL.match_start(&t[m.end()..]).is_none(),
            None,
        )),
        _ => Box::new(constant(pattern, flags)),
    }
}

static DOC_REGEX: LazyLock<Vec<(&'static str, Box<dyn Pat>)>> = LazyLock::new(|| {
    DOC_PATTERNS
        .iter()
        .map(|&(k, p, i)| (k, doc_pat(k, p, i)))
        .collect()
});

fn doc_regex(name: &str) -> &'static dyn Pat {
    &*DOC_REGEX
        .iter()
        .find(|(k, _)| *k == name)
        .expect("a known doc pattern")
        .1
}

/// 모델용 문서 범주별 고치는 법(python `DOC_HINT`). `ledger id path` 는 배포 범위 이름을 끼운다.
pub fn doc_hint(cat: Category) -> &'static str {
    match cat {
        Category::History => {
            "keep the current fact or instruction and move dates, ids, rounds, who decided and change narration to the commit message or an existing ledger"
        }
        Category::Language => {
            "write it in English, since a model reads this file (wording shown to the user as is can stay Korean inside quotes)"
        }
        _ => "",
    }
}

fn ledger_hint(scope: &str) -> String {
    format!(
        "the .md file named next to the id does not ship with this document, so name a ledger file inside {scope} or drop the id"
    )
}

/// 모델용 문서의 종류(python `doc_class`).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum DocClass {
    /// 입구 문서: 지침 파일, 스킬 파일, 에이전트와 규칙 폴더, 스킬 폴더 아래 문서.
    Entry,
    /// skills 아래 references 의 .md.
    Reference,
}

/// python `doc_class(rel)`. 조각이 없는 경로(`.`)는 python 이 IndexError 로 끝난다.
pub fn doc_class(rel: &str) -> Result<Option<DocClass>> {
    let parts = pathlib_parts(rel);
    let Some((&name, dirs)) = parts.split_last() else {
        return Err(Halt::PyError("doc_class of an empty path"));
    };
    if !name.ends_with(".md") {
        return Ok(None);
    }
    if let Some(at) = dirs.iter().position(|p| *p == "skills") {
        let after = &dirs[at + 1..];
        return Ok(Some(if after.contains(&"references") {
            DocClass::Reference
        } else {
            DocClass::Entry
        }));
    }
    if name == "CLAUDE.md" || name == "SKILL.md" || dirs.last() == Some(&"agents") {
        return Ok(Some(DocClass::Entry));
    }
    if dirs.contains(&".claude") && dirs.contains(&"rules") {
        return Ok(Some(DocClass::Entry));
    }
    Ok(None)
}

/// python `doc_lines(text)`: (줄 번호 0 기반, 줄). frontmatter 와 코드 펜스 안은 뺀다.
pub fn doc_lines(text: &str) -> Vec<(usize, &str)> {
    let mut out = Vec::new();
    let mut fence: Option<char> = None;
    let mut front = false;
    for (idx, line) in text.split('\n').enumerate() {
        if idx == 0 && strip(line) == "---" {
            front = true;
            continue;
        }
        if front {
            front = strip(line) != "---";
            continue;
        }
        if let Some(m) = FENCE.match_start(line) {
            let mark = m.text(line, 1).and_then(|t| t.chars().next());
            match fence {
                None => fence = mark,
                Some(f) if Some(f) == mark => fence = None,
                Some(_) => {}
            }
            continue;
        }
        if fence.is_none() {
            out.push((idx, line));
        }
    }
    out
}

fn blank_out(rx: &dyn Pat, s: &str) -> String {
    rx.replace_all(s, &mut |_| " ".to_owned())
}

// 줄에서 인라인 코드, URL, 공개 식별자를 지운 글
fn scrubbed(line: &str, pats: &Patterns) -> String {
    let mut s = blank_out(&*URL, &blank_out(&*INLINE_CODE, line));
    for p in &pats.public {
        s = blank_out(p.as_ref(), &s);
    }
    s
}

/// python `doc_check(text, added, rel, cfg, pats, pub)`: 추가한 줄의 이력 표지(1 기반 줄, 범주).
pub fn doc_check(
    text: &str,
    added: &Added,
    rel: &str,
    pats: &Patterns,
) -> Result<Vec<(usize, Category)>> {
    let Some(cls) = doc_class(rel)? else {
        return Ok(Vec::new());
    };
    let names = if cls == DocClass::Entry {
        DOC_ENTRY
    } else {
        DOC_REFERENCE
    };

    // Patterns for this kind of document
    let mut rx: Vec<(&str, &dyn Pat)> = Vec::new();
    for &k in names {
        match k {
            "decision" if pats.get(k).is_some() => rx.push((k, doc_regex(k))),
            "date" | "round" | "decision" => {
                if let Some(r) = pats.get(k) {
                    rx.push((k, r));
                }
            }
            _ => rx.push((k, doc_regex(k))),
        }
    }

    // Added lines outside fences and status lines
    let mut out = Vec::new();
    for (idx, line) in doc_lines(text) {
        if !added.contains(&idx) || DOC_STATUS.match_start(line).is_some() {
            continue;
        }
        let s = scrubbed(line, pats);
        let bare = blank_out(&*PATH_TOKEN, &s);
        let hit = rx.iter().any(|(k, r)| match *k {
            "path" | "ref_path" => r.is_match(&s),
            "ledger" => r.is_match(&bare) && !HAS_MD_PATH.is_match(&s),
            "date" => r.is_match(&bare),
            _ => r.is_match(&s),
        });
        if hit {
            out.push((idx + 1, Category::History));
        }
    }
    Ok(out)
}

/// 스킬 파일 머리의 설명 칸(python `skill_description`).
struct SkillDescription {
    first: usize,
    last: usize,
    value: String,
    disabled: bool,
}

fn first_is_blank_or_indent(line: &str) -> bool {
    line.chars().next().is_none_or(|c| c == ' ' || c == '\t')
}

fn skill_description(text: &str) -> Option<SkillDescription> {
    let lines: Vec<&str> = text.split('\n').collect();
    if lines.first().is_none_or(|l| strip(l) != "---") {
        return None;
    }
    let mut desc: Option<(usize, usize, String)> = None;
    let mut dmi = false;
    let mut i = 1;
    while i < lines.len() && strip(lines[i]) != "---" {
        dmi = dmi || DMI.match_start(lines[i]).is_some();
        let Some(m) = DESCRIPTION.match_start(lines[i]) else {
            i += 1;
            continue;
        };

        // The value and its folded or indented continuation lines
        let rest = strip(m.text(lines[i], 1).unwrap_or(""));
        let mut j = i + 1;
        while j < lines.len()
            && strip(lines[j]) != "---"
            && (first_is_blank_or_indent(lines[j]) || strip(lines[j]).is_empty())
        {
            j += 1;
        }
        let head = if rest.is_empty() || rest.starts_with(['>', '|']) {
            None
        } else {
            Some(rest)
        };
        let parts: Vec<&str> = head
            .into_iter()
            .chain(lines[i + 1..j].iter().copied())
            .map(strip)
            .filter(|x| !x.is_empty())
            .collect();
        let mut val = parts.join(" ");
        let chars: Vec<char> = val.chars().collect();
        if chars.len() >= 2
            && chars[0] == chars[chars.len() - 1]
            && (chars[0] == '"' || chars[0] == '\'')
        {
            val = chars[1..chars.len() - 1].iter().collect();
        }
        desc = Some((i, j - 1, val));
        i = j;
    }
    desc.map(|(first, last, value)| SkillDescription {
        first,
        last,
        value,
        disabled: dmi,
    })
}

// 한국어 계기 문구인가: 트리거로 시작하거나 따옴표 밖 한글 낱말이 라틴보다 많다
fn korean_phrase(x: &str) -> bool {
    let s = blank_out(&*QUOTED, x);
    x.trim_start_matches(harness_hook::py::text::is_space)
        .starts_with("트리거")
        || HANGUL_WORD.find_iter(&s).len() > LATIN_WORD.find_iter(&s).len()
}

/// python `description_problems(val)`: 스킬 description 이 꼴(무엇과 언제, 영어, 3인칭, 한국어 계기는 끝에)을 벗어난 점.
fn description_problems(val: &str) -> Vec<&'static str> {
    let mut parts = SENTENCE_GAP.split(strip(val));
    while parts.last().is_some_and(|p| korean_phrase(p)) {
        parts.pop();
    }
    let body = parts.join(" ");
    let bare = blank_out(&*QUOTED, &body);
    let mut out = Vec::new();
    if body.is_empty() || HANGUL_WORD.find_iter(&bare).len() >= 3 {
        out.push("not English outside the trailing Korean trigger phrases");
    }
    if !DESC_WHEN.is_match(&body) {
        out.push("no when-clause");
    }
    if DESC_PERSON.is_match(&bare) {
        out.push("first or second person");
    }
    out
}

fn korean_line(line: &str) -> bool {
    let s = blank_out(&*QUOTED, &blank_out(&*URL, line));
    let h = HANGUL_WORD.find_iter(&s).len();
    h >= 3 && h >= LATIN_WORD.find_iter(&s).len()
}

/// python `ship_root(path, root)`: 문서와 함께 배포되는 범위(가장 가까운 `.claude-plugin` 이 있는 폴더, 없으면 저장소).
fn ship_root(path: &str, root: &str) -> Result<String> {
    let mut d = dirname(&abspath(path).ok_or(Halt::PyError("abspath failed"))?).to_owned();
    while d.starts_with(root) && d != root {
        if fs::is_dir(&join(&d, ".claude-plugin")) {
            return Ok(d);
        }
        let up = dirname(&d).to_owned();
        if up == d {
            return Err(Halt::Unported("ship_root does not reach the repo root"));
        }
        d = up;
    }
    Ok(root.to_owned())
}

/// python `shipped(p, path, ship, root)`: 경로 p 가 문서 폴더, 배포 범위, 저장소 가운데 하나에서 배포 범위 안의 있는 파일인가.
fn shipped(p: &str, path: &str, ship: &str, root: &str) -> Result<bool> {
    let doc_dir = dirname(&abspath(path).ok_or(Halt::PyError("abspath failed"))?).to_owned();
    for base in [doc_dir.as_str(), ship, root] {
        let c = normpath(&join(base, p));
        if (c == ship || c.starts_with(&format!("{ship}/"))) && fs::is_file(&c) {
            return Ok(true);
        }
    }
    Ok(false)
}

/// 꼴 문제(1 기반 줄, 범주)와 범주별 고치는 법.
pub type DocShape = (Vec<(usize, Category)>, Vec<(Category, String)>);

/// python `doc_shape(text, added, path, rel, pub)`: 추가한 줄의 꼴 문제와 범주별 고치는 법.
///
/// 스킬 description 꼴, 영어가 아닌 줄(이미 한국어인 문서는 빼고), 함께 배포되지 않는 원장 경로.
pub fn doc_shape(
    text: &str,
    added: &Added,
    path: &str,
    rel: &str,
    pats: &Patterns,
) -> Result<DocShape> {
    let mut out = Vec::new();
    let mut det: Vec<(Category, String)> = Vec::new();

    // Skill description
    let skill = (basename(rel) == "SKILL.md")
        .then(|| skill_description(text))
        .flatten();
    if let Some(d) = skill.filter(|d| !d.disabled && (d.first..=d.last).any(|k| added.contains(&k)))
    {
        let probs = description_problems(&d.value);
        if !probs.is_empty() {
            out.push((d.first + 1, Category::SkillDescription));
            det.push((
                    Category::SkillDescription,
                    format!(
                        "{}. Write what it does, then when to use it (\"Use when ...\"), in English and third person, with any Korean trigger phrases at the end (a skill with `disable-model-invocation: true` takes a one-line menu description instead)",
                        probs.join(", ")
                    ),
                ));
        }
    }

    // Korean lines in an English document
    let rows = doc_lines(text);
    let old: Vec<bool> = rows
        .iter()
        .filter(|(i, l)| !added.contains(i) && !strip(l).is_empty())
        .map(|(_, l)| korean_line(l))
        .collect();
    let ko = old.iter().filter(|b| **b).count();
    if !(ko >= 3 && ko as f64 > DOC_KO_SHARE * old.len() as f64) {
        out.extend(
            rows.iter()
                .filter(|(i, l)| added.contains(i) && korean_line(l))
                .map(|(i, _)| (i + 1, Category::Language)),
        );
    }

    // Ledger ids next to a path that does not ship
    if doc_class(rel)? == Some(DocClass::Entry) {
        let mut root = abspath(path).ok_or(Halt::PyError("abspath failed"))?;
        for _ in pathlib_parts(rel) {
            root = dirname(&root).to_owned();
        }
        let ship = ship_root(path, &root)?;
        let ledger = doc_regex("ledger");
        for (i, line) in &rows {
            if !added.contains(i) || DOC_STATUS.match_start(line).is_some() {
                continue;
            }
            let s = scrubbed(line, pats);
            if !(ledger.is_match(&blank_out(&*PATH_TOKEN, &s)) && HAS_MD_PATH.is_match(&s)) {
                continue;
            }
            let mut any_shipped = false;
            for m in MD_PATH.find_iter(line) {
                let p = &line[m.start()..m.end()];
                if shipped(p.split('#').next().unwrap_or(p), path, &ship, &root)? {
                    any_shipped = true;
                    break;
                }
            }
            if !any_shipped {
                out.push((i + 1, Category::LedgerPath));
                let scope = if ship != root {
                    relpath(&ship, &root).ok_or(Halt::PyError("relpath failed"))?
                } else {
                    "this repo".to_owned()
                };
                det.retain(|(c, _)| *c != Category::LedgerPath);
                det.push((Category::LedgerPath, ledger_hint(&scope)));
            }
        }
    }
    Ok((out, det))
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 문서 종류를 경로로 가르고, frontmatter 와 펜스 안의 줄은 검사하지 않는다.
    #[test]
    fn classes_and_lines() {
        // Kinds by path; `.` has no parts, where python raises IndexError
        assert_eq!(doc_class("CLAUDE.md").unwrap(), Some(DocClass::Entry));
        assert_eq!(
            doc_class("skills/x/references/a.md").unwrap(),
            Some(DocClass::Reference)
        );
        assert_eq!(
            doc_class(".claude/rules/a.md").unwrap(),
            Some(DocClass::Entry)
        );
        assert_eq!(doc_class("docs/a.md").unwrap(), None);
        assert!(doc_class(".").is_err());

        // Frontmatter and fenced lines are not checked
        let lines = doc_lines("---\na: b\n---\nx\n```\ny\n```\nz");
        assert_eq!(lines, vec![(3, "x"), (7, "z")]);
    }

    /// 스킬 description 의 꼴 문제를 python 과 같은 문구로 낸다.
    #[test]
    fn descriptions() {
        // Trailing Korean trigger phrases are allowed
        assert!(description_problems("Does X. Use when Y. 트리거 문구").is_empty());

        // First person and no when-clause
        assert_eq!(
            description_problems("I can help"),
            vec!["no when-clause", "first or second person"]
        );
    }

    /// 이 모듈의 고정 패턴이 모두 regex crate 로 옮겨지고 엔진이 만들어진다.
    #[test]
    fn fixed_patterns_build() {
        INLINE_CODE.check();
        URL.check();
        PATH_TOKEN.check();
        HAS_MD_PATH.check();
        DOC_STATUS.check();
        FENCE.check();
        HANGUL_WORD.check();
        LATIN_WORD.check();
        QUOTED.check();
        DESC_WHEN.check();
        DESC_PERSON.check();
        MD_PATH.check();
        SENTENCE_GAP.check();
        DMI.check();
        DESCRIPTION.check();
        AS_OF_TAIL.check();
        for (_, r) in DOC_REGEX.iter() {
            r.check();
        }
    }

    /// 앞뒤 보기를 코드로 옮긴 문서 패턴들은 python 패턴과 같은 일치를 낸다.
    #[test]
    fn lookaround_patterns_like_python() {
        // Persons, sentence ends, paths and narration, with their neighbours
        let icase = Flags::IGNORECASE;
        let texts = [
            "I can do it",
            "xI can",
            "I'll go",
            "'I'm here",
            "We will. you can",
            "let me see",
            "LET ME",
            "ami can",
            "a. b! c?  d",
            ".  ",
            "a .b",
            "x audit/1 session/ handoff/",
            "a-audit/ waudit/2 .claude/plan/",
            "previously, as of v2",
            "As of Version 3",
            "as of luau",
            "as of now",
            "the fact fix",
            "현재 기준",
        ];

        // The skill description patterns, then every doc pattern
        crate::pat::assert_same(
            r"(?<![\w'])(?:I (?:can|will|help|am)|I'll|I'm|you can|we can|we will|let me)\b",
            icase,
            &*DESC_PERSON,
            &[],
            &texts,
        );
        crate::pat::assert_same(r"(?<=[.!?])\s+", Flags::NONE, &*SENTENCE_GAP, &[], &texts);
        for (name, pattern, i) in DOC_PATTERNS {
            let flags = if *i { icase } else { Flags::NONE };
            crate::pat::assert_same(pattern, flags, doc_regex(name), &[], &texts);
        }
    }
}
