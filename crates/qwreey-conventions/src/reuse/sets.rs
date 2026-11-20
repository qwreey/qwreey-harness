//! 파일에서 문자열 묶음과 사본 표시를 뽑는다(python `hooks/reuse_sets.py`).
//!
//! 묶음은 따옴표 문자열 3개 이상의 리터럴 목록이나 `"a" | "b"` 합집합이다. 원소는 글자가 있는 낱말만 센다.
//! 렉서([`crate::lex`])는 묶음 후보나 `@copy-of` 가 있을 때만 돌려 주석 줄의 묶음을 거른다.
//! 줄 번호는 python 처럼 1 기반이다. 정규식 위치는 바이트지만 줄 번호로만 쓰므로 판정은 같다.

use std::collections::BTreeSet;
use std::sync::LazyLock;

use harness_hook::py::re::Flags;
use harness_hook::py::text::strip;
use harness_hook::rx::Regex;

use crate::lex::{Family, Row, lex};
use crate::reuse::Clock;
use crate::reuse::regions::parse_regions;

/// 정의 머리 아래의 묶음(python `FLAG_DEF`).
pub const FLAG_DEF: i64 = 1;
/// 타입 합집합(python `FLAG_TYPE`).
pub const FLAG_TYPE: i64 = 2;
/// 파일 사본 표시를 읽는 머리 줄 수(python `HEADER_LINES`).
pub const HEADER_LINES: usize = 10;

/// `@dup-ok` 사유로 치지 않는 글(python `BAD_REASONS`, 소문자로 견준다).
const BAD_REASONS: &[&str] = &[
    "",
    "-",
    "later",
    "todo",
    "fixme",
    "tbd",
    "n/a",
    "나중에",
    "추후",
];
/// 줄이 이것으로 끝나면 다음 줄로 이어진다(python `CONT`).
const CONT: &[char] = &[',', '(', '{', '[', '=', '|'];

const STR: &str = r#""[^"\\\n]*"|'[^'\\\n]*'"#;

fn compiled(pattern: &str, flags: Flags) -> Regex {
    Regex::with_flags(pattern, flags)
}

static STR_RE: LazyLock<Regex> = LazyLock::new(|| compiled(STR, Flags::NONE));
// python 의 패턴은 소유 되풀이(`\s*+`, `[,;]?+`, `++`)로 되짚기를 막는다. regex crate 는 되짚지 않으므로 보통 되풀이로 같은 글을
// 쓴다: 소유 꼴은 맞는 결과를 바꾸지 않는다(그 되짚기 길은 모두 같은 자리에서 끝난다, 형제 저장소 파일 10만 7천 개에서 같음).
static GROUP: LazyLock<Regex> = LazyLock::new(|| {
    let pattern = format!(
        r"[\[\{{\(]((?:\s*(?:{STR})\s*[,;]?)+)\s*[\]\}}\)]|((?:(?:{STR})\s*(?:\||\bor\b)\s*)+(?:{STR}))"
    );
    let flags = Flags {
        dotall: true,
        ..Flags::NONE
    };
    compiled(&pattern, flags)
});
/// python `WORD` 의 글자 꼴(`^(?=.*[A-Za-z])[\w.\-/ ]{2,}$` 에서 앞보기를 뺀 것). 앞보기는 [`is_word`] 가 본다.
static WORD_CHARS: LazyLock<Regex> = LazyLock::new(|| compiled(r"^[\w.\-/ ]{2,}$", Flags::NONE));

// python `WORD.match(x)`: ASCII 글자가 있고(원소에는 줄바꿈이 없어 `.*` 가 끝까지 본다) 글자 꼴이 맞는다
fn is_word(x: &str) -> bool {
    x.chars().any(|c| c.is_ascii_alphabetic()) && WORD_CHARS.match_start(x).is_some()
}
// 정의 머리: 이름 붙은 바인딩과 const/static/let/local/type. 정의가 아닌 쪽끼리(if x in (...) 두 번)는 짝으로 보지 않는다
static DEF: LazyLock<Regex> = LazyLock::new(|| {
    compiled(
        r"^\s*(?:pub(?:\([\w:]+\))?\s+)?(?:export\s+)?(?:const|static|let|local|type)\s+\w+|^\s*[A-Za-z_]\w*\s*(?::[^=]+)?=\s*(?:table\.freeze\(|frozenset\(|set\()?[\[\{\(]|^\s*[A-Za-z_]\w*\s*:\s*&?\[",
        Flags::NONE,
    )
});
static NAME: LazyLock<Regex> = LazyLock::new(|| {
    compiled(
        r"^\s*(?:pub(?:\([\w:]+\))?\s+)?(?:export\s+)?(?:(?:const|static|let|local|type)\s+(?:mut\s+)?)?([A-Za-z_]\w*)",
        Flags::NONE,
    )
});
static TYPE: LazyLock<Regex> = LazyLock::new(|| {
    compiled(
        r#"^\s*(?:export\s+)?type\s+\w+|^\s*\w+\s*:\s*["']"#,
        Flags::NONE,
    )
});
/// 사본 표시(python `COPY`). 대상은 경로처럼 시작해야 한다: 표시를 설명하는 글(`<path>` 자리표시)은 표시가 아니다.
pub static COPY: LazyLock<Regex> =
    LazyLock::new(|| compiled(r#"@copy-of:[ \t]*([A-Za-z0-9_.][^\s`'"<>]*)"#, Flags::NONE));
static DUP: LazyLock<Regex> = LazyLock::new(|| {
    compiled(
        r"(?:--|//|#|/\*|\{/\*)\s*@dup-ok\b:?[ \t]*([^\n]*)",
        Flags::NONE,
    )
});

/// 문자열 묶음 하나(python 의 6칸 목록 `[줄, 이름, 플래그, 원소, 표시 대상, @dup-ok 사유]`).
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct StringSet {
    /// 묶음이 시작하는 줄(1 기반).
    pub line: i64,
    /// 정의 이름. 정의가 아니면 빈 글.
    pub name: String,
    /// [`FLAG_DEF`], [`FLAG_TYPE`] 의 합.
    pub flags: i64,
    /// 낱말 원소, 정렬. 색인에서 읽은 값은 적힌 그대로다.
    pub words: Vec<String>,
    /// 위의 `@copy-of` 가 가리키는 `<경로>#<이름>`.
    pub copy_of: Option<String>,
    /// 위 4줄 안의 `@dup-ok` 사유(앞뒤 공백을 뗀 글).
    pub dup: Option<String>,
}

impl StringSet {
    /// 정의 머리 아래에 있는가.
    pub fn is_def(&self) -> bool {
        self.flags & FLAG_DEF != 0
    }

    /// 타입 합집합인가.
    pub fn is_type(&self) -> bool {
        self.flags & FLAG_TYPE != 0
    }

    /// 원소 집합(python `frozenset(st[3])`).
    pub fn members(&self) -> BTreeSet<&str> {
        self.words.iter().map(String::as_str).collect()
    }
}

/// 사본 표시의 종류(python 의 `"f"`, `"v"`, `"r"`).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum MarkKind {
    /// 파일 사본(머리의 `@copy-of: <경로>`).
    File,
    /// 값 사본(`@copy-of: <경로>#<이름>` 아래의 묶음).
    Value,
    /// 영역 사본과 정본 영역(`@start-replace`).
    Region,
}

impl MarkKind {
    /// 색인 파일의 글.
    pub fn code(self) -> &'static str {
        match self {
            MarkKind::File => "f",
            MarkKind::Value => "v",
            MarkKind::Region => "r",
        }
    }

    /// 색인 파일의 글에서.
    pub fn from_code(code: &str) -> Option<MarkKind> {
        match code {
            "f" => Some(MarkKind::File),
            "v" => Some(MarkKind::Value),
            "r" => Some(MarkKind::Region),
            _ => None,
        }
    }
}

/// 사본 표시 하나(python `[줄, 대상 경로, 이름 또는 None, 종류]`).
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Mark {
    pub line: i64,
    pub target: String,
    pub name: Option<String>,
    pub kind: MarkKind,
}

/// python `reason_ok(text)`: `@dup-ok` 사유가 6글자 이상이고 미루는 말이 아닌가.
pub fn reason_ok(text: &str) -> bool {
    let t = strip(strip(text).trim_end_matches(['*', '/', '}', ' ']));
    !BAD_REASONS.contains(&t.to_lowercase().as_str()) && t.chars().count() >= 6
}

/// python `_is_def(lines, ln)`: 묶음 줄(1 기반)이나 그 위 3줄 안의 정의 머리 줄(0 기반).
///
/// 위로는 여러 줄 리터럴(줄 끝이 `,` 등)과 `| "a"` 로 시작하는 다음 줄을 따라서만 올라간다.
fn def_line(lines: &[&str], ln: usize) -> Option<usize> {
    let lowest = ln.saturating_sub(4);
    for k in (lowest..ln).rev() {
        // Stop where the literal does not continue upward
        if k < ln - 1 {
            let continues = lines[k]
                .trim_end_matches(harness_hook::py::text::is_space)
                .ends_with(CONT)
                || lines[k + 1]
                    .trim_start_matches(harness_hook::py::text::is_space)
                    .starts_with('|');
            if !continues {
                return None;
            }
        }

        if DEF.match_start(lines[k]).is_some() {
            return Some(k);
        }
    }
    None
}

/// 시간 한도: 시계가 이 ms 를 넘으면 [`Budget`](python `deadline`).
#[derive(Clone, Copy)]
pub struct Deadline<'a> {
    pub clock: &'a Clock,
    pub ms: f64,
}

/// [`extract_within`] 가 한도를 넘었다(python `reuse_sets.Budget`).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Budget;

// python `_within(deadline)`
fn within(deadline: Option<Deadline>) -> std::result::Result<(), Budget> {
    match deadline {
        Some(d) if d.clock.ms() > d.ms => Err(Budget),
        _ => Ok(()),
    }
}

/// python `extract(text, fam)`: (묶음 목록, 표시 목록).
///
/// Rust 파일은 `#[cfg(test)]` 앞까지만 본다.
pub fn extract(text: &str, fam: Family) -> (Vec<StringSet>, Vec<Mark>) {
    extract_within(text, fam, None).unwrap_or_default()
}

/// python `extract(text, fam, deadline)`: 한도를 넘으면 python 과 같은 자리(묶음 후보마다, 렉서 앞)에서 [`Budget`].
pub fn extract_within(
    text: &str,
    fam: Family,
    deadline: Option<Deadline>,
) -> std::result::Result<(Vec<StringSet>, Vec<Mark>), Budget> {
    let text = match (fam, text.find("#[cfg(test)]")) {
        (Family::Rust, Some(cut)) => &text[..cut],
        _ => text,
    };
    let lines: Vec<&str> = text.split('\n').collect();

    let cands = candidates(text, deadline)?;
    let has_mark = text.contains("@copy-of");
    within(deadline)?;
    let rows = if !cands.is_empty() || has_mark {
        lex(text, fam, false)
    } else {
        Vec::new()
    };

    let mut sets: Vec<StringSet> = Vec::new();
    for (ln, els) in cands {
        within(deadline)?;
        sets.extend(string_set(&lines, &rows, ln, &els));
    }
    let mut marks = if has_mark {
        copy_marks(&lines, &rows, &mut sets)
    } else {
        Vec::new()
    };
    if text.contains("@start-replace") {
        marks.extend(parse_regions(text).regions.into_iter().map(|r| Mark {
            line: r.line as i64,
            target: r.path,
            name: Some(r.name),
            kind: MarkKind::Region,
        }));
    }
    Ok((sets, marks))
}

// GROUP 의 일치마다 (줄, 원소 집합). 원소가 3개 미만이면 뺀다
fn candidates(
    text: &str,
    deadline: Option<Deadline>,
) -> std::result::Result<Vec<(usize, BTreeSet<String>)>, Budget> {
    let mut out = Vec::new();
    let mut line = 1;
    let mut counted = 0;
    for m in GROUP.find_iter(text) {
        within(deadline)?;
        let group = &text[m.start()..m.end()];
        let els: BTreeSet<String> = STR_RE
            .find_iter(group)
            .iter()
            .map(|s| &group[s.start() + 1..s.end() - 1])
            .filter(|s| !s.is_empty())
            .map(str::to_owned)
            .collect();
        if els.len() < 3 {
            continue;
        }

        // python bisect_right(starts, m.start()): 앞에 있는 줄바꿈 수 + 1
        line += text[counted..m.start()]
            .bytes()
            .filter(|&b| b == b'\n')
            .count();
        counted = m.start();
        out.push((line, els));
    }
    Ok(out)
}

// 후보 하나를 묶음으로: 주석 줄, 낱말 3개 미만, argv 목록은 뺀다
fn string_set(
    lines: &[&str],
    rows: &[Row],
    ln: usize,
    els: &BTreeSet<String>,
) -> Option<StringSet> {
    let row = &rows[ln - 1];
    if !row.code && !row.c.is_empty() {
        return None;
    }
    let words: Vec<String> = els.iter().filter(|x| is_word(x)).cloned().collect();
    if words.len() < 3 || (words.iter().any(|x| x.starts_with('-')) && words.len() <= 8) {
        return None;
    }

    // Definition head and name
    let dk = def_line(lines, ln);
    let head = lines[dk.unwrap_or(ln - 1)];
    let flags = if dk.is_some() { FLAG_DEF } else { 0 }
        | if TYPE.match_start(head).is_some() {
            FLAG_TYPE
        } else {
            0
        };
    let name = dk
        .and_then(|k| {
            NAME.match_start(lines[k])
                .and_then(|m| m.text(lines[k], 1).map(str::to_owned))
        })
        .unwrap_or_default();

    // The last @dup-ok in the three lines above and this one
    let mut dup = None;
    for line in &lines[ln.saturating_sub(4)..ln] {
        if let Some(d) = DUP.search(line) {
            dup = Some(strip(d.text(line, 1).unwrap_or("")).to_owned());
        }
    }

    Some(StringSet {
        line: ln as i64,
        name,
        flags,
        words,
        copy_of: None,
        dup,
    })
}

// `@copy-of` 표시들. 값 사본이면 바로 아래 6줄 안의 첫 묶음에 대상을 적는다
fn copy_marks(lines: &[&str], rows: &[Row], sets: &mut [StringSet]) -> Vec<Mark> {
    let mut marks = Vec::new();
    for (i, s) in lines.iter().enumerate() {
        let Some(m) = COPY.search(s) else { continue };
        if !(i < HEADER_LINES || !rows[i].c.is_empty()) {
            continue;
        }
        let full = m
            .text(s, 1)
            .unwrap_or("")
            .trim_end_matches(['.', ',', ';', ')', '*', '/', '}']);
        let (tgt, name) = match full.split_once('#') {
            Some((t, n)) => (t, Some(n)),
            None => (full, None),
        };
        let line = i as i64 + 1;

        // A path alone in the header is a file copy
        if name.is_none() && i < HEADER_LINES {
            marks.push(mark(line, tgt, None, MarkKind::File));
            continue;
        }

        // The first set within the next six lines is the copy
        let given = name.filter(|n| !n.is_empty());
        match sets
            .iter_mut()
            .find(|st| line < st.line && st.line <= line + 6)
        {
            Some(st) => {
                let name = given.unwrap_or(&st.name).to_owned();
                st.copy_of = Some(format!("{tgt}#{name}"));
                marks.push(mark(line, tgt, Some(name), MarkKind::Value));
            }
            None => match given {
                Some(n) => marks.push(mark(line, tgt, Some(n.to_owned()), MarkKind::Value)),
                None => marks.push(mark(line, tgt, None, MarkKind::File)),
            },
        }
    }
    marks
}

fn mark(line: i64, target: &str, name: Option<String>, kind: MarkKind) -> Mark {
    Mark {
        line,
        target: target.to_owned(),
        name,
        kind,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn words(sets: &[StringSet]) -> Vec<Vec<&str>> {
        sets.iter()
            .map(|s| s.words.iter().map(String::as_str).collect())
            .collect()
    }

    /// 정의 머리, 이름, 플래그, `@dup-ok` 를 python 처럼 읽는다.
    #[test]
    fn reads_definitions_like_python() {
        // A named list, a type union and a list inside a comment
        let text = "local KINDS = { \"omega\", \"sigma\", \"kappa\" }\nexport type T = \"aa\" | \"bb\" | \"cc\"\n-- { \"xx\", \"yy\", \"zz\" }\n";
        let (sets, marks) = extract(text, Family::Lua);
        assert_eq!(
            words(&sets),
            [["kappa", "omega", "sigma"], ["aa", "bb", "cc"]]
        );
        assert_eq!((sets[0].name.as_str(), sets[0].flags), ("KINDS", FLAG_DEF));
        assert_eq!(
            (sets[1].name.as_str(), sets[1].flags),
            ("T", FLAG_DEF | FLAG_TYPE)
        );
        assert!(marks.is_empty());

        // argv-like lists of up to 8 words are not sets
        let (sets, _) = extract("x = [\"-a\", \"bb\", \"cc\", \"dd\"]\n", Family::Py);
        assert!(sets.is_empty());

        // The dup-ok reason is stripped; a short reason is not ok
        let (sets, _) = extract(
            "# @dup-ok: later \nX = [\"aa\", \"bb\", \"cc\"]\n",
            Family::Py,
        );
        assert_eq!(sets[0].dup.as_deref(), Some("later"));
        assert!(!reason_ok("later") && reason_ok("different knowledge */"));
    }

    /// 값 사본 표시는 아래 6줄 안의 첫 묶음에 붙고, 머리의 경로만 있는 표시는 파일 사본이다.
    #[test]
    fn copy_marks_like_python() {
        // A value copy names the set below it
        let text = "-- @copy-of: a/src.luau#FORMS\nlocal F = { \"coin\", \"stick\", \"back\" }\n";
        let (sets, marks) = extract(text, Family::Lua);
        assert_eq!(sets[0].copy_of.as_deref(), Some("a/src.luau#FORMS"));
        assert_eq!(
            marks,
            [mark(1, "a/src.luau", Some("FORMS".into()), MarkKind::Value)]
        );

        // An empty name falls back to the set's own name
        let (_, marks) = extract(
            "-- @copy-of: a.luau#\nlocal F = { \"aa\", \"bb\", \"cc\" }\n",
            Family::Lua,
        );
        assert_eq!(marks[0].name.as_deref(), Some("F"));

        // A header path with trailing punctuation is a file copy
        let (_, marks) = extract("\"\"\"Mod.\n@copy-of: lib/x.py.\n\"\"\"\n", Family::Py);
        assert_eq!(marks, [mark(2, "lib/x.py", None, MarkKind::File)]);
    }

    /// GROUP 을 큰 글에 돌린 시간을 보인다(`cargo test -- --ignored --nocapture group_cost`, 판정은 하지 않는다).
    #[test]
    #[ignore]
    fn group_cost_on_large_text() {
        // About 970 KB of short definitions, the worst ordinary case: one match per line
        let lists: String = (0..19000)
            .map(|i| format!("L{i} = [\"a{i}x\", \"b{i}x\", \"c{i}x\", \"d{i}x\"]\n"))
            .collect();
        let started = std::time::Instant::now();
        let n = GROUP.find_iter(&lists).len();
        println!(
            "GROUP lists {} bytes: {n} matches in {:?}",
            lists.len(),
            started.elapsed()
        );

        // The same size of code with few lists
        let code = "def f(x):\n    return x + 1  # note\n".repeat(26000);
        let started = std::time::Instant::now();
        let n = GROUP.find_iter(&code).len();
        println!(
            "GROUP code {} bytes: {n} matches in {:?}",
            code.len(),
            started.elapsed()
        );
    }

    /// Rust 파일의 시험 모듈 안 묶음은 보지 않는다.
    #[test]
    fn rust_tests_are_cut() {
        let text = "#[cfg(test)]\nconst A: &[&str] = &[\"aa\", \"bb\", \"cc\"];\n";
        assert!(extract(text, Family::Rust).0.is_empty());
        assert_eq!(extract(text, Family::C).0.len(), 1);
    }

    /// 한도를 넘긴 시계로는 묶음 후보에서 Budget 이고, 한도가 없으면 끝까지 뽑는다.
    #[test]
    fn extract_stops_at_the_deadline() {
        let text = "X = [\"aa\", \"bb\", \"cc\"]\n";
        let clock = Clock::start();

        // A deadline already behind the clock
        let past = Deadline {
            clock: &clock,
            ms: -1.0,
        };
        assert!(extract_within(text, Family::Py, Some(past)).is_err());

        // No deadline reads everything
        assert_eq!(extract(text, Family::Py).0.len(), 1);
    }

    /// 닫는 괄호 없이 이어 붙인 문자열이 길어도 GROUP 은 금방 끝난다(되짚기 없는 꼴, python 과 같은 글).
    #[test]
    fn group_is_linear_on_open_concatenation() {
        // The reviewer's shape: strings on their own lines inside an unclosed call
        let body: String = (0..40)
            .map(|i| format!("            \"part number {i} of a long help text \"\n"))
            .collect();
        let text = format!(
            "def main():\n    parser.add_argument(\"--mode\",\n        help=(\n{body}            % DEFAULT))\n"
        );
        let started = std::time::Instant::now();
        let n = GROUP.find_iter(&text).len();

        // 40 strings took hours before; a debug build stays far under a second now
        assert_eq!(n, 0);
        assert!(started.elapsed().as_secs_f64() < 1.0);
    }

    /// 이 모듈의 고정 패턴이 모두 regex crate 로 옮겨지고 엔진이 만들어진다.
    #[test]
    fn fixed_patterns_build() {
        STR_RE.check();
        GROUP.check();
        WORD_CHARS.check();
        DEF.check();
        NAME.check();
        TYPE.check();
        COPY.check();
        DUP.check();
    }

    /// 소유 되풀이를 뺀 GROUP 과 앞보기를 뺀 WORD 는 python 패턴과 같다.
    #[test]
    fn group_and_word_like_python() {
        // GROUP against python's possessive pattern (DOTALL as python compiles it)
        let dotall = Flags {
            dotall: true,
            ..Flags::NONE
        };
        let python_group = format!(
            r"[\[\{{\(]((?:\s*+(?:{STR})\s*+[,;]?+)++)\s*+[\]\}}\)]|((?:(?:{STR})\s*(?:\||\bor\b)\s*)+(?:{STR}))"
        );
        crate::pat::assert_same(
            &python_group,
            dotall,
            &*GROUP,
            &[(1, 1), (2, 2)],
            &[
                r#"x = ["aa", "bb" ,  "cc" ; ]"#,
                r#"("a" "b"  "c""#,
                r#"{'a',}"#,
                r#""a" | "b" or "c" |"#,
                r#"["a" ,]"#,
                r#"( "a"  "b" )"#,
                r#"x = ["a","b" "#,
                "[\"a\"\n  \"b\"\n]",
            ],
        );

        // WORD: an ASCII letter and the word characters, as python's lookahead and class
        let python_word =
            harness_hook::py::re::Regex::new(r"^(?=.*[A-Za-z])[\w.\-/ ]{2,}$").unwrap();
        for x in [
            "ab", "a", "12", "a1", "한글", "한a", "a-b/c d", "a!", "-x", "é1", "a\u{301}",
        ] {
            assert_eq!(is_word(x), python_word.match_start(x).is_some(), "{x:?}");
        }
    }
}
