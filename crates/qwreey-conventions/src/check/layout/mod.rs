//! readable-code 의 layout 알림(python `hooks/layout_metrics.py` 의 편집 알림 부분).
//!
//! 이번 편집이 새로 쓰거나(함수 줄의 절반 이상) grow 줄 이상 키운 함수의 빈 줄 없는 긴 본문, 끼운 여러 줄 주석,
//! 호출하는 쪽이 못 보는 문서 주석을 알린다. 입력은 [`crate::lex::lex`] 의 `keep_code` 줄 목록이다.

pub mod functions;
pub mod metrics;

use std::collections::HashMap;

use harness_hook::py::text::strip;
use harness_hook::py::value::Value;

use crate::edit::Added;
use crate::lex::Row;
pub use metrics::Finding;
use metrics::TEST_MARK;

/// layout 을 재는 언어(python `LANG_BY_EXT` 의 값).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Lang {
    Lua,
    Py,
    Ts,
    Rust,
    Go,
    Kt,
}

impl Lang {
    /// 확장자(소문자) -> 언어(python `LANG_BY_EXT.get(ext)`).
    pub fn of_ext(ext: &str) -> Option<Lang> {
        Some(match ext {
            ".luau" | ".lua" => Lang::Lua,
            ".py" => Lang::Py,
            ".ts" | ".tsx" | ".js" | ".jsx" | ".mjs" => Lang::Ts,
            ".rs" => Lang::Rust,
            ".go" => Lang::Go,
            ".kt" => Lang::Kt,
            _ => return None,
        })
    }

    /// 편집기 호버와 자동완성이 보여 주는 문서 주석의 꼴(python `DOC_FORM`).
    fn doc_form(self) -> &'static str {
        match self {
            Lang::Lua => {
                "a `---` doc comment (luau-lsp shows only `---` and `--[=[ ]=]` on hover and completion, never `--`)"
            }
            Lang::Py => "a docstring (`#` comments above the def are not shown on hover)",
            Lang::Ts => "a `/** */` JSDoc comment (`//` is not shown on hover)",
            Lang::Rust => "a `///` doc comment (`//` is not shown on hover)",
            Lang::Go => "a `//` doc comment directly above the func, starting with its name",
            Lang::Kt => "a `/** */` KDoc comment (`//` is not shown on hover)",
        }
    }

    /// 시험 함수가 따를 문서 꼴(python `TEST_FORM`). 시험은 Rust 만 가린다.
    fn test_form(self) -> &'static str {
        match self {
            Lang::Rust => "a one-line `///` doc comment",
            _ => "a one-line doc comment",
        }
    }
}

/// 알림 기준(python `DEFAULT_LAYOUT` 에 저장소 conventions.json 의 `layout` 숫자 값을 덮은 것).
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct Limits {
    pub min_lines: f64,
    pub max_run: f64,
    pub doc_first_max: f64,
    pub grow: f64,
    pub mostly: f64,
}

impl Limits {
    /// python `limits(user)`: 숫자(bool 제외)인 값만 덮는다.
    pub fn from_user(user: Option<&Value>) -> Limits {
        let mut lim = Limits {
            min_lines: 15.0,
            max_run: 20.0,
            doc_first_max: 100.0,
            grow: 15.0,
            mostly: 0.5,
        };
        let Some(Value::Dict(user)) = user else {
            return lim;
        };
        for (k, v) in user.iter() {
            let n = match v {
                Value::Int(i) => *i as f64,
                Value::Float(f) => *f,
                Value::BigInt(digits) => digits.parse::<f64>().unwrap_or(f64::NAN),
                _ => continue,
            };
            match k {
                "min_lines" => lim.min_lines = n,
                "max_run" => lim.max_run = n,
                "doc_first_max" => lim.doc_first_max = n,
                "grow" => lim.grow = n,
                "mostly" => lim.mostly = n,
                _ => {}
            }
        }
        lim
    }
}

/// 편집 알림 하나(python `edit_findings` 의 튜플).
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Shape {
    pub category: Finding,
    /// 함수 키(이름, 같은 이름의 두 번째부터 `이름#2`).
    pub key: String,
    pub desc: String,
    /// 지난 편집에서 알린 doc summary 를 다시 본 것인가.
    pub again: bool,
}

/// python `edit_findings(text, rows, added, lang, user_limits, recheck)`: 이번 편집이 쓰거나 키운 함수의 알림.
///
/// 거의 새로 쓴 함수와 grow 줄 이상 키운 함수는 모든 범주를, recheck 키의 함수는 doc summary 만 본다.
/// 줄 범위가 틀리면 `None`(python 은 예외를 잡아 layout 알림을 모두 버린다).
pub fn edit_findings(
    text: &str,
    rows: &[Row],
    added: &Added,
    lang: Lang,
    lim: &Limits,
    recheck: &[String],
) -> Option<Vec<Shape>> {
    let lines: Vec<&str> = text.split('\n').collect();
    let found = functions::functions(rows, &lines, lang)?;
    let mut out = Vec::new();
    for (f, key) in found.iter().zip(fn_keys(&found)) {
        // How much of the function this edit wrote
        let span: Vec<usize> = (f.start..=f.last)
            .filter(|&ln| lines.get(ln).is_some_and(|l| !strip(l).is_empty()))
            .collect();
        let new = span.iter().filter(|ln| added.contains(ln)).count();
        let wrote = !span.is_empty() && new as f64 >= lim.mostly * span.len() as f64;
        let grew = new as f64 >= lim.grow;
        let again = recheck.contains(&key);
        if !(wrote || grew || again) {
            continue;
        }

        // Categories this function hits
        let m = metrics::measure(rows, &lines, f, lang)?;
        let tag = if grew && !wrote {
            format!(" [grown by {new} lines]")
        } else {
            String::new()
        };
        for (category, desc) in metrics::findings(&m, lim) {
            if !(wrote || grew) && category != Finding::DocSummary {
                continue;
            }
            out.push(Shape {
                category,
                key: key.clone(),
                desc: desc + &tag,
                again: again && category == Finding::DocSummary,
            });
        }
    }
    Some(out)
}

/// python `fn_keys(fns)`: 함수마다 알림 중복 제거와 다시 보기에 쓰는 키.
fn fn_keys(fns: &[functions::Function]) -> Vec<String> {
    let mut seen: HashMap<&str, usize> = HashMap::new();
    fns.iter()
        .map(|f| {
            let n = seen.entry(f.name.as_str()).or_insert(0);
            *n += 1;
            if *n == 1 {
                f.name.clone()
            } else {
                format!("{}#{n}", f.name)
            }
        })
        .collect()
}

/// 범주당 이름을 대는 함수 수(python `LIST_MAX`). 나머지는 수만 센다.
const LIST_MAX: usize = 8;

/// python `notice(items, lang)`: 알림 한 줄의 layout 부분. `items` 는 (범주, 설명, 다시 본 것인가).
pub fn notice(items: &[(Finding, String, bool)], lang: Lang) -> String {
    // Doc summaries that name tests, counted before the list is cut
    let docs: Vec<&String> = items
        .iter()
        .filter(|(cat, _, _)| *cat == Finding::DocSummary)
        .map(|(_, desc, _)| desc)
        .collect();
    let tests = docs.iter().filter(|d| d.contains(TEST_MARK)).count();

    // Descriptions per category, in first-seen order
    let mut by: Vec<(Finding, Vec<String>)> = Vec::new();
    for (cat, desc, again) in items {
        let text = if *again {
            format!("{desc} (still so after your last edit)")
        } else {
            desc.clone()
        };
        match by.iter_mut().find(|(c, _)| c == cat) {
            Some((_, list)) => list.push(text),
            None => by.push((*cat, vec![text])),
        }
    }
    for (_, descs) in &mut by {
        if descs.len() > LIST_MAX {
            let more = descs.len() - LIST_MAX;
            descs.truncate(LIST_MAX);
            descs.push(format!("{more} more"));
        }
    }
    let get = |cat: Finding| {
        by.iter()
            .find(|(c, _)| *c == cat)
            .map(|(_, d)| d.join("; "))
    };

    // One sentence group per category
    let mut parts = Vec::new();
    if let Some(list) = get(Finding::Layout) {
        parts.push(format!(
            "Functions you wrote or grew read as one block: {list}. Hand-written functions of this size have about 4 paragraphs and runs under 13 lines. If a function has steps, separate them with blank lines and short step labels; if it is one step (a literal, one expression), leave it."
        ));
    }
    if let Some(list) = get(Finding::Interleaved) {
        parts.push(format!(
            "Multi-line comments between statements: {list}. Move a design reason above the declaration, apart from the doc comment, or cut it to one line at the trap."
        ));
    }
    if let Some(list) = get(Finding::DocSummary) {
        let mut text = format!("Doc comments: {list}.");
        if tests < docs.len() {
            text += &format!(
                " Public functions in code others call get {} whose first sentence ends on the first line, about 80 characters.",
                lang.doc_form()
            );
        }
        if tests > 0 {
            text += &format!(
                " Each test gets {} saying the one behavior it checks; a line that needs \"and\" means two tests.",
                lang.test_form()
            );
        }
        parts.push(text);
    }
    format!(
        "{} These numbers are evidence, not a verdict; a repo's own rules win.",
        parts.join(" ")
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    fn doc(desc: &str) -> (Finding, String, bool) {
        (Finding::DocSummary, desc.to_owned(), false)
    }

    /// 시험만 걸린 doc summary 는 공개 함수 문장 없이 시험 문장을 단다.
    #[test]
    fn test_only_doc_notice_names_the_test_form() {
        let text = notice(&[doc("a L3 is a test with no doc comment")], Lang::Rust);
        assert!(text.starts_with(
            "Doc comments: a L3 is a test with no doc comment. Each test gets a one-line `///` doc comment"
        ));
        assert!(!text.contains("Public functions"));
    }

    /// 공개 함수와 시험이 함께 걸리면 두 문장을 모두 단다.
    #[test]
    fn mixed_doc_notice_has_both_sentences() {
        let items = [
            doc("f L1 has no doc comment"),
            doc("a L3 is a test with no doc comment"),
        ];
        let text = notice(&items, Lang::Rust);
        assert!(text.contains("Public functions in code others call get a `///` doc comment"));
        assert!(text.contains("Each test gets a one-line `///` doc comment"));
    }
}
