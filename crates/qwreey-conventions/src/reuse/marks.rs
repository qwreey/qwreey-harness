//! 표시 자리와 꼴(M1, python reuse-check 의 `marker_notes`, `comment_kinds`, `json_marker_note`).
//!
//! 표시는 줄 주석에 둔다. 문서 주석(Rust `///`, `/** */`, Luau `---` 와 `--[=[ ]=]`)은 문서 도구가 싣거나 태그로 읽고,
//! 영역 표시는 [`crate::reuse::regions::MARK`] 꼴의 줄만 읽힌다. 형제 저장소는 `@copy-of` 가 `<저장소>:<경로>`,
//! `@start-replace` 가 `../<저장소>/<경로>` 다. 열 위치는 바이트다(렉서와 정규식이 모두 바이트를 준다).

use std::sync::LazyLock;

use harness_hook::py::re::Regex;
use harness_hook::py::text::is_space;

use crate::edit::Added;
use crate::lex::{Family, lex};
use crate::reuse::regions::MARK;
use crate::reuse::sets::{COPY, HEADER_LINES};

fn compiled(pattern: &str) -> Regex {
    Regex::new(pattern).expect("constant pattern")
}

static MARK_WORD: LazyLock<Regex> =
    LazyLock::new(|| compiled(r"@(copy-of|start-replace|end-replace)(?![\w-])"));
static REGION_PATH: LazyLock<Regex> =
    LazyLock::new(|| compiled(r"@start-replace:[ \t]*([^\s#]+)#"));
static MIXED_COPY: LazyLock<Regex> = LazyLock::new(|| compiled(r"^\.\./([\w.-]+):([^/\\].*)$"));
static COLON_REGION: LazyLock<Regex> =
    LazyLock::new(|| compiled(r"^(?:\.\./)?([\w.-]+):([^/\\].*)$"));
static LUA_OPENER: LazyLock<Regex> = LazyLock::new(|| compiled(r"--\[(=*)\[$"));
static OPENER_AT_END: LazyLock<Regex> = LazyLock::new(|| compiled(r"(?:--\[=*\[|/\*|<!--)$"));
static CLOSER: LazyLock<Regex> = LazyLock::new(|| compiled(r"\*/|\]=*\]|-->"));

/// 주석 조각의 종류(python 의 `line`, `docline`, `block`, `doc`, `html`).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Kind {
    Line,
    DocLine,
    Block,
    Doc,
    Html,
}

impl Kind {
    // python BLOCKISH: 줄 끝까지 열린 채 다음 줄로 잇는 종류
    fn blockish(self) -> bool {
        matches!(self, Kind::Block | Kind::Doc | Kind::Html)
    }
}

/// python `opener_kind(prefix, seg, fam)`: `prefix` 는 조각 앞 글(여는 표식으로 끝난다), `seg` 는 조각 본문.
fn opener_kind(prefix: &str, seg: &str, fam: Family) -> Kind {
    if prefix.ends_with("<!--") {
        return Kind::Html;
    }

    // Luau: long brackets are blocks, `---` is a doc line
    if fam == Family::Lua {
        if let Some(m) = LUA_OPENER.search(prefix) {
            return if m.text(prefix, 1).is_some_and(|eq| !eq.is_empty()) {
                Kind::Doc
            } else {
                Kind::Block
            };
        }
        return if seg.starts_with('-') && !seg.starts_with("--") {
            Kind::DocLine
        } else {
            Kind::Line
        };
    }

    // C family: `/**` and Rust `/*!` are doc blocks, Rust `///` a doc line
    if prefix.ends_with("/*") {
        let doc = (seg.starts_with('*') && !seg.starts_with("*/"))
            || (fam == Family::Rust && seg.starts_with('!'));
        return if doc { Kind::Doc } else { Kind::Block };
    }
    if fam == Family::Rust
        && prefix.ends_with("//")
        && seg.starts_with('/')
        && !seg.starts_with("//")
    {
        return Kind::DocLine;
    }
    Kind::Line
}

/// python `comment_kinds(text, fam)`: 줄마다 `(시작, 끝, 종류)`. 줄 끝까지 열린 블록의 종류는 다음 줄로 잇는다.
fn comment_kinds(text: &str, fam: Family) -> Vec<Vec<(usize, usize, Kind)>> {
    let rows = lex(text, fam, true);
    let mut out = Vec::new();
    let mut carry: Option<Kind> = None;
    for (k, s) in text.split('\n').enumerate() {
        let segs: Vec<(usize, usize, Kind)> = rows[k]
            .s
            .iter()
            .map(|&(a, b)| {
                let kind = match carry {
                    Some(c) if a == 0 => c,
                    _ => opener_kind(&s[..a], &s[a..b], fam),
                };
                (a, b, kind)
            })
            .collect();

        // What the next line inherits
        match segs.last() {
            Some(&(_, b, kind)) if b == s.len() => carry = kind.blockish().then_some(kind),
            _ if k + 1 < rows.len() && rows[k + 1].inside && OPENER_AT_END.is_match(s) => {
                // 여는 표식이 줄 끝이면 조각이 없다
                carry = Some(opener_kind(s, "", fam));
            }
            // 빈 줄은 열린 블록을 잇는다
            _ if !segs.is_empty() || !rows[k].inside => carry = None,
            _ => {}
        }
        out.push(segs);
    }
    out
}

// python mark_text(s, p): p 에서 시작하는 표시 글, 닫는 주석 표식 앞까지
fn mark_text(s: &str) -> &str {
    let end = CLOSER.search(s).map_or(s.len(), |m| m.start());
    s[..end].trim_end_matches(is_space)
}

fn line_comment(text: &str, fam: Family) -> String {
    let head = match fam {
        Family::Lua => "--",
        Family::Py => "#",
        _ => "//",
    };
    format!("{head} {text}")
}

/// python `marker_notes(rel, ext, text, added)`: 추가한 줄의 표시가 읽히지 않거나 문서에 실리는 자리, 섞인 형제 저장소 꼴.
pub fn marker_notes(rel: &str, fam: Family, text: &str, added: &Added) -> Vec<(usize, String)> {
    let lines: Vec<&str> = text.split('\n').collect();
    let todo: Vec<usize> = added
        .iter()
        .copied()
        .filter(|&i| i < lines.len() && MARK_WORD.is_match(lines[i]))
        .collect();
    if todo.is_empty() {
        return Vec::new();
    }

    let kinds = comment_kinds(text, fam);
    todo.into_iter()
        .filter_map(|i| marker_note(rel, fam, lines[i], i, &kinds[i]).map(|n| (i + 1, n)))
        .collect()
}

// 줄 하나의 M1 알림
fn marker_note(
    rel: &str,
    fam: Family,
    s: &str,
    i: usize,
    kinds: &[(usize, usize, Kind)],
) -> Option<String> {
    let m = MARK_WORD.search(s)?;
    let mk = format!("@{}", m.text(s, 1).unwrap_or(""));
    let p = m.start();
    let ln = i + 1;

    // Outside any comment: only a python docstring past the header
    let Some(&(a, _, kind)) = kinds.iter().find(|&&(a, b, _)| a <= p && p <= b) else {
        let bare = s
            .trim_start_matches(is_space)
            .trim_start_matches(['r', 'R', 'b', 'B', 'u', 'U'])
            .trim_start_matches(['"', '\''])
            .trim_start_matches(is_space);
        let read = mk != "@copy-of" || COPY.match_start(bare).is_some();
        if fam == Family::Py && i >= HEADER_LINES && bare.starts_with(&mk) && read {
            return Some(format!(
                "{rel}:{ln}: the {mk} marker is inside a docstring past the first 10 lines, where it is not read. \
                 Put it in a line comment above the copied lines: `{}`.",
                line_comment(mark_text(bare), fam)
            ));
        }
        return None;
    };

    // 주석 글 중간에 든 이름(설명, 인용한 예)은 표시가 아니다
    let decor: &[char] = if kind.blockish() {
        &[' ', '\t', '*', '!']
    } else {
        &[' ', '\t', '/', '!', '-']
    };
    if !s[a..p].trim_matches(decor).is_empty() {
        return None;
    }
    let copy_at = COPY.match_start(&s[p..]);
    if mk == "@copy-of" && copy_at.is_none() {
        return None;
    }
    let body = mark_text(&s[p..]);
    let fix = line_comment(body, fam);

    // Doc comments and HTML comments
    if matches!(kind, Kind::Doc | Kind::DocLine) {
        return Some(format!(
            "{rel}:{ln}: the {mk} marker is in a doc comment, which documentation tools publish or read as a doc tag. \
             Move it to a plain line comment: `{fix}`."
        ));
    }
    if kind == Kind::Html && mk == "@copy-of" {
        return Some(format!(
            "{rel}:{ln}: the @copy-of marker is in an HTML comment, which can reach the built page. \
             In an Astro template write `{{/* {body} */}}`; in the frontmatter or a script, `{fix}`."
        ));
    }

    // Region markers not on a line of their own
    if mk != "@copy-of" && MARK.match_start(s).is_none() {
        return Some(format!(
            "{rel}:{ln}: this {mk} is not read as a region marker: a region marker sits alone on a line comment \
             (`#`, `//`, `--`), e.g. `{fix}`."
        ));
    }

    // Mixed sibling-repo forms
    if let Some(c) = copy_at {
        let tgt = c
            .text(&s[p..], 1)
            .unwrap_or("")
            .trim_end_matches(['.', ',', ';', ')', '*', '/', '}']);
        let mm = MIXED_COPY.match_start(tgt)?;
        return Some(format!(
            "{rel}:{ln}: @copy-of {tgt} mixes the two sibling-repo forms. @copy-of names a sibling repo as \
             `<repo>:<path>` (`{}:{}`); `../<repo>/<path>` is the @start-replace form.",
            mm.text(tgt, 1).unwrap_or(""),
            mm.text(tgt, 2).unwrap_or("")
        ));
    }
    if mk == "@start-replace" {
        let rp = REGION_PATH.search_from(s, p)?;
        let path = rp.text(s, 1).unwrap_or("");
        let mm = COLON_REGION.match_start(path)?;
        return Some(format!(
            "{rel}:{ln}: @start-replace {path} uses the `<repo>:<path>` form, which only @copy-of reads. \
             A region names a sibling repo by its path from this repo's root: `../{}/{}`.",
            mm.text(path, 1).unwrap_or(""),
            mm.text(path, 2).unwrap_or("")
        ));
    }
    None
}

/// python `json_marker_note(rel, text, added)`: JSON 에는 표시를 둘 주석이 없다. 첫 줄 하나만 알린다.
pub fn json_marker_note(rel: &str, text: &str, added: &Added) -> Option<String> {
    let lines: Vec<&str> = text.split('\n').collect();
    let i = added.iter().copied().find(|&i| {
        i < lines.len() && (COPY.is_match(lines[i]) || lines[i].contains("@start-replace:"))
    })?;
    Some(format!(
        "{rel}:{}: JSON cannot hold a copy marker, and nothing reads one here. Drop it and name the source \
         in the code that reads this file or in the test that compares it with the source.",
        i + 1
    ))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn notes(fam: Family, text: &str) -> Vec<String> {
        let added: Added = (0..text.split('\n').count()).collect();
        marker_notes("f", fam, text, &added)
            .into_iter()
            .map(|(_, n)| n)
            .collect()
    }

    /// 문서 주석의 표시는 알리고, 줄 주석과 주석 글 중간의 이름은 조용하다.
    #[test]
    fn doc_comments_are_flagged() {
        // Luau --- and --[=[ ]=] are doc comments
        assert!(
            notes(Family::Lua, "--- @copy-of: a.luau#F\n")[0].contains("`-- @copy-of: a.luau#F`")
        );
        assert!(
            notes(Family::Lua, "--[=[\n\t@copy-of: a.luau#F\n]=]\n")[0]
                .starts_with("f:2: the @copy-of marker is in a doc comment")
        );

        // A plain line comment and prose inside a doc block are fine
        assert!(notes(Family::Lua, "-- @copy-of: a.luau#F\n").is_empty());
        assert!(
            notes(
                Family::C,
                "/**\n * The `@copy-of:` marker goes above.\n */\n"
            )
            .is_empty()
        );

        // A JSDoc one-liner drops the closer from the fix
        assert!(
            notes(Family::C, "/** @copy-of: m/a.ts#K */\n")[0].contains("`// @copy-of: m/a.ts#K`")
        );
    }

    /// 형제 저장소 꼴이 섞이면 고칠 꼴을 알린다.
    #[test]
    fn sibling_forms() {
        assert!(
            notes(Family::Lua, "-- @copy-of: ../other:src/x.luau#F\n")[0]
                .contains("(`other:src/x.luau#F`)")
        );
        assert!(
            notes(Family::Py, "# @start-replace: other:lib/t.py#O\n")[0]
                .contains("`../other/lib/t.py`")
        );
        assert!(notes(Family::Py, "# @start-replace: ../other/lib/t.py#O\n").is_empty());
    }
}
