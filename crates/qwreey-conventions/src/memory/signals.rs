//! 메모리 글이 저장소 지식으로 보이는가(python `lib/memory_signals.py` 의 parse_memory, signals, classify, describe).
//!
//! 강한 신호(경로, 빌드와 시험 명령, "이 저장소에서")는 종류마다 2점, 약한 신호(심볼, 규약 낱말)는 1점,
//! type 가산(project +1, reference -1), 환경 표현은 -2. 3점 이상이고 강한 신호나 심볼이 있으면 저장소 지식이다.
//! `type: user` 는 늘 개인 메모다.

use std::sync::LazyLock;

use harness_hook::py::re::Flags;
use harness_hook::py::text::is_space;
use harness_hook::rx::Regex;

use crate::pat::{Look, Pat, before, is_word};

/// 점수가 이 이상이면 저장소 지식(python `THRESHOLD`).
const THRESHOLD: i32 = 3;
/// 근거 글에 종류마다 보이는 조각 수(python `describe(limit=3)`).
const DESCRIBE_LIMIT: usize = 3;

const EXT: &str =
    r"(?:luau|lua|ts|tsx|js|jsx|mjs|py|rs|go|kt|md|json|toml|yaml|yml|sh|astro|html|css|sql)";

fn re(pattern: &str, flags: Flags) -> Regex {
    Regex::with_flags(pattern, flags)
}

static TYPE_LINE: LazyLock<Regex> = LazyLock::new(|| {
    let multiline = Flags {
        multiline: true,
        ..Flags::NONE
    };
    re(r"^\s*type:\s*([\w-]+)", multiline)
});
// python `(?<![\w/~.])...`: 뒤보기는 앞 글자 검사로. 거른 뒤에는 그 글자들이 이어진 동안을 건너뛴다(그 안의 자리는 늘 걸러진다)
static RE_PATH: LazyLock<Look> = LazyLock::new(|| {
    Look::new(
        &format!(r"(?:\.?[\w-]+/)+[\w.-]+\.{EXT}\b"),
        |t, m| before(t, m.start()).is_none_or(|c| !path_char(c)),
        None,
    )
    .skipping(path_char)
});

// 경로 앞에 오면 그 자리를 경로의 시작으로 보지 않는 글자(python `[\w/~.]`)
fn path_char(c: char) -> bool {
    is_word(c) || matches!(c, '/' | '~' | '.')
}
static RE_SYMBOL: LazyLock<Regex> = LazyLock::new(|| {
    re(
        r"`[A-Za-z_][\w]*(?:(?:\.|::|:)[A-Za-z_]\w*)+(?:\(\))?`|`[A-Za-z_]\w*\(\)`",
        Flags::NONE,
    )
});
static RE_COMMAND: LazyLock<Regex> = LazyLock::new(|| {
    re(
        r"`(?:make|npm|pnpm|yarn|bun|cargo|go|pytest|python3?|lune|rojo|luau|luau-analyze|selene|stylua|wally|just|tsc|vitest|jest)\b[^`\n]*`",
        Flags::NONE,
    )
});
static RE_HERE: LazyLock<Regex> = LazyLock::new(|| {
    re(
        r"\b(?:in|for|of) (?:this|the) (?:repo|repository|codebase|project)\b|\bthis (?:repo|repository|codebase)\b|이 (?:저장소|레포|프로젝트|코드베이스)(?:에서|의|는|에는)?",
        Flags::IGNORECASE,
    )
});
static RE_CONV: LazyLock<Regex> = LazyLock::new(|| {
    re(
        r"\b(?:convention|always use|never use|must not|do not use|gotcha|pitfall|workaround|invariant)\b|규약|컨벤션|항상 .{0,12}(?:쓴다|사용|한다)|금지|함정|주의",
        Flags::IGNORECASE,
    )
});
static RE_ENV: LazyLock<Regex> = LazyLock::new(|| {
    re(
        r"sandbox|this machine|my machine|container|dev ?server|mise\b|~/\.claude|/code/\.|\bshim\b|이 기기|샌드박스|개발 서버|내 환경|이 환경",
        Flags::IGNORECASE,
    )
});
static RE_ABS_ENV: LazyLock<Regex> =
    LazyLock::new(|| re(r"(?:~|/home/\w+|/code/\.claude|/tmp)/[\w./-]*", Flags::NONE));

/// 신호 종류마다 맞은 조각(겹치지 않게, 처음 나온 순서). python `signals(body)` 의 dict.
#[derive(Clone, Debug, Default, PartialEq, Eq)]
pub struct Signals {
    pub path: Vec<String>,
    pub command: Vec<String>,
    pub here: Vec<String>,
    pub symbol: Vec<String>,
    pub conv: Vec<String>,
    pub env: Vec<String>,
}

/// python `parse_memory(text)` 의 (type, body). type 은 frontmatter 의 `type:` 줄(중첩된 것도), 없으면 빈 글.
pub fn parse_memory(text: &str) -> (String, &str) {
    let Some((fm, end)) = frontmatter(text) else {
        return (String::new(), text);
    };
    let kind = TYPE_LINE
        .search(fm)
        .and_then(|t| t.text(fm, 1))
        .map(str::to_lowercase)
        .unwrap_or_default();
    (kind, &text[end..])
}

/// python `frontmatter(text)`: `re.match(r"^---\s*\n(.*?)\n---\s*\n?", text, re.S)` 의 (머리 글, 끝 자리)를 되짚기 없이.
///
/// 그 정규식은 `\s*` 가 줄바꿈을 하나씩 돌려주며 닫는 `---` 가 없으면 줄바꿈마다 글 끝까지 다시 훑었다.
/// `---` 다음 줄바꿈은 공백 줄의 마지막 줄바꿈이고, 그 줄바꿈이 닫는 `\n---` 의 머리이면 하나 앞 줄바꿈이다.
pub fn frontmatter(text: &str) -> Option<(&str, usize)> {
    let rest = text.strip_prefix("---")?;
    let run = rest.len() - rest.trim_start_matches(is_space).len();
    let nl: Vec<usize> = rest[..run]
        .match_indices('\n')
        .map(|(i, _)| i + 3)
        .collect();
    let &last = nl.last()?;

    // The closing marker after the last newline, else that newline as the closing marker
    let (start, close) = match text[last + 1..].find("\n---") {
        Some(k) => (last, last + 1 + k),
        None if nl.len() >= 2 && text[last + 1..].starts_with("---") => (nl[nl.len() - 2], last),
        None => return None,
    };
    let after = &text[close + 4..];
    let end = close + 4 + (after.len() - after.trim_start_matches(is_space).len());
    Some((&text[start + 1..close], end))
}

// python [m.group(0) for m in re.finditer(...)] 를 dict.fromkeys 로 겹치지 않게
fn found(re: &dyn Pat, text: &str) -> Vec<String> {
    let mut out: Vec<String> = Vec::new();
    for m in re.find_iter(text) {
        let s = &text[m.start()..m.end()];
        if !out.iter().any(|x| x == s) {
            out.push(s.to_owned());
        }
    }
    out
}

/// python `signals(body)`. 경로는 이 기기의 절대 경로(`~/...`, `/tmp/...`)를 지운 글에서 찾는다.
pub fn signals(body: &str) -> Signals {
    let cleaned = RE_ABS_ENV.replace_all(body, |_| " ".to_owned());
    Signals {
        path: found(&*RE_PATH, &cleaned),
        command: found(&*RE_COMMAND, body),
        here: found(&*RE_HERE, body),
        symbol: found(&*RE_SYMBOL, body),
        conv: found(&*RE_CONV, body),
        env: found(&*RE_ENV, body),
    }
}

/// python `classify(text)` 의 판정과 신호: 저장소 지식으로 보이면 `true`.
pub fn classify(text: &str) -> (bool, Signals) {
    let (kind, body) = parse_memory(text);
    let sig = signals(body);

    // Score the kinds of signals
    let strong = [&sig.path, &sig.command, &sig.here];
    let mut score: i32 = strong.iter().filter(|v| !v.is_empty()).count() as i32 * 2;
    score += [&sig.symbol, &sig.conv]
        .iter()
        .filter(|v| !v.is_empty())
        .count() as i32;
    score += match kind.as_str() {
        "project" => 1,
        "reference" => -1,
        _ => 0,
    };
    if !sig.env.is_empty() {
        score -= 2;
    }

    let backed = strong.iter().any(|v| !v.is_empty()) || !sig.symbol.is_empty();
    (kind != "user" && score >= THRESHOLD && backed, sig)
}

/// python `describe(sig)`: 짧은 근거 글(`path src/a.py; command `make all``).
pub fn describe(sig: &Signals) -> String {
    let kinds = [
        ("path", &sig.path),
        ("command", &sig.command),
        ("here", &sig.here),
        ("symbol", &sig.symbol),
        ("conv", &sig.conv),
    ];
    kinds
        .iter()
        .filter(|(_, v)| !v.is_empty())
        .map(|(k, v)| format!("{k} {}", v[..v.len().min(DESCRIBE_LIMIT)].join(", ")))
        .collect::<Vec<_>>()
        .join("; ")
}

#[cfg(test)]
mod tests {
    use super::*;

    /// frontmatter 는 python 의 원래 정규식과 같은 머리 글과 끝 자리를 낸다(되짚는 엔진 py::re 를 기준으로).
    #[test]
    fn frontmatter_like_the_python_regex() {
        // Reference: the regex python used before, read by py::re
        let dotall = Flags {
            dotall: true,
            ..Flags::NONE
        };
        let reference =
            harness_hook::py::re::Regex::with_flags(r"^---\s*\n(.*?)\n---\s*\n?", dotall).unwrap();
        let pieces = [
            "-", "---", "\n", " ", "\t", "a", "\u{3000}", "\r", "x:", "\n---", "\u{b}",
        ];

        // Every string of up to 5 pieces
        let mut texts = vec![String::new()];
        for _ in 0..5 {
            let longer: Vec<String> = texts
                .iter()
                .flat_map(|t| pieces.iter().map(move |p| format!("{t}{p}")))
                .collect();
            texts.extend(longer);
            texts.dedup();
        }
        for t in &texts {
            let want = reference
                .match_start(t)
                .map(|m| (m.text(t, 1).unwrap_or(""), m.end()));
            assert_eq!(frontmatter(t), want, "{t:?}");
        }

        // Long whitespace without a closing marker stays fast
        let long = format!("---{}x", " \n".repeat(20000));
        assert_eq!(frontmatter(&long), None);
    }

    /// 저장소 지식, 개인 메모, 환경 메모를 python 판정대로 가른다.
    #[test]
    fn classifies_like_python() {
        // Paths, commands and "in this repo" with type project
        let repo = "---\nname: b\nmetadata:\n  type: project\n---\nIn this repo, build with `make all`. The parser lives in src/parser.py.\n";
        let (is_repo, sig) = classify(repo);
        assert!(is_repo);
        assert_eq!(
            describe(&sig),
            "path src/parser.py; command `make all`; here In this repo"
        );

        // type user is never repo knowledge
        let user = "---\ntype: user\n---\nin this repo see src/main.py and `make all`\n";
        assert!(!classify(user).0);

        // Environment wording costs two points
        let env = "---\ntype: feedback\n---\nOn this machine (the sandbox) the shim fails. Also uses tools/run.sh.\n";
        assert!(!classify(env).0);
    }

    /// 이 기기의 절대 경로는 경로 신호가 아니다.
    #[test]
    fn machine_paths_are_not_repo_paths() {
        // ~/.claude and /tmp paths are blanked before the path search
        assert!(
            signals("see ~/.claude/x/y.md and /tmp/a/b.py")
                .path
                .is_empty()
        );
        assert_eq!(signals("see docs/a.md").path, vec!["docs/a.md"]);
    }

    /// 이 모듈의 고정 패턴이 모두 regex crate 로 옮겨지고 엔진이 만들어진다.
    #[test]
    fn fixed_patterns_build() {
        TYPE_LINE.check();
        RE_PATH.check();
        RE_SYMBOL.check();
        RE_COMMAND.check();
        RE_HERE.check();
        RE_CONV.check();
        RE_ENV.check();
        RE_ABS_ENV.check();
    }

    /// 뒤보기를 앞 글자 검사로 옮긴 경로 패턴은 python 패턴과 같은 조각을 찾는다(긴 낱말을 건너뛰어도).
    #[test]
    fn path_like_python() {
        crate::pat::assert_same(
            &format!(r"(?<![\w/~.])(?:\.?[\w-]+/)+[\w.-]+\.{EXT}\b"),
            Flags::NONE,
            &*RE_PATH,
            &[],
            &[
                "see src/parser.py and ./lib/a.ts",
                "x/src/a.py",
                "~/a/b.md",
                ".claude/rules/x.md",
                "a.b/c.py",
                "-x/y.py",
                "한src/a.py",
                "src/a.pyx src/b.rs",
                "aaaa/bbbb/cccc/dddd.py",
                "(src/a.py)",
                "/tmp/a/b.py",
            ],
        );
    }
}
