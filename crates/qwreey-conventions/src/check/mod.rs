//! conventions-check(python `hooks/conventions-check.py`): 이번에 추가한 줄이 주석, 모델용 문서 관례를 벗어난 것 같으면 알린다.
//!
//! PostToolUse(Write, Edit, MultiEdit)에서 info 태그 하나를 낸다. 막지 않는다. 알림은 (session, 호출한 쪽, compact 회차,
//! 파일, 범주)마다 한 번이다. 이번에 추가하지 않은 줄의 문제는 [`leftovers`] 에 쌓아 Stop 에서 사용자에게 한 줄로 보인다.

mod char_tables;
pub mod chars;
pub mod config;
pub mod docs;
pub mod history;
pub mod lang;
pub mod layout;
pub mod leftovers;
pub mod state;

use harness_hook::HookInput;
use harness_hook::epoch;
use harness_hook::output::{EnsureAscii, HookOutput};
use harness_hook::py::fs::{self, FsError};
use harness_hook::py::path::{abspath, relpath, splitext};
use harness_hook::py::value::{Dict, Value};

use crate::context::{Context, PLUGIN};
use crate::edit::{self, Added, MAX_BYTES};
use crate::halt::{Halt, Result};
use crate::lex::{self, Family, Row};
use crate::pyval;
use config::{Cfg, Patterns};
use lang::{Script, SiblingCache};
use layout::{Finding, Lang, Limits, Shape};

/// 알림 범주(python 의 범주 글). 선언 순서가 알림 문장의 순서다(python `CATEGORY_ORDER`).
#[derive(Clone, Copy, Debug, PartialEq, Eq, PartialOrd, Ord, Hash)]
pub enum Category {
    History,
    RefTail,
    SkillDescription,
    LedgerPath,
    Symbol,
    Escape,
    Invisible,
    Language,
}

impl Target {
    /// 코드 파일인가(python `kind == "comment"`). 아니면 모델용 문서다.
    pub fn is_code(&self) -> bool {
        matches!(self.kind, Kind::Comment(_))
    }

    /// 이 파일의 알림 끝 대응 문장.
    pub fn tail(&self) -> &'static str {
        if self.is_code() {
            COMMENT_TAIL
        } else {
            DOC_TAIL
        }
    }

    /// 코드 파일이고 머리 6줄에 생성 파일 표시가 있는가(python `kind == "comment" and generated(text)`).
    pub fn skips_generated(&self, text: &str) -> bool {
        self.is_code() && edit::generated(text, 6)
    }
}

impl Category {
    const ORDER: [Category; 8] = [
        Category::History,
        Category::RefTail,
        Category::SkillDescription,
        Category::LedgerPath,
        Category::Symbol,
        Category::Escape,
        Category::Invisible,
        Category::Language,
    ];

    /// 알림과 상태 파일의 이름.
    pub fn as_str(self) -> &'static str {
        match self {
            Category::History => "history marker",
            Category::RefTail => "Ref tail without a reason sentence",
            Category::SkillDescription => "skill description",
            Category::LedgerPath => "ledger id path",
            Category::Symbol => "non-keyboard symbol",
            Category::Escape => "escaped character",
            Category::Invisible => "invisible character",
            Category::Language => "language mismatch",
        }
    }

    // 코드 주석 범주의 고치는 법(python `FIX_HINT`)
    fn comment_hint(self) -> &'static str {
        match self {
            Category::History => {
                "keep the reason as a sentence about the code now and move dates, ids, rounds, who decided and what it used to do to the commit message"
            }
            Category::RefTail => "write the reason sentence above the Ref: line",
            _ => "",
        }
    }
}

/// 주석 알림 끝의 대응 문장(python `COMMENT_TAIL`). 여러 파일을 한 알림에 담는 bash-writes 는 끝에 한 번만 붙인다.
pub const COMMENT_TAIL: &str = "Fix those lines; a false match (quoted text, a needed symbol) can stay, said once in your report.";
/// 모델용 문서 알림 끝의 대응 문장(python `DOC_TAIL`, 지금은 [`COMMENT_TAIL`] 과 같은 글).
pub const DOC_TAIL: &str = COMMENT_TAIL;
/// 상태 폴더(python `NS`, 이름 변경 전과 같게 둔다).
const NS: &str = leftovers::NS;
/// 범주당 찍는 숫자 수 상한(python `LINE_LIST_MAX`).
const LINE_LIST_MAX: usize = 40;

/// 검사하는 파일의 종류.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Kind {
    /// 코드 파일(주석 줄만 본다).
    Comment(Family),
    /// 모델용 문서.
    Doc,
}

/// 검사할 파일(python `target` 의 결과).
pub struct Target {
    cfg: Cfg,
    rel: String,
    kind: Kind,
    ext: String,
}

/// 한 번의 편집(python `file_notice` 의 인자).
pub struct Edit<'a> {
    pub path: &'a str,
    pub target: &'a Target,
    pub text: &'a str,
    pub added: &'a Added,
}

/// 훅 하나(PostToolUse 와 Stop).
pub fn run(ctx: &Context, input: &HookInput) -> Result<Option<String>> {
    if input.hook_event_name() == Some("Stop") {
        let sid = pyval::sanitized_id(input.get("session_id"));
        return leftovers::report(ctx.tempdir()?, &sid);
    }
    let tool = input.tool_name().unwrap_or("");
    if !matches!(tool, "Write" | "Edit" | "MultiEdit") {
        return Ok(None);
    }

    // Which file, and whether it is checked at all
    let ti = pyval::dict_or_empty(input.get("tool_input"))?;
    let path = pyval::str_or_empty(pyval::get(ti, "file_path"))?;
    if path.is_empty() {
        return Ok(None);
    }
    let Some(target) = target(ctx, path, input.get("cwd"))? else {
        return Ok(None);
    };

    // Text and the lines this edit added
    let resp = input.get("tool_response").and_then(Value::as_dict);
    let disk = match fs::getsize(path) {
        Err(FsError::Value) => return Err(Halt::PyError("os.path.getsize of an unusable path")),
        Err(FsError::Os(_)) => None,
        Ok(size) if size > MAX_BYTES => None,
        Ok(_) => fs::read_text(path).ok(),
    };
    let Some((text, added)) = edit::collect(tool, ti, resp, disk.as_deref())? else {
        return Ok(None);
    };
    if target.skips_generated(&text) {
        return Ok(None);
    }

    // Notice once per (session, caller, epoch, file, category)
    let state_path = state_file(ctx, input)?;
    let edit = Edit {
        path,
        target: &target,
        text: &text,
        added: &added,
    };
    let body = {
        let _lock = state::StateLock::acquire(&state_path);
        let mut st = state::load(&state_path);
        let (body, dirty) = file_notice(ctx, input, &edit, &mut st, true)?;
        if dirty {
            state::save(&state_path, &st);
        }
        body
    };
    if body.is_empty() {
        return Ok(None);
    }

    let tag = notice_tag(ctx, input, &body)?;
    Ok(Some(
        HookOutput::context("PostToolUse", tag).render(EnsureAscii::No),
    ))
}

/// python `notice_tag(data, body)`: 주석 알림과 layout 알림을 담는 info 태그 하나.
pub fn notice_tag(ctx: &Context, input: &HookInput, body: &[String]) -> Result<String> {
    Ok(format!(
        "<harness-hook name=\"{PLUGIN}\" level=\"info\"{}>{}</harness-hook>",
        ctx.nonce_attr(input.get("session_id"))?,
        body.join(" ")
    ))
}

/// 알림 중복 상태 파일(python `state_file(session_id, agent_id)`). 폴더를 만든다.
pub fn state_file(ctx: &Context, input: &HookInput) -> Result<String> {
    let sid = pyval::truthy_text(input.get("session_id")).unwrap_or_default();
    let agent = pyval::truthy_text(input.get("agent_id"));
    epoch::state_path(ctx.tempdir()?, PLUGIN, NS, &sid, agent.as_deref())
        .map_err(|_| Halt::PyError("cannot create the state dir"))
}

/// python `target(path, data)`: 검사하는 파일이면 그 설정과 종류, 아니면 `None`.
pub fn target(ctx: &Context, path: &str, cwd: Option<&Value>) -> Result<Option<Target>> {
    let ext = splitext(path).1.to_lowercase();
    let root = edit::project_root(path, cwd, &ctx.hook.env)?;
    let cfg = Cfg::load(&root);
    let rel = relpath(path, &root).ok_or(Halt::PyError("os.path.relpath failed"))?;
    let kind = match lex::family(&ext) {
        Some(fam) => Kind::Comment(fam),
        None if docs::doc_class(&rel)?.is_some() => Kind::Doc,
        None => return Ok(None),
    };
    if cfg.excluded(path, &rel)? {
        return Ok(None);
    }
    Ok(Some(Target {
        cfg,
        rel,
        kind,
        ext,
    }))
}

/// python `file_notice(...)`: 한 파일에서 추가한 줄의 알림 문장들과, 상태를 바꿨는가.
///
/// 이번에 추가하지 않은 줄의 문제는 Stop 보고용으로 쌓는다. 새로 알릴 것이 없으면 빈 목록이다.
/// `tail` 이 거짓이면 주석 알림 끝의 대응 문장을 뺀다(여러 파일을 한 알림에 담는 쪽이 한 번만 붙인다).
pub fn file_notice(
    ctx: &Context,
    input: &HookInput,
    e: &Edit<'_>,
    st: &mut Dict,
    tail: bool,
) -> Result<(Vec<String>, bool)> {
    let t = e.target;
    let pats = t.cfg.patterns()?;
    let lang = Lang::of_ext(&t.ext)
        .filter(|_| matches!(t.kind, Kind::Comment(_)) && ctx.is_on("HARNESS_READABLE_CODE"));
    let rows = match t.kind {
        Kind::Comment(fam) => Some(lex::lex(e.text, fam, lang.is_some())),
        Kind::Doc => None,
    };
    record_leftovers(ctx, input, e, rows.as_deref(), &pats);
    if e.added.is_empty() {
        return Ok((Vec::new(), false));
    }

    // Added-line checks
    let mut cache = SiblingCache::default();
    let (problems, expected, doc_det) = added_problems(e, rows.as_deref(), &pats, &mut cache)?;

    // Layout of the functions this edit wrote or grew
    let key = abspath(e.path).ok_or(Halt::PyError("os.path.abspath failed"))?;
    let (recheck, shapes) = match (lang, rows.as_deref()) {
        (Some(lang), Some(rows)) => layout_step(st, &key, e, rows, lang),
        _ => (Vec::new(), Vec::new()),
    };
    if problems.is_empty() && shapes.is_empty() && recheck.is_empty() {
        return Ok((Vec::new(), false));
    }

    // One notice per (file, category); layout per (file, category, function)
    let seen: Vec<Value> = match state::section(st, "files").get(&key) {
        Some(Value::List(items)) => items.clone(),
        _ => Vec::new(),
    };
    let was_seen = |name: &str| seen.iter().any(|v| v.as_str() == Some(name));
    let fresh: Vec<(usize, Category)> = problems
        .into_iter()
        .filter(|(_, c)| !was_seen(c.as_str()))
        .collect();
    let fresh_shapes: Vec<Shape> = shapes
        .into_iter()
        .filter(|s| s.again || !was_seen(&shape_key(s)))
        .collect();

    // Remember notices and doc rechecks
    let mut now = seen.clone();
    for (_, c) in &fresh {
        if !now[seen.len()..]
            .iter()
            .any(|v| v.as_str() == Some(c.as_str()))
        {
            now.push(Value::Str(c.as_str().to_owned()));
        }
    }
    now.extend(
        fresh_shapes
            .iter()
            .filter(|s| !s.again)
            .map(|s| Value::Str(shape_key(s))),
    );
    state::section(st, "files").insert(key.as_str(), Value::List(now));
    let docs: Vec<Value> = fresh_shapes
        .iter()
        .filter(|s| s.category == Finding::DocSummary && !s.again)
        .map(|s| Value::Str(s.key.clone()))
        .collect();
    let recheck_section = state::section(st, "doc_recheck");
    if docs.is_empty() {
        recheck_section.remove(&key);
    } else {
        recheck_section.insert(key.as_str(), Value::List(docs));
    }
    let dirty = !fresh.is_empty() || !fresh_shapes.is_empty() || !recheck.is_empty();

    // Notice text
    let mut body = Vec::new();
    if let Some(sentence) = comment_sentence(e, &fresh, expected, &doc_det, tail)? {
        body.push(sentence);
    }
    if let (false, Some(lang)) = (fresh_shapes.is_empty(), lang) {
        let mut ordered = fresh_shapes;
        ordered.sort_by_key(|s| s.category);
        let items: Vec<(Finding, String, bool)> = ordered
            .into_iter()
            .map(|s| (s.category, s.desc, s.again))
            .collect();
        body.push(format!(
            "{} layout (readable-code): {}",
            t.rel,
            layout::notice(&items, lang)
        ));
    }
    Ok((body, dirty))
}

fn shape_key(s: &Shape) -> String {
    format!("{}|{}", s.category.as_str(), s.key)
}

// 추가한 줄의 (줄, 범주)들, 주석이 따를 문자 체계, 모델용 문서의 범주별 고치는 법
type Problems = (
    Vec<(usize, Category)>,
    Option<Script>,
    Vec<(Category, String)>,
);

fn added_problems(
    e: &Edit<'_>,
    rows: Option<&[Row]>,
    pats: &Patterns,
    cache: &mut SiblingCache,
) -> Result<Problems> {
    let t = e.target;
    let (mut problems, mut expected, mut det) = (Vec::new(), None, Vec::new());
    match rows {
        Some(rows) => {
            problems.extend(history::check_lines(rows, e.added, pats, &t.cfg)?);
            let lines: Vec<&str> = e.text.split('\n').collect();
            let labels = lang::step_labels(rows, &lines, &t.cfg);
            expected = lang::expected_script(rows, e.added, &t.cfg, e.path, &t.ext, &labels, cache);
            if let Some(exp) = expected {
                problems.extend(
                    lang::language_lines(rows, e.added, exp, &labels)
                        .into_iter()
                        .map(|ln| (ln, Category::Language)),
                );
            }
        }
        None => {
            problems.extend(docs::doc_check(e.text, e.added, &t.rel, pats)?);
            let (shape, d) = docs::doc_shape(e.text, e.added, e.path, &t.rel, pats)?;
            problems.extend(shape);
            det = d;
        }
    }
    problems.extend(
        chars::invisible_lines(e.text, e.added)
            .into_iter()
            .map(|ln| (ln, Category::Invisible)),
    );
    Ok((problems, expected, det))
}

// python layout_step: (다시 볼 함수 키, layout 알림). 지표 코드가 실패하면 둘 다 빈 목록이다
fn layout_step(
    st: &mut Dict,
    key: &str,
    e: &Edit<'_>,
    rows: &[Row],
    lang: Lang,
) -> (Vec<String>, Vec<Shape>) {
    let recheck: Vec<String> = match state::section(st, "doc_recheck").get(key) {
        Some(Value::List(items)) => items
            .iter()
            .filter_map(|v| v.as_str().map(str::to_owned))
            .collect(),
        _ => Vec::new(),
    };
    let limits = Limits::from_user(e.target.cfg.get("layout"));
    match layout::edit_findings(e.text, rows, e.added, lang, &limits, &recheck) {
        Some(shapes) => (recheck, shapes),
        None => (Vec::new(), Vec::new()),
    }
}

// 주석이나 모델용 문서 알림 문장 하나(범주 순서대로 줄과 고치는 법)
fn comment_sentence(
    e: &Edit<'_>,
    fresh: &[(usize, Category)],
    expected: Option<Script>,
    det: &[(Category, String)],
    tail: bool,
) -> Result<Option<String>> {
    let t = e.target;
    let is_comment = matches!(t.kind, Kind::Comment(_));
    let mut parts = Vec::new();
    for cat in Category::ORDER {
        let mut lns: Vec<usize> = fresh
            .iter()
            .filter(|(_, c)| *c == cat)
            .map(|(ln, _)| *ln)
            .collect();
        lns.sort_unstable();
        lns.dedup();
        if lns.is_empty() {
            continue;
        }
        let detail = match cat {
            Category::Symbol => chars::symbol_detail(e.text, &lns, &t.cfg.allow()?),
            Category::Invisible => chars::invisible_detail(e.text, &lns),
            Category::Escape => chars::escape_detail(e.text, &lns),
            Category::Language if is_comment && expected.is_some() => {
                format!(
                    "write it in {} like the file's other comments",
                    expected.map_or("", Script::language)
                )
            }
            _ if is_comment => cat.comment_hint().to_owned(),
            _ => det
                .iter()
                .find(|(c, _)| *c == cat)
                .map(|(_, d)| d.clone())
                .filter(|d| !d.is_empty())
                .unwrap_or_else(|| docs::doc_hint(cat).to_owned()),
        };
        let mut part = format!("{} {}", line_list(&lns), cat.as_str());
        if !detail.is_empty() {
            part.push_str(": ");
            part.push_str(&detail);
        }
        parts.push(part);
    }
    if parts.is_empty() {
        return Ok(None);
    }
    let what = if is_comment { "comment" } else { "agent-doc" };
    let end = if tail {
        format!(" {}", t.tail())
    } else {
        String::new()
    };
    Ok(Some(format!(
        "{} may not follow the {what} conventions. {}.{end}",
        t.rel,
        parts.join("; ")
    )))
}

// python record_leftovers: 이번에 추가하지 않은 줄의 문제를 범주별로 센다. 어떤 실패도 넘긴다(python 은 예외를 모두 잡는다)
fn record_leftovers(
    ctx: &Context,
    input: &HookInput,
    e: &Edit<'_>,
    rows: Option<&[Row]>,
    pats: &Patterns,
) {
    let _ = (|| -> Result<()> {
        let t = e.target;
        let lines = e.text.bytes().filter(|&b| b == b'\n').count() + 1;
        let old: Added = (0..lines).filter(|i| !e.added.contains(i)).collect();
        let mut probs = match rows {
            Some(rows) => history::check_lines(rows, &old, pats, &t.cfg)?,
            None => docs::doc_check(e.text, &old, &t.rel, pats)?,
        };
        probs.extend(
            chars::invisible_lines(e.text, &old)
                .into_iter()
                .map(|ln| (ln, Category::Invisible)),
        );

        let dir = leftovers::left_dir(ctx.tempdir()?)?;
        let sid = pyval::sanitized_id(input.get("session_id"));
        let who = match pyval::truthy_text(input.get("agent_id")) {
            Some(agent) => harness_hook::epoch::sanitize(&agent),
            None => "main".to_owned(),
        };
        let key = abspath(e.path).ok_or(Halt::PyError("abspath failed"))?;
        leftovers::record(
            &dir,
            &sid,
            &who,
            &key,
            &t.rel,
            &probs,
            harness_hook::nonce::now_secs(),
        );
        Ok(())
    })();
}

/// python `line_list(lines)`: 줄 번호를 이어진 범위로 묶은 글.
///
/// 숫자가 상한을 넘으면 남은 줄은 `(+N more)` 로 센다.
pub fn line_list(lines: &[usize]) -> String {
    let mut nums = lines.to_vec();
    nums.sort_unstable();
    nums.dedup();
    let mut runs: Vec<(usize, usize)> = Vec::new();
    for n in &nums {
        match runs.last_mut() {
            Some(last) if *n == last.1 + 1 => last.1 = *n,
            _ => runs.push((*n, *n)),
        }
    }

    let (mut parts, mut used, mut covered) = (Vec::new(), 0, 0);
    for (a, b) in runs {
        let cost = if a == b { 1 } else { 2 };
        if used + cost > LINE_LIST_MAX {
            break;
        }
        parts.push(if a == b {
            format!("L{a}")
        } else {
            format!("L{a}-{b}")
        });
        used += cost;
        covered += b - a + 1;
    }
    let rest = nums.len() - covered;
    let more = if rest > 0 {
        format!(" (+{rest} more)")
    } else {
        String::new()
    };
    format!("{}{more}", parts.join(", "))
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 이어진 줄은 범위로 묶고, 숫자 40개를 넘는 줄은 수로만 센다.
    #[test]
    fn line_list_groups_runs() {
        // Runs and singles
        assert_eq!(line_list(&[12, 13, 14, 40, 3]), "L3, L12-14, L40");

        // 한 줄씩 건너뛴 줄은 숫자 하나씩이라 40개까지 찍고 나머지 10개는 센다
        let many: Vec<usize> = (1..=50).map(|i| i * 2).collect();
        assert!(line_list(&many).ends_with("L80 (+10 more)"));
    }
}
