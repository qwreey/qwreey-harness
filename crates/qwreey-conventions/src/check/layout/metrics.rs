//! 한 함수의 읽기 모양 지표와 알림 범주(python `layout_metrics.measure`, `_doc_info`, `findings`).
//!
//! 알림이 쓰는 지표만 잰다: 빈 줄, 최장 이어짐, 끼운 여러 줄 주석, 문서 주석. 라벨 수, 여러 이름 선언, 한 글자 이름은
//! `conventions-scan layout`(python)만 쓴다.

use std::collections::BTreeSet;
use std::sync::LazyLock;

use harness_hook::py::text::strip;
use harness_hook::rx::Regex;

use super::functions::{ATTRIBUTE, Function};
use super::{Lang, Limits};
use crate::lex::Row;

fn constant(pattern: &str) -> Regex {
    Regex::new(pattern)
}

/// 편집기 접기 표지(`--#region`, `// #endregion`)는 문서도 이유도 아니라 건너뛴다.
static REGION: LazyLock<Regex> =
    LazyLock::new(|| constant(r"^\s*(?:--|//)\s*#\s*(?:end)?region\b"));
static DOC_MARK: LazyLock<Regex> =
    LazyLock::new(|| constant(r"^\s*(?:--\[=*\[|-{2,}|/\*\*?|\*/|\*|/{2,}|#)\s?"));
static DOC_CLOSE: LazyLock<Regex> = LazyLock::new(|| constant(r"(?:\*/|\]=*\])$"));
static DOC_TAG: LazyLock<Regex> = LazyLock::new(|| constant(r"^(?:@|\*|-\s|\|)"));
/// 첫 문장이 끝난 줄: 문장 부호나 한국어 종결 어미로 끝난다.
static SENTENCE_END: LazyLock<Regex> =
    LazyLock::new(|| constant(r#"(?:[.?!:]|[다요음함됨임])["')\]`]*$"#));
static PY_STR_OPEN: LazyLock<Regex> = LazyLock::new(|| constant(r#"^[rRbBuUfF]*("""|'''|"|')"#));
static PY_STR_CLOSE: LazyLock<Regex> = LazyLock::new(|| constant(r#"("""|''')$"#));
static DOC_OPEN: LazyLock<[Regex; 4]> = LazyLock::new(|| {
    [
        constant(r"^\s*(?:---|--\[=+\[)"),
        constant(r"^\s*/\*\*"),
        constant(r"^\s*(?:///|/\*\*)"),
        constant(r"^\s*//"),
    ]
});

/// 문서 없는 시험의 설명(python `TEST_NO_DOC`, `TEST_HIDDEN_DOC`).
const TEST_NO_DOC: &str = "is a test with no doc comment";
const TEST_HIDDEN_DOC: &str = "is a test whose comment is not a doc comment";
/// 알림이 시험의 설명을 가리는 말(python `TEST_MARK`). 함수 이름에는 빈칸이 없다.
pub(super) const TEST_MARK: &str = " is a test ";

fn doc_open(lang: Lang) -> &'static Regex {
    match lang {
        Lang::Lua => &DOC_OPEN[0],
        Lang::Rust => &DOC_OPEN[2],
        Lang::Go => &DOC_OPEN[3],
        _ => &DOC_OPEN[1],
    }
}

/// 문서 주석의 상태.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Doc {
    None,
    Ok,
    /// 호버에 보이지 않는 꼴(`--` 나 `//` 주석).
    Hidden,
}

/// 문서 주석 정보(python `_doc_info` 의 dict).
#[derive(Clone, Debug, PartialEq, Eq)]
struct DocInfo {
    doc: Doc,
    first_len: usize,
    sentence: bool,
    /// 파이썬 docstring 줄(본문에서 뺀다).
    skip: BTreeSet<usize>,
}

impl DocInfo {
    fn none() -> DocInfo {
        DocInfo {
            doc: Doc::None,
            first_len: 0,
            sentence: true,
            skip: BTreeSet::new(),
        }
    }
}

/// 한 함수의 지표(줄 번호는 1 기반).
#[derive(Clone, Debug, PartialEq)]
pub struct Metrics {
    pub name: String,
    pub start: usize,
    pub end: usize,
    pub public: bool,
    pub metamethod: bool,
    pub test: bool,
    pub nonblank: usize,
    pub blank: usize,
    pub max_run: usize,
    /// 끼운 여러 줄 주석: (1 기반 시작 줄, 줄 수).
    pub interleaved: Vec<(usize, usize)>,
    doc: DocInfo,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Kind {
    Blank,
    Comment,
    Code,
}

/// python `measure(rows, lines, fn, lang)`. 줄 범위가 틀리면 `None`(python 은 예외로 layout 알림을 모두 버린다).
pub fn measure(rows: &[Row], lines: &[&str], f: &Function, lang: Lang) -> Option<Metrics> {
    let doc = doc_info(rows, lines, f, lang)?;
    let kinds = body_kinds(rows, f, &doc.skip)?;
    let nonblank = kinds.iter().filter(|(_, k)| *k != Kind::Blank).count();
    let runs = runs(&kinds);
    Some(Metrics {
        name: f.name.clone(),
        start: f.start + 1,
        end: f.last + 1,
        public: f.public,
        metamethod: f.metamethod,
        test: f.test,
        nonblank,
        blank: kinds.len() - nonblank,
        max_run: runs.iter().copied().max().unwrap_or(0),
        interleaved: interleaved(&kinds),
        doc,
    })
}

// 본문 줄마다 (0 기반 줄, 종류). 앞뒤 빈 줄과 skip 줄(파이썬 docstring)은 뺀다
fn body_kinds(rows: &[Row], f: &Function, skip: &BTreeSet<usize>) -> Option<Vec<(usize, Kind)>> {
    let mut out = Vec::new();
    for ln in f.header_end + 1..f.end {
        if skip.contains(&ln) {
            continue;
        }
        let r = rows.get(ln)?;
        let kind = if r.code {
            Kind::Code
        } else if !r.c.is_empty() || r.inside {
            Kind::Comment
        } else {
            Kind::Blank
        };
        out.push((ln, kind));
    }

    // Trim blank lines at both ends
    let lead = out.iter().take_while(|(_, k)| *k == Kind::Blank).count();
    let trail = out
        .iter()
        .rev()
        .take_while(|(_, k)| *k == Kind::Blank)
        .count();
    if lead == out.len() {
        return Some(Vec::new());
    }
    Some(out[lead..out.len() - trail].to_vec())
}

// 빈 줄로 나뉜 문단마다의 줄 수
fn runs(kinds: &[(usize, Kind)]) -> Vec<usize> {
    let mut runs = Vec::new();
    let mut cur = 0;
    for (_, kind) in kinds {
        if *kind != Kind::Blank {
            cur += 1;
        } else if cur > 0 {
            runs.push(cur);
            cur = 0;
        }
    }
    if cur > 0 {
        runs.push(cur);
    }
    runs
}

// 끼운 여러 줄 주석: 바로 위와 아래가 코드인 2줄 이상 덩어리 (1 기반 시작 줄, 줄 수)
fn interleaved(kinds: &[(usize, Kind)]) -> Vec<(usize, usize)> {
    let mut out = Vec::new();
    let mut i = 0;
    while i < kinds.len() {
        if kinds[i].1 != Kind::Comment {
            i += 1;
            continue;
        }
        let mut j = i;
        while j + 1 < kinds.len() && kinds[j + 1].1 == Kind::Comment {
            j += 1;
        }
        let above = if i > 0 { kinds[i - 1].1 } else { Kind::Blank };
        let below = kinds.get(j + 1).map_or(Kind::Blank, |k| k.1);
        if j > i && above == Kind::Code && below == Kind::Code {
            out.push((kinds[i].0 + 1, j - i + 1));
        }
        i = j + 1;
    }
    out
}

// ---------- 문서 주석 ----------

fn comment_only(row: &Row) -> bool {
    !row.code && !row.c.is_empty()
}

fn doc_info(rows: &[Row], lines: &[&str], f: &Function, lang: Lang) -> Option<DocInfo> {
    if lang == Lang::Py {
        return py_doc(rows, lines, f);
    }

    // Comment lines above the header, past decorators and region markers
    let mut k = f.start as i64 - 1;
    let at = |k: i64| usize::try_from(k).ok();
    while let Some(i) =
        at(k).filter(|&i| rows[i].code && ATTRIBUTE.match_start(&rows[i].k).is_some())
    {
        k = i as i64 - 1;
    }
    while let Some(i) =
        at(k).filter(|&i| comment_only(&rows[i]) && REGION.match_start(lines[i]).is_some())
    {
        k = i as i64 - 1;
    }
    let Some(k) = at(k).filter(|&i| comment_only(&rows[i])) else {
        return Some(DocInfo::none());
    };

    // The nearest comment decides; a reason comment above the doc does not hide it
    let block = nearest_doc(rows, lines, k, lang);
    if block.is_empty() {
        let mut top = k;
        while top > 0
            && comment_only(&rows[top - 1])
            && REGION.match_start(lines[top - 1]).is_none()
        {
            top -= 1;
        }
        return Some(DocInfo {
            doc: Doc::Hidden,
            first_len: doc_text(lines[top]).chars().count(),
            sentence: true,
            skip: BTreeSet::new(),
        });
    }
    Some(summary(block.iter().map(|l| doc_text(l)).collect()))
}

// k 줄이 든 여러 줄 주석의 여는 줄(줄 주석이면 k)
fn block_start(rows: &[Row], mut k: usize) -> usize {
    while k > 0 && rows[k].inside && comment_only(&rows[k - 1]) {
        k -= 1;
    }
    k
}

// k 줄에서 위로 이어진 문서 주석 꼴의 줄들(위에서 아래 순). k 줄이 문서 꼴이 아니면 빈 목록
fn nearest_doc<'t>(rows: &[Row], lines: &[&'t str], k: usize, lang: Lang) -> Vec<&'t str> {
    let open = doc_open(lang);
    let mut start = block_start(rows, k);
    if open.match_start(lines[start]).is_none() {
        return Vec::new();
    }
    if start < k {
        return lines[start..=k].to_vec();
    }
    while start > 0
        && comment_only(&rows[start - 1])
        && !rows[start - 1].inside
        && REGION.match_start(lines[start - 1]).is_none()
        && open.match_start(lines[start - 1]).is_some()
    {
        start -= 1;
    }
    lines[start..=k].to_vec()
}

fn doc_text(line: &str) -> String {
    let line = strip(line);
    let cut = DOC_MARK.match_start(line).map_or(0, |m| m.end());
    let text = strip(&line[cut..]);
    let text = DOC_CLOSE.replace_all(text, |_| String::new());
    strip(&text).to_owned()
}

fn summary(texts: Vec<String>) -> DocInfo {
    let texts: Vec<String> = texts.into_iter().skip_while(String::is_empty).collect();
    let first = texts.first().map_or("", String::as_str);
    let next = texts.get(1).map_or("", String::as_str);
    let runs_on = !first.is_empty()
        && !next.is_empty()
        && DOC_TAG.match_start(next).is_none()
        && !SENTENCE_END.is_match(first);
    DocInfo {
        doc: Doc::Ok,
        first_len: first.chars().count(),
        sentence: !runs_on,
        skip: BTreeSet::new(),
    }
}

fn py_doc(rows: &[Row], lines: &[&str], f: &Function) -> Option<DocInfo> {
    let mut k = f.header_end + 1;
    while k < f.end && strip(lines.get(k)?).is_empty() {
        k += 1;
    }
    if k >= f.end || strip(&rows.get(k)?.k) != "\"\"" {
        return Some(DocInfo::none());
    }

    let mut end = k + 1;
    while end < f.end && rows.get(end)?.inside {
        end += 1;
    }
    let head = PY_STR_OPEN.replace_all(strip(lines[k]), |_| String::new());
    let texts: Vec<String> = std::iter::once(head)
        .chain(lines.get(k + 1..end)?.iter().map(|l| strip(l).to_owned()))
        .map(|t| strip(&PY_STR_CLOSE.replace_all(&t, |_| String::new())).to_owned())
        .collect();
    Some(DocInfo {
        skip: (k..end).collect(),
        ..summary(texts)
    })
}

// ---------- 알림 범주 ----------

/// 알림 범주(python `CATEGORIES`), 이 순서로 알린다.
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord)]
pub enum Finding {
    Layout,
    Interleaved,
    DocSummary,
}

impl Finding {
    /// 상태 파일과 알림의 이름.
    pub fn as_str(self) -> &'static str {
        match self {
            Finding::Layout => "layout",
            Finding::Interleaved => "interleaved comment",
            Finding::DocSummary => "doc summary",
        }
    }
}

/// python `findings(m, lang, limits)`: 걸린 범주와 설명, 범주 순서대로.
pub fn findings(m: &Metrics, lim: &Limits) -> Vec<(Finding, String)> {
    let mut out = Vec::new();
    if m.nonblank as f64 >= lim.min_lines && (m.blank == 0 || m.max_run as f64 > lim.max_run) {
        out.push((
            Finding::Layout,
            format!(
                "{} L{}-{} ({} lines, {} blank, longest run {})",
                m.name, m.start, m.end, m.nonblank, m.blank, m.max_run
            ),
        ));
    }
    if !m.interleaved.is_empty() {
        let spots: Vec<String> = m
            .interleaved
            .iter()
            .map(|(l, n)| format!("L{l} ({n} lines)"))
            .collect();
        out.push((
            Finding::Interleaved,
            format!("{} {}", m.name, spots.join(", ")),
        ));
    }
    if let Some(doc) = doc_problem(m, lim) {
        out.push((
            Finding::DocSummary,
            format!("{} L{} {doc}", m.name, m.start),
        ));
    }
    out
}

fn doc_problem(m: &Metrics, lim: &Limits) -> Option<String> {
    if m.metamethod {
        return None;
    }
    match m.doc.doc {
        Doc::None if m.test => Some(TEST_NO_DOC.to_owned()),
        Doc::Hidden if m.test => Some(TEST_HIDDEN_DOC.to_owned()),
        Doc::None if m.public => Some("has no doc comment".to_owned()),
        Doc::Hidden if m.public => Some("has a comment that hover does not show".to_owned()),
        Doc::None | Doc::Hidden => None,
        Doc::Ok if m.doc.first_len as f64 > lim.doc_first_max => {
            Some(format!("first doc line is {} characters", m.doc.first_len))
        }
        Doc::Ok if !m.doc.sentence => {
            Some("first doc sentence runs past the first line".to_owned())
        }
        Doc::Ok => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 이 모듈의 고정 패턴이 모두 regex crate 로 옮겨지고 엔진이 만들어진다.
    #[test]
    fn fixed_patterns_build() {
        REGION.check();
        DOC_MARK.check();
        DOC_CLOSE.check();
        DOC_TAG.check();
        SENTENCE_END.check();
        PY_STR_OPEN.check();
        PY_STR_CLOSE.check();
        for r in DOC_OPEN.iter() {
            r.check();
        }
    }
}
