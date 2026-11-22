//! 가장 바깥 함수 찾기(python `layout_metrics.functions`). 안쪽 콜백과 지역 함수는 바깥 함수 본문에 든다.
//!
//! - Lua: `function`/`do`/`then`/`repeat` 와 `end`/`until` 의 짝. Luau 의 `if` 식은 `end` 가 없어 쌓지 않는다.
//! - Python: `def` 줄과 들여쓰기. 클래스는 함수가 아니라서 메서드가 따로 잡힌다.
//! - C 계열(ts, js, rs, go, kt): 함수 머리 뒤 첫 `{` 와 그 짝 `}`.

use std::sync::LazyLock;

use harness_hook::py::text::{is_space, strip};
use harness_hook::rx::Regex;

use super::Lang;
use crate::check::chars::is_upper;
use crate::lex::Row;

fn constant(pattern: &str) -> Regex {
    Regex::new(pattern)
}

static LUA_TOKEN: LazyLock<Regex> =
    LazyLock::new(|| constant(r"[A-Za-z_]\w*|\.\.\.?=?|[=~<>]=|//=?|[-+*/%^]=|->|::|\S"));
static LUA_NAME: LazyLock<Regex> =
    LazyLock::new(|| constant(r#"function\s+([\w.:]+)\s*[(<]|([\w.:\[\]"]+)\s*=\s*function\b"#));
static LUA_PUBLIC: LazyLock<Regex> = LazyLock::new(|| {
    constant(
        r"^\s*function\s+[A-Za-z_]\w*(?:\.\w+)*[.:]\w+|^\s*[A-Za-z_]\w*(?:\.\w+)+\s*=\s*function\b",
    )
});
static METAMETHOD: LazyLock<Regex> = LazyLock::new(|| constant(r"(?:^|[.:])__\w+$"));
static C_TOKEN: LazyLock<Regex> = LazyLock::new(|| constant(r"[A-Za-z_$][\w$]*|=>|->|::|\S"));
static C_METHOD: LazyLock<Regex> = LazyLock::new(|| {
    constant(
        r"^\s*(?:(?:public|private|protected|static|async|override|readonly|abstract|export|default|get|set)\s+)*\*?\s*([A-Za-z_$#][\w$]*)\s*(?:<[^>]*>)?\s*\(",
    )
});
static C_NAMES: LazyLock<[Regex; 6]> = LazyLock::new(|| {
    [
        constant(r"\bfunction\s*\*?\s*([\w$]+)"),
        constant(r"\bfn\s+(\w+)"),
        constant(r"\bfunc\s*(?:\([^)]*\)\s*)?(\w+)"),
        constant(r"\bfun\s+(?:<[^>]*>\s*)?(?:[\w.]+\.)?(\w+)"),
        constant(r"\b(?:const|let|var)\s+([\w$]+)\s*(?::[^=]*)?="),
        constant(r"([\w$]+)\s*[:=]\s*(?:async\s*)?(?:function|\()"),
    ]
});
static KT_PRIVATE: LazyLock<Regex> =
    LazyLock::new(|| constant(r"\b(?:private|protected|internal)\b"));
static TS_EXPORT: LazyLock<Regex> = LazyLock::new(|| constant(r"\bexport\b"));
static RUST_PUB: LazyLock<Regex> = LazyLock::new(|| constant(r"\bpub\b"));
/// 함수 머리 위의 속성이나 데코레이터 줄(`#[...]`, `@x`). 문서 주석은 그 위에 있어도 된다.
pub(super) static ATTRIBUTE: LazyLock<Regex> = LazyLock::new(|| constant(r"^\s*(?:#\[|@)"));
/// Rust 시험 속성: `#[test]`, `#[tokio::test]`, `#[tokio::test(flavor = "...")]`. `#[cfg(test)]` 는 시험이 아니다.
static RUST_TEST: LazyLock<Regex> =
    LazyLock::new(|| constant(r"#\[\s*(?:[A-Za-z_]\w*\s*::\s*)*test\s*[\](]"));
static PY_DEF: LazyLock<Regex> = LazyLock::new(|| constant(r"^\s*(?:async\s+)?def\s+(\w+)"));
static PY_CLASS: LazyLock<Regex> = LazyLock::new(|| constant(r"^\s*class\s+(\w+)"));
static PY_MAIN: LazyLock<Regex> = LazyLock::new(|| constant(r"^if\s+__name__\s*=="));

/// 이 토큰 뒤의 `if` 는 식이라 `end` 가 없다(python `LUA_EXPR_BEFORE`).
const LUA_EXPR_BEFORE: &[&str] = &[
    "=", "(", ",", "{", "[", "return", "and", "or", "not", "elseif", "if", "while", "until", "in",
    "..", "==", "~=", "<=", ">=", "+", "-", "*", "/", "//", "%", "^", "#", "+=", "-=", "*=", "/=",
    "//=", "%=", "^=", "..=",
];
const C_CONTROL: &[&str] = &[
    "if", "for", "while", "switch", "catch", "with", "return", "match", "loop", "else", "do",
    "try", "when", "typeof", "sizeof", "new", "await", "yield", "throw", "case", "super", "this",
    "function",
];
const C_CONTINUES: &[&str] = &["{", "where", "->", ":", ")"];
/// def 머리를 찾아 내려가는 줄 수. 닫히지 않은 괄호가 파일 끝까지 훑지 않게 막는다.
const PY_HEADER_SCAN: usize = 50;

/// 함수 하나(줄은 0 기반). 본문은 `header_end + 1` 부터 `end - 1` 까지, `last` 는 함수의 마지막 줄이다.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Function {
    pub name: String,
    pub start: usize,
    pub header_end: usize,
    pub end: usize,
    pub last: usize,
    pub public: bool,
    pub metamethod: bool,
    /// Rust 시험 함수(`#[test]` 같은 속성이 달린 것).
    pub test: bool,
    indent: usize,
}

/// python `functions(rows, lines, lang)`: 가장 바깥 함수 목록. 줄 수가 맞지 않는 입력이면 `None`(python 은 예외).
pub fn functions(rows: &[Row], lines: &[&str], lang: Lang) -> Option<Vec<Function>> {
    if rows.len() != lines.len() {
        return None;
    }
    Some(match lang {
        Lang::Lua => lua_functions(rows),
        Lang::Py => py_functions(rows, lines),
        _ => c_functions(rows, lang),
    })
}

fn tokens<'t>(rx: &Regex, text: &'t str) -> Vec<&'t str> {
    rx.find_iter(text)
        .iter()
        .map(|m| &text[m.start()..m.end()])
        .collect()
}

fn first_group(rx: &Regex, text: &str) -> Option<String> {
    rx.search(text)
        .and_then(|m| m.text(text, 1).map(str::to_owned))
}

// ---------- Lua ----------

// 블록을 여닫는 토큰마다 (줄, 여는가, function 인가). 반복문 머리의 `do` 와 `if` 식은 뺀다
fn lua_blocks(rows: &[Row]) -> Vec<(usize, bool, bool)> {
    let mut out = Vec::new();
    let mut pending_do = 0usize;
    let mut prev = "";
    let mut prev_ln = usize::MAX;
    for (ln, row) in rows.iter().enumerate() {
        for tok in tokens(&LUA_TOKEN, &row.k) {
            match tok {
                "while" | "for" => {
                    out.push((ln, true, false));
                    pending_do += 1;
                }
                "do" if pending_do > 0 => pending_do -= 1,
                "function" | "repeat" | "do" => out.push((ln, true, tok == "function")),
                "if" if !lua_if_expr(prev, prev_ln == ln) => out.push((ln, true, false)),
                "end" | "until" => out.push((ln, false, false)),
                _ => {}
            }
            prev = tok;
            prev_ln = ln;
        }
    }
    out
}

fn lua_if_expr(prev: &str, same_line: bool) -> bool {
    // `<`, `>` 는 줄 끝에서 제네릭 타입이나 캐스트를 닫는 일이 많아, 같은 줄의 `if` 앞에서만 식으로 본다
    LUA_EXPR_BEFORE.contains(&prev) || (same_line && (prev == "<" || prev == ">"))
}

fn lua_functions(rows: &[Row]) -> Vec<Function> {
    // Pair openers and closers, keep outermost functions
    let mut stack: Vec<(bool, usize)> = Vec::new();
    let mut spans = Vec::new();
    for (ln, open, is_fn) in lua_blocks(rows) {
        if open {
            stack.push((is_fn, ln));
        } else if let Some((true, start)) = stack.pop()
            && !stack.iter().any(|(f, _)| *f)
        {
            spans.push((start, ln));
        }
    }

    // Describe each span
    spans
        .into_iter()
        .map(|(start, end)| {
            let head = &rows[start].k;
            let name = LUA_NAME
                .search(head)
                .and_then(|m| {
                    m.text(head, 1)
                        .or_else(|| m.text(head, 2))
                        .map(str::to_owned)
                })
                .unwrap_or_else(|| "(anonymous)".to_owned());
            Function {
                start,
                header_end: params_end(rows, start, end),
                end,
                last: end,
                public: LUA_PUBLIC.match_start(head).is_some(),
                metamethod: METAMETHOD.is_match(&name),
                test: false,
                name,
                indent: 0,
            }
        })
        .collect()
}

// 머리 줄부터 매개변수 괄호가 닫히는 줄. 못 찾으면 머리 줄
fn params_end(rows: &[Row], start: usize, end: usize) -> usize {
    let mut depth: i64 = 0;
    for (ln, row) in rows.iter().enumerate().take(end + 1).skip(start) {
        for ch in row.k.chars() {
            if ch == '(' {
                depth += 1;
            } else if ch == ')' {
                depth -= 1;
                if depth == 0 {
                    return ln;
                }
            }
        }
    }
    start
}

// ---------- Python ----------

/// python `_indent(line)`: `expandtabs()` 한 줄의 앞 공백 글자 수.
pub fn indent(line: &str) -> usize {
    let mut col = 0;
    let mut count = 0;
    for c in line.chars().take_while(|&c| is_space(c)) {
        match c {
            '\t' => {
                let n = 8 - col % 8;
                col += n;
                count += n;
            }
            '\n' | '\r' => {
                col = 0;
                count += 1;
            }
            _ => {
                col += 1;
                count += 1;
            }
        }
    }
    count
}

fn py_functions(rows: &[Row], lines: &[&str]) -> Vec<Function> {
    let mut out = Vec::new();
    let mut ln = 0;
    while ln < rows.len() {
        let name = if rows[ln].inside {
            None
        } else {
            first_group(&PY_DEF, &rows[ln].k)
        };
        let Some(name) = name else {
            ln += 1;
            continue;
        };

        let ind = indent(lines[ln]);
        let head_end = py_header_end(rows, ln);
        let last = py_body_end(rows, lines, head_end, ind);
        out.push(Function {
            public: !name.starts_with('_'),
            metamethod: name.starts_with("__") && name.ends_with("__"),
            test: false,
            name,
            start: ln,
            header_end: head_end,
            end: last + 1,
            last,
            indent: ind,
        });
        ln = last + 1;
    }

    py_public_scope(&mut out, rows, lines);
    out
}

// `def` 머리가 끝나는 줄: 매개변수 괄호가 열린 뒤 괄호 깊이 0 의 첫 콜론
fn py_header_end(rows: &[Row], start: usize) -> usize {
    let mut depth: i64 = 0;
    let mut opened = false;
    for (k, row) in rows.iter().enumerate().skip(start).take(PY_HEADER_SCAN) {
        for ch in row.k.chars() {
            match ch {
                '(' | '[' | '{' => {
                    depth += 1;
                    opened = true;
                }
                ')' | ']' | '}' => depth -= 1,
                ':' if depth <= 0 && opened => return k,
                _ => {}
            }
        }
    }
    start
}

// 본문의 마지막 코드 줄. 빈 줄, 주석 줄, 여러 줄 문자열 안의 줄은 들여쓰기와 무관하게 본문을 끊지 않는다
fn py_body_end(rows: &[Row], lines: &[&str], head_end: usize, ind: usize) -> usize {
    let mut last = head_end;
    for k in head_end + 1..rows.len() {
        if rows[k].inside || !rows[k].code {
            continue;
        }
        if indent(lines[k]) <= ind {
            break;
        }
        last = k;
    }
    last
}

// 모듈 맨 위 함수와 공개 클래스의 메서드만 공개다. `__main__` 블록이 있는 스크립트는 남이 부르는 코드가 아니다
fn py_public_scope(found: &mut [Function], rows: &[Row], lines: &[&str]) {
    if rows.iter().any(|r| PY_MAIN.match_start(&r.k).is_some()) {
        for f in found.iter_mut() {
            f.public = false;
        }
        return;
    }

    let classes: Vec<(usize, usize, String)> = rows
        .iter()
        .enumerate()
        .filter_map(|(ln, r)| {
            PY_CLASS
                .match_start(&r.k)
                .and_then(|m| Some((ln, indent(lines[ln]), m.text(&r.k, 1)?.to_owned())))
        })
        .collect();
    for f in found.iter_mut().filter(|f| f.indent != 0) {
        let owner = classes.iter().rfind(|c| c.0 < f.start && c.1 < f.indent);
        f.public = f.public && owner.is_some_and(|c| c.1 == 0 && !c.2.starts_with('_'));
    }
}

// ---------- C family ----------

// 읽는 중인 함수 머리
#[derive(Clone, Copy, Debug)]
struct Sig {
    ln: usize,
    /// 머리가 시작할 때의 괄호 깊이.
    paren: i64,
    angle: i64,
    brace: i64,
    call: bool,
}

// 여는 중괄호 하나: (함수 본문인가, 머리 줄, 중괄호 줄, 머리 안의 중괄호인가)
type Brace = (bool, Option<usize>, usize, bool);

fn c_spans(rows: &[Row], lang: Lang) -> Vec<(usize, usize, usize)> {
    let keyword = match lang {
        Lang::Rust => "fn",
        Lang::Go => "func",
        Lang::Kt => "fun",
        _ => "function",
    };
    let mut stack: Vec<Brace> = Vec::new();
    let mut spans = Vec::new();
    let mut sig: Option<Sig> = None;
    let mut paren: i64 = 0;
    let mut prev = String::new();
    let depth =
        |sig: &Option<Sig>, paren: i64| sig.map_or(0, |s| paren - s.paren + s.angle + s.brace);
    let start = |ln, paren, call| {
        Some(Sig {
            ln,
            paren,
            angle: 0,
            brace: 0,
            call,
        })
    };

    for (ln, row) in rows.iter().enumerate() {
        // A ts method head or a call taking a callback
        let code = row.k.trim_end_matches(is_space);
        if lang == Lang::Ts
            && sig.is_none()
            && !code.ends_with(';')
            && first_group_match(&C_METHOD, code)
                .is_some_and(|name| !C_CONTROL.contains(&name.as_str()))
        {
            sig = start(ln, paren, true);
        }

        // Tokens of the line
        let toks = tokens(&C_TOKEN, code);
        for (i, &tok) in toks.iter().enumerate() {
            let next_is_brace = toks.get(i + 1) == Some(&"{");
            if tok == "(" || tok == ")" {
                paren += if tok == "(" { 1 } else { -1 };
            } else if tok == keyword
                || (tok == "=>"
                    && next_is_brace
                    && sig.is_none_or(|s| s.call || depth(&sig, paren) == 0))
            {
                sig = start(ln, paren, false);
            } else if sig.is_some() && (tok == "<" || tok == ">") && lang != Lang::Go {
                if let Some(s) = sig.as_mut() {
                    s.angle = (s.angle + if tok == "<" { 1 } else { -1 }).max(0);
                }
            } else if tok == "{" && sig.is_some() && (depth(&sig, paren) > 0 || prev == ":") {
                if let Some(s) = sig.as_mut() {
                    s.brace += 1;
                }
                stack.push((false, None, ln, true));
            } else if tok == "{" {
                let inside = stack.iter().any(|b| b.0);
                stack.push((sig.is_some() && !inside, sig.map(|s| s.ln), ln, false));
                sig = None;
            } else if tok == "}" && !stack.is_empty() {
                let Some((is_fn, head, brace, in_sig)) = stack.pop() else {
                    continue;
                };
                if let (true, Some(s)) = (in_sig, sig.as_mut()) {
                    s.brace = (s.brace - 1).max(0);
                }
                if let (true, Some(head)) = (is_fn, head) {
                    spans.push((head, brace, ln));
                }
            } else if (if sig.is_some() {
                depth(&sig, paren)
            } else {
                paren
            }) <= 0
                && (tok == ";" || (tok == "=" && lang == Lang::Kt))
            {
                sig = None;
            }
            tok.clone_into(&mut prev);
        }

        // A head with no brace on this or the next line is a call or a signature
        if sig.is_some()
            && depth(&sig, paren) <= 0
            && !code.is_empty()
            && !code.ends_with('{')
            && !next_continues(rows, ln)
        {
            sig = None;
        }
    }
    spans
}

fn first_group_match(rx: &Regex, text: &str) -> Option<String> {
    rx.match_start(text)
        .and_then(|m| m.text(text, 1).map(str::to_owned))
}

// 다음 코드 줄이 머리를 잇는가(Allman 중괄호, Rust where 절, 반환 타입 줄)
fn next_continues(rows: &[Row], ln: usize) -> bool {
    for row in rows.iter().skip(ln + 1).take(3) {
        let code = strip(&row.k);
        if !code.is_empty() {
            return C_CONTINUES.iter().any(|c| code.starts_with(c));
        }
    }
    false
}

fn c_functions(rows: &[Row], lang: Lang) -> Vec<Function> {
    c_spans(rows, lang)
        .into_iter()
        .map(|(head, brace, end)| {
            let code = &rows[head].k;
            let name = C_NAMES
                .iter()
                .find_map(|rx| first_group(rx, code))
                .or_else(|| first_group_match(&C_METHOD, code))
                .unwrap_or_else(|| "(anonymous)".to_owned());
            Function {
                public: c_public(code, &name, lang),
                name,
                start: head,
                header_end: brace,
                end,
                last: end,
                metamethod: false,
                test: lang == Lang::Rust && rust_test(rows, head),
                indent: 0,
            }
        })
        .collect()
}

// 머리 줄이나 그 바로 위 속성 줄에 시험 속성이 있는가
fn rust_test(rows: &[Row], head: usize) -> bool {
    let attrs = rows[..head]
        .iter()
        .rev()
        .take_while(|r| r.code && ATTRIBUTE.match_start(&r.k).is_some());
    std::iter::once(&rows[head])
        .chain(attrs)
        .any(|r| RUST_TEST.is_match(&r.k))
}

fn c_public(code: &str, name: &str, lang: Lang) -> bool {
    match lang {
        Lang::Ts => TS_EXPORT.is_match(code),
        Lang::Rust => RUST_PUB.is_match(code),
        Lang::Go => name.chars().next().is_some_and(is_upper),
        _ => !KT_PRIVATE.is_match(code) && name != "(anonymous)",
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::lex::{Family, lex};

    fn found(text: &str, fam: Family, lang: Lang) -> Vec<(String, usize, usize, bool)> {
        let rows = lex(text, fam, true);
        let lines: Vec<&str> = text.split('\n').collect();
        functions(&rows, &lines, lang)
            .unwrap()
            .into_iter()
            .map(|f| (f.name, f.start, f.end, f.public))
            .collect()
    }

    /// 언어마다 가장 바깥 함수의 이름, 시작, 끝, 공개 여부를 찾는다.
    #[test]
    fn finds_outer_functions() {
        // Lua if-expressions and loops keep the function open
        let lua = "local M = {}\nfunction M.run(a)\n  local x = if a then 1 else 2\n  for i = 1, 3 do\n  end\nend\nreturn M\n";
        assert_eq!(
            found(lua, Family::Lua, Lang::Lua),
            vec![("M.run".to_owned(), 1, 5, true)]
        );

        // Python: a method of a public class is public
        let py = "def a(x):\n    return x\n\nclass B:\n    def run(self):\n        return 1\n";
        assert_eq!(
            found(py, Family::Py, Lang::Py),
            vec![("a".to_owned(), 0, 2, true), ("run".to_owned(), 4, 6, true)]
        );

        // Rust: pub marks a public function
        let rs = "pub fn f(x: u8) -> u8 {\n    x\n}\nfn g() {}\n";
        assert_eq!(
            found(rs, Family::Rust, Lang::Rust),
            vec![("f".to_owned(), 0, 2, true), ("g".to_owned(), 3, 3, false)]
        );

        // A tab expands to the next multiple of 8
        assert_eq!(indent("\t x"), 9);
    }

    /// 시험 속성(`#[test]`, `#[tokio::test(...)]`, 머리 줄의 `#[test]`)이 달린 함수만 시험이다.
    #[test]
    fn marks_rust_tests() {
        let rs = "#[cfg(test)]\nmod tests {\n    #[test]\n    fn a() {}\n\n    #[tokio::test(flavor = \"x\")]\n    #[ignore]\n    async fn b() {}\n\n    #[test] fn c() {}\n\n    fn helper() {}\n}\n";
        let rows = lex(rs, Family::Rust, true);
        let lines: Vec<&str> = rs.split('\n').collect();
        let tests: Vec<(String, bool)> = functions(&rows, &lines, Lang::Rust)
            .unwrap()
            .into_iter()
            .map(|f| (f.name, f.test))
            .collect();
        let want = [("a", true), ("b", true), ("c", true), ("helper", false)];
        assert_eq!(tests, want.map(|(n, t)| (n.to_owned(), t)).to_vec());
    }

    /// 이 모듈의 고정 패턴이 모두 regex crate 로 옮겨지고 엔진이 만들어진다.
    #[test]
    fn fixed_patterns_build() {
        LUA_TOKEN.check();
        LUA_NAME.check();
        LUA_PUBLIC.check();
        METAMETHOD.check();
        C_TOKEN.check();
        C_METHOD.check();
        for r in C_NAMES.iter() {
            r.check();
        }
        KT_PRIVATE.check();
        TS_EXPORT.check();
        RUST_PUB.check();
        ATTRIBUTE.check();
        RUST_TEST.check();
        PY_DEF.check();
        PY_CLASS.check();
        PY_MAIN.check();
    }
}
