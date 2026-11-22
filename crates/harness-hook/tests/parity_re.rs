//! py::re 를 python `re` 와 대조한다: 손으로 고른 패턴과, 작은 글자 모음에서 만든 패턴 수천 개를 여러 글에 맞춰 본다.
//! 견주는 것은 오류 종류(re.error, OverflowError), search 의 범위, fullmatch, 빈 아닌 finditer 범위다.
//! 여기서 옮기지 않은 문법(Unsupported)은 python 과 견주지 않고 수만 센다.

mod common;

use common::{case, python};
use harness_hook::Env;
use harness_hook::py::path::normpath;
use harness_hook::py::re::{Error, Flags, Regex};
use harness_hook::py::tempfile::gettempdir;
use serde_json::{Value, json};

const PATTERNS: &[&str] = &[
    // Shapes the hooks use
    r#"<<(?!<)-?\s*(?:'([A-Za-z_]\w*)'|"([A-Za-z_]\w*)"|\\?([A-Za-z_]\w*))"#,
    r"&&|\|\||[;|\n]",
    r"(?<![A-Za-z])(bench|fuzz|perf(?:orm(?:ance)?)?(?![A-Za-z])|stress|soak|load-?test|hyperfine)",
    r"(?:^|[;&|\s(])([A-Za-z_][A-Za-z0-9_]*)=(\S*)",
    r"os\.clock\(|perf_counter|timeit|performance\.now\(|hrtime|Instant::now",
    r"(?:(?<=\$\()|(?<=`)|(?<![^\s({!]))(?:[\w./-]*/)?(pgrep|pkill)(?=\s)",
    r"-(?:\d+|(?:SIG)?[A-Z][A-Z0-9]+(?:[+-]\d+)?)",
    r"(?<![>&<])&(?![>&])",
    r#"(?:^|[;&|\s(])([A-Za-z_]\w*)=("[^"]*"|'[^']*'|[^\s;&|)]*)"#,
    r"\$\{?([A-Za-z_]\w*)\}?",
    r"[\d.]+[smhd]?",
    r"[A-Za-z_][A-Za-z0-9_]*=\S*",
    r"\A(?:core\.(.+)\.(\d+)|core(?:\.\d+)?)\Z",
    r"core dumped|Segmentation fault|\bSIG(?:SEGV|ABRT)\b|signal: (?:3|4|11)\b",
    r"\AExit code (\d+)",
    r"(?<![A-Za-z0-9_.-])luau\-lsp",
    // Patterns usable with pgrep
    "test-delegate-cli.py",
    "[t]est-delegate",
    "python3 run.py",
    "^/bin/bash",
    "bash -c .*sleep$",
    "node server\\.js",
    "[[:alpha:]]+",
    "[[:digit:]]",
    "a|b|",
    "(foo|bar)+baz",
    "x{2,3}y",
    "x{,2}",
    "x{3,}",
    "x{}",
    "x{a}",
    "x{2,1}",
    "x{99999999999}",
    "(?i)TEST",
    "(?m)^sleep",
    "(?s)a.b",
    "a(?i)b",
    "(?i:a)b",
    "(?P<n>ab)(?P=n)",
    "(a)(b)\\2\\1",
    "(a)\\2",
    "(a\\1)",
    "\\0\\101\\08",
    "\\x41\\u0042\\U00000043",
    "\\x4",
    "\\N{EM DASH}",
    "\\q",
    "\\",
    "[",
    "[]",
    "[]a]",
    "[^]a]",
    "[a-]",
    "[z-a]",
    "[\\d-z]",
    "[\\w.-]+",
    "[^\\s]+",
    "\\bsleep\\b",
    "\\Bleep",
    "a**",
    "a*?b",
    "a+?",
    "a??",
    "a*+",
    "c++",
    "a*+b",
    "x?+x",
    "(a|ab)++c",
    "(?>a)",
    "(?>a|ab)c",
    "(?>a*)a",
    "(?#comment)a*",
    "(?<=ab)c",
    "(?<=a|bc)d",
    "(?<=a+)b",
    "(?<!x)y",
    "(?=)a",
    "(?!)",
    "()*a",
    "(a*)*b",
    "(a|)+c",
    "*a",
    "a|*b",
    "(*a)",
    "^*",
    ")",
    "(",
    "(?",
    "(?P",
    "(?Px)",
    "(?<x)",
    "(?z)",
    "(?L)",
    "(?x) a b",
    "(?a)\\w",
    "$",
    "a$",
    "\\Z",
    "\u{17f}tre\u{17f}\u{17f}",
    "[A-Z]it",
    "[^a-z]",
    "\u{d55c}+",
    "\\w+\u{903}",
    // Empty-iteration captures (python accepts one and ends the repeat), python 3.14 `\z`, `\B` on empty text
    "()*+\\d",
    "()*\\d",
    "(a|)*+\\d",
    "(a|)*?c",
    "(a*)*+b",
    "(a?)*+b",
    "(a|)+c",
    "(|a){2,3}c",
    "(?:()|a)*+\\d",
    "\\B",
    "a\\z",
    "[\\z]",
    // Single-char repeats (REPEAT_ONE) and big repeat counts
    " * * *z",
    "[ab]{2,5}?c",
    "a*?b",
    ".{3}x",
    "(?:a)*b",
    "x*+x",
    "\\s+?\\S",
    "x{2000}",
    "x{0,99999}y",
    "(?:x{500}){500}",
    "(?:){99999}",
];

const TEXTS: &[&str] = &[
    "/bin/bash -c until ! pgrep -f \"test-delegate-cli.py\" >/dev/null; do sleep 2; done",
    "/bin/bash -c python3 test-delegate.py & until ! pgrep -f \"[t]est-delegate\"; do sleep 2; done",
    "cd bench && ./run.sh\nluau perf.luau",
    "F=tests/fuzz.luau; luau $F",
    "cat <<'EOF' > x\nos.clock()\nEOF",
    "aab abab xxy x{} x{a} \u{212a}it Kit kit STRE\u{17f}S stress",
    "core.luau-lsp.123",
    "Exit code 139\nSegmentation fault (core dumped)",
    "a\n",
    "",
    "\u{d55c}\u{d55c} abc_\u{903} \u{663}\u{664}s 12.5m",
    "foobarfoobaz abab aa ab\u{c}cd",
    "     a  z ab  abbbc  1",
];

const ALPHABET: &[&str] = &[
    "a", "b", ".", "*", "+", "?", "|", "(", ")", "[", "]", "^", "$", "\\b", "\\w", "\\d", "\\s",
    "{1,2}", "-", "(?:", "(?=", "(?<=", "(?!", "(?>", "++", "*+", "\\1", "s", "\u{17f}", "K", "{",
    "}", ",", " ", "\\", "()", "*?", "{0,2}?", "\\B", "\\z", "(|a)",
];

// Small fixed-seed random generator (LCG) so every run builds the same patterns
fn generated(count: usize) -> Vec<String> {
    let mut state: u64 = 0x9e37_79b9_7f4a_7c15;
    let mut next = move || {
        state = state
            .wrapping_mul(6_364_136_223_846_793_005)
            .wrapping_add(1_442_695_040_888_963_407);
        (state >> 33) as usize
    };
    (0..count)
        .map(|_| {
            let len = 1 + next() % 6;
            (0..len)
                .map(|_| ALPHABET[next() % ALPHABET.len()])
                .collect()
        })
        .collect()
}

fn flags_of(bits: u64) -> Flags {
    Flags {
        ignore_case: bits & 1 != 0,
        multiline: bits & 2 != 0,
        dotall: bits & 4 != 0,
    }
}

fn chars_at(text: &str, byte: usize) -> usize {
    text[..byte].chars().count()
}

// Result in the same shape as python; None when Unsupported
fn rust_result(pattern: &str, bits: u64, text: &str) -> Option<Value> {
    let re = match Regex::with_flags(pattern, flags_of(bits)) {
        Ok(re) => re,
        Err(Error::Syntax(_)) => return Some(json!("error")),
        Err(Error::Overflow) => return Some(json!("overflow")),
        Err(Error::TooDeep) => return Some(json!("recursion")),
        Err(Error::Unsupported(_)) => return None,
    };
    let span = |s: usize, e: usize| json!([chars_at(text, s), chars_at(text, e)]);
    let search = re.search(text).map(|m| span(m.start(), m.end()));
    let iter: Vec<Value> = re
        .find_iter(text)
        .iter()
        .filter(|m| m.end() > m.start())
        .map(|m| span(m.start(), m.end()))
        .collect();
    let groups = re.search(text).map(|m| {
        (1..=re.groups())
            .map(|i| m.group(i).map(|(s, e)| span(s, e)))
            .collect::<Vec<_>>()
    });
    Some(
        json!({"search": search, "full": re.fullmatch(text).is_some(), "iter": iter, "groups": groups}),
    )
}

/// 정규식의 일치와 오류 종류가 python `re` 와 같다(손으로 고른 패턴과 만든 패턴, 플래그별).
#[test]
fn regex_matches_python() {
    // Cases: hand-picked patterns with four flag sets, built ones with none and IGNORECASE
    let mut cases = Vec::new();
    for p in PATTERNS {
        for bits in [0, 1, 2, 4] {
            for t in TEXTS {
                cases.push(((*p).to_owned(), bits, (*t).to_owned()));
            }
        }
    }
    // Group nesting: 400 levels read by both, 600 raises RecursionError in python
    for depth in [400, 600] {
        let p = format!("{}x{}", "(?:".repeat(depth), ")".repeat(depth));
        cases.push((p, 0, "axb".to_owned()));
    }
    for (i, p) in generated(4000).into_iter().enumerate() {
        let t = TEXTS[i % TEXTS.len()];
        cases.push((p, (i % 2) as u64, t.to_owned()));
    }
    let args: Vec<Value> = cases.iter().map(|(p, b, t)| json!([p, b, t])).collect();
    let Some(results) = python(&[case("re", &[], json!({"cases": args}))]) else {
        return;
    };
    let want = results[0].as_array().expect("list of results");

    // Compare
    let mut unsupported = 0;
    let mut bad = Vec::new();
    for ((p, bits, t), want) in cases.iter().zip(want) {
        match rust_result(p, *bits, t) {
            None => unsupported += 1,
            Some(got) if &got != want => bad.push(format!(
                "{p:?} flags={bits} text={t:?}\n  python {want}\n  rust   {got}"
            )),
            Some(_) => {}
        }
    }
    eprintln!(
        "re parity: {} cases, {unsupported} unsupported",
        cases.len()
    );
    assert!(
        bad.is_empty(),
        "{} differences:\n{}",
        bad.len(),
        bad.iter().take(20).cloned().collect::<Vec<_>>().join("\n")
    );
}

/// `normpath` 와 임시 폴더 고르기가 python 판과 같다.
#[test]
fn normpath_and_tempdir_match_python() {
    let paths = [
        "",
        ".",
        "/",
        "//",
        "///a",
        "a/../..",
        "/../a",
        "a/./b//c/",
        "//a/b/../c",
        "../a/..",
    ];
    let tmp = std::env::temp_dir().to_string_lossy().into_owned();
    let env = [
        ("TMPDIR".to_owned(), "/no/such/dir".to_owned()),
        ("TEMP".to_owned(), format!("{tmp}/./")),
    ];
    let Some(results) = python(&[
        case("normpath", &[], json!({"paths": paths})),
        case("gettempdir", &env, json!({})),
    ]) else {
        return;
    };
    let ours: Vec<String> = paths.iter().map(|p| normpath(p)).collect();
    assert_eq!(results[0], json!(ours));
    assert_eq!(results[1], json!(gettempdir(&Env::from_pairs(env))));
}
