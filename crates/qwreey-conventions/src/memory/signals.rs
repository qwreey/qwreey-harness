//! 메모리 글이 저장소 지식으로 보이는가(python `lib/memory_signals.py` 의 parse_memory, signals, classify, describe).
//!
//! 강한 신호(경로, 빌드와 시험 명령, "이 저장소에서")는 종류마다 2점, 약한 신호(심볼, 규약 낱말)는 1점,
//! type 가산(project +1, reference -1), 환경 표현은 -2. 3점 이상이고 강한 신호나 심볼이 있으면 저장소 지식이다.
//! `type: user` 는 늘 개인 메모다.

use std::sync::LazyLock;

use harness_hook::py::re::{Flags, Regex};

/// 점수가 이 이상이면 저장소 지식(python `THRESHOLD`).
const THRESHOLD: i32 = 3;
/// 근거 글에 종류마다 보이는 조각 수(python `describe(limit=3)`).
const DESCRIBE_LIMIT: usize = 3;

const EXT: &str =
    r"(?:luau|lua|ts|tsx|js|jsx|mjs|py|rs|go|kt|md|json|toml|yaml|yml|sh|astro|html|css|sql)";

fn re(pattern: &str, flags: Flags) -> Regex {
    Regex::with_flags(pattern, flags).expect("constant pattern")
}

static FRONTMATTER: LazyLock<Regex> = LazyLock::new(|| {
    let dotall = Flags {
        dotall: true,
        ..Flags::NONE
    };
    re(r"^---\s*\n(.*?)\n---\s*\n?", dotall)
});
static TYPE_LINE: LazyLock<Regex> = LazyLock::new(|| {
    let multiline = Flags {
        multiline: true,
        ..Flags::NONE
    };
    re(r"^\s*type:\s*([\w-]+)", multiline)
});
static RE_PATH: LazyLock<Regex> = LazyLock::new(|| {
    re(
        &format!(r"(?<![\w/~.])(?:\.?[\w-]+/)+[\w.-]+\.{EXT}\b"),
        Flags::NONE,
    )
});
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
    // 닫는 `\n---` 가 없으면 맞지 않는다. 정규식에 맡기면 빈 줄 n 개 뒤에서 n 제곱으로 되돌아간다(python 도 같다)
    if !text.starts_with("---") || !text[3..].contains("\n---") {
        return (String::new(), text);
    }
    let Some(m) = FRONTMATTER.match_start(text) else {
        return (String::new(), text);
    };
    let fm = m.text(text, 1).unwrap_or("");
    let kind = TYPE_LINE
        .search(fm)
        .and_then(|t| t.text(fm, 1))
        .map(str::to_lowercase)
        .unwrap_or_default();
    (kind, &text[m.end()..])
}

// python [m.group(0) for m in re.finditer(...)] 를 dict.fromkeys 로 겹치지 않게
fn found(re: &Regex, text: &str) -> Vec<String> {
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
        path: found(&RE_PATH, &cleaned),
        command: found(&RE_COMMAND, body),
        here: found(&RE_HERE, body),
        symbol: found(&RE_SYMBOL, body),
        conv: found(&RE_CONV, body),
        env: found(&RE_ENV, body),
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
}
