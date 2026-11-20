//! 주석 언어(python `word_counts`, `step_labels`, `comment_stats`, `expected_script`, `language_lines`).
//!
//! 파일 주석의 90% 이상이 한 문자 체계(기존 10줄 이상)인데 추가한 줄이 다른 체계 낱말을 3개 이상 쓰면 알린다.
//! 단계 라벨(본문 안 들여쓴 한 줄 주석)은 판정과 다수 계산에서 뺀다.

use std::collections::{BTreeSet, HashMap};
use std::sync::LazyLock;

use harness_hook::py::fs;
use harness_hook::py::path::{dirname, join};
use harness_hook::py::re::Flags;
use harness_hook::py::value::Value;
use harness_hook::rx::Regex;

use super::config::Cfg;
use super::docs::{INLINE_CODE, URL};
use super::history::has_directive;
use crate::edit::Added;
use crate::lex::{self, Row, comment_body};

/// 문자 체계(python `SCRIPT_WORDS` 의 키), 이 순서가 python dict 순서다.
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum Script {
    Latin,
    Hangul,
    Cjk,
    Cyrillic,
}

impl Script {
    const ALL: [Script; 4] = [Script::Latin, Script::Hangul, Script::Cjk, Script::Cyrillic];

    /// 알림에 쓰는 언어 이름(python `SCRIPT_NAME`).
    pub fn language(self) -> &'static str {
        match self {
            Script::Latin => "English",
            Script::Hangul => "Korean",
            Script::Cjk => "Japanese or Chinese",
            Script::Cyrillic => "Russian",
        }
    }

    fn words(self) -> &'static Regex {
        &SCRIPT_WORDS[self as usize]
    }

    /// 언어 코드의 앞 두 글자(소문자) -> 문자 체계(python `LANG_SCRIPT`).
    fn of_lang(code: &str) -> Option<Script> {
        let two: String = code.to_lowercase().chars().take(2).collect();
        Some(match two.as_str() {
            "en" => Script::Latin,
            "ko" => Script::Hangul,
            "ja" | "zh" => Script::Cjk,
            "ru" => Script::Cyrillic,
            _ => return None,
        })
    }
}

fn constant(pattern: &str) -> Regex {
    Regex::new(pattern)
}

static SCRIPT_WORDS: LazyLock<[Regex; 4]> = LazyLock::new(|| {
    [
        constant(r"[A-Za-zÀ-ɏ]{3,}"),
        constant(r"[가-힣]+"),
        constant(r"[぀-ヿ㐀-鿿]+"),
        constant(r"[Ѐ-ӿ]{2,}"),
    ]
});
/// 라벨 낱말(python `LABEL_WORDS`): 라틴은 두 글자 낱말도 센다. 다른 체계는 [`SCRIPT_WORDS`].
static LABEL_LATIN: LazyLock<Regex> = LazyLock::new(|| constant(r"[A-Za-zÀ-ɏ]+"));
static LABEL_REASON: LazyLock<Regex> = LazyLock::new(|| {
    Regex::with_flags(
        r"\b(?:because|since|so|otherwise|unless|must|never|in order to|to avoid|due to|workaround)\b",
        Flags::IGNORECASE,
    )
});
/// 주석 안의 코드 조각(타입 표기, 대입, 블록)은 문장이 아니다(python `CODE_LIKE`).
static CODE_LIKE: LazyLock<Regex> = LazyLock::new(|| constant(r"::|=|[{};]|^\s*`{3}"));

const LANG_MIN_LINES: usize = 10;
const LANG_SHARE: f64 = 0.9;
const LANG_MIN_WORDS: usize = 3;
const LABEL_MAX_CHARS: usize = 72;
const LABEL_WORDS_MIN: usize = 2;
const LABEL_WORDS_MAX: usize = 10;
const SIBLING_MAX_FILES: usize = 20;
/// 형제 파일을 합쳐 이만큼 읽으면 멈춘다(편집 한 번의 훅이 큰 폴더에서 길어지지 않게).
const SIBLING_MAX_BYTES: u64 = 1_000_000;
const SIBLING_FILE_MAX: u64 = 200_000;

/// 체계마다 낱말 수(python `word_counts`). URL 과 인라인 코드는 먼저 지운다.
pub type Counts = [usize; 4];

/// python `word_counts(seg)`.
pub fn word_counts(seg: &str) -> Counts {
    let seg = URL.replace_all(seg, |_| " ".to_owned());
    let seg = INLINE_CODE.replace_all(&seg, |_| " ".to_owned());
    Script::ALL.map(|s| s.words().find_iter(&seg).len())
}

/// python `line_script(counts)`: 낱말이 가장 많은 체계 하나. 없거나 비기면 `None`.
fn line_script(counts: &Counts) -> Option<Script> {
    let top = *counts.iter().max()?;
    if top == 0 {
        return None;
    }
    let mut best = Script::ALL
        .into_iter()
        .filter(|s| counts[*s as usize] == top);
    let first = best.next()?;
    best.next().is_none().then_some(first)
}

/// 단계 라벨 줄(0 기반).
pub type Labels = BTreeSet<usize>;

/// python `step_labels(rows, lines, cfg)`: 언어 판정에서 뺄 단계 라벨 줄. `label_language` 가 글이 아니면 빈 집합.
///
/// 라벨: 본문 안에 들여쓴 한 줄 주석, 위 줄은 주석만 있는 줄이 아니고 아래 줄은 코드, label_language 글자의 낱말 2-10개,
/// 72자 이하, 마침표와 이유 접속어가 없다.
pub fn step_labels(rows: &[Row], lines: &[&str], cfg: &Cfg) -> Labels {
    let lang = match cfg.get("label_language") {
        None => Some("en"),
        Some(Value::Str(s)) => Some(s.as_str()),
        Some(_) => None,
    };
    let Some(script) = lang.and_then(Script::of_lang) else {
        return Labels::new();
    };
    let words_rx = if script == Script::Latin {
        &*LABEL_LATIN
    } else {
        script.words()
    };

    let mut out = Labels::new();
    for i in 1..rows.len().saturating_sub(1) {
        // Shape: one indented comment line heading code
        let r = &rows[i];
        let indented = lines.get(i).is_some_and(|l| l.starts_with([' ', '\t']));
        if r.code || r.c.len() != 1 || !indented {
            continue;
        }
        if (!rows[i - 1].c.is_empty() && !rows[i - 1].code) || !rows[i + 1].code {
            continue;
        }

        // Text: a short phrase in the label language
        let body = comment_body(&r.c[0]);
        if body.is_empty()
            || body.chars().count() > LABEL_MAX_CHARS
            || body.ends_with('.')
            || LABEL_REASON.is_match(body)
        {
            continue;
        }
        let counts = word_counts(body);
        if Script::ALL
            .iter()
            .any(|s| *s != script && counts[*s as usize] > 0)
        {
            continue;
        }
        let n = words_rx.find_iter(body).len();
        if (LABEL_WORDS_MIN..=LABEL_WORDS_MAX).contains(&n) {
            out.insert(i);
        }
    }
    out
}

/// 체계마다 주석 줄 수(python `comment_stats` 의 Counter).
#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct Stats([usize; 4]);

impl Stats {
    fn add(&mut self, other: &Stats) {
        for (a, b) in self.0.iter_mut().zip(other.0) {
            *a += b;
        }
    }

    /// python `majority(cnt)`: 10줄 이상이고 한 체계가 90% 이상이면 그 체계.
    fn majority(&self) -> Option<Script> {
        let total: usize = self.0.iter().sum();
        if total < LANG_MIN_LINES {
            return None;
        }
        let (script, n) = Script::ALL
            .into_iter()
            .map(|s| (s, self.0[s as usize]))
            .max_by_key(|&(_, n)| n)?;
        (n as f64 / total as f64 >= LANG_SHARE).then_some(script)
    }
}

/// python `comment_stats(rows, skip)`: 주석 줄(지시자, skip 줄 제외)의 문자 체계 분포.
pub fn comment_stats(rows: &[Row], skip: impl Fn(usize) -> bool) -> Stats {
    let mut cnt = Stats::default();
    for (i, r) in rows.iter().enumerate() {
        if skip(i) || r.c.is_empty() || has_directive(r) {
            continue;
        }
        if let Some(s) = line_script(&word_counts(&r.c.join(" "))) {
            cnt.0[s as usize] += 1;
        }
    }
    cnt
}

/// 형제 파일 주석 통계 캐시: (경로, mtime_ns, 크기) -> 통계(python `_SIBLING_STATS`, 한 프로세스 안에서만).
#[derive(Debug, Default)]
pub struct SiblingCache(HashMap<(String, i128, u64), Stats>);

/// python `sibling_majority(path, fam_ext, cfg)`: 같은 폴더의 같은 확장자 파일들(이름순 앞 20개, 합쳐 1 MB 까지)의 다수.
fn sibling_majority(path: &str, ext: &str, cfg: &Cfg, cache: &mut SiblingCache) -> Option<Script> {
    let d = dirname(path);
    let mut names: Vec<String> = fs::listdir(d)
        .ok()?
        .into_iter()
        .filter(|n| n.ends_with(ext))
        .collect();
    names.sort();
    let fam = lex::family(ext)?;

    let mut cnt = Stats::default();
    let mut read = 0;
    for n in names
        .iter()
        .map(|n| join(d, n))
        .filter(|p| p != path)
        .take(SIBLING_MAX_FILES)
    {
        let Ok(st) = fs::stat(&n) else { continue };
        if st.size > SIBLING_FILE_MAX {
            continue;
        }
        if read + st.size > SIBLING_MAX_BYTES {
            break;
        }
        read += st.size;

        // Lex each sibling once per (path, mtime, size)
        let key = (n.clone(), st.mtime_ns, st.size);
        if !cache.0.contains_key(&key) {
            let Ok(sib) = fs::read_text(&n) else { continue };
            let rows = lex::lex(&sib, fam, false);
            let lines: Vec<&str> = sib.split('\n').collect();
            let labels = step_labels(&rows, &lines, cfg);
            cache
                .0
                .insert(key.clone(), comment_stats(&rows, |i| labels.contains(&i)));
        }
        if let Some(stats) = cache.0.get(&key) {
            cnt.add(stats);
        }
    }
    cnt.majority()
}

/// python `expected_script(rows, added, cfg, path, ext, labels)`: 이 파일 주석이 따를 문자 체계.
///
/// 파일 다수, 저장소 `comment_language`, 형제 파일 다수 순서. 모두 없으면 검사하지 않는다(`None`).
pub fn expected_script(
    rows: &[Row],
    added: &Added,
    cfg: &Cfg,
    path: &str,
    ext: &str,
    labels: &Labels,
    cache: &mut SiblingCache,
) -> Option<Script> {
    let own = comment_stats(rows, |i| added.contains(&i) || labels.contains(&i)).majority();
    if own.is_some() {
        return own;
    }
    if let Some(s) = cfg
        .get("comment_language")
        .and_then(Value::as_str)
        .and_then(Script::of_lang)
    {
        return Some(s);
    }
    sibling_majority(path, ext, cfg, cache)
}

/// python `language_lines(rows, added, expected, labels)`: 다른 체계가 우세한 추가 줄(1 기반). 그 낱말이 모두 3개 미만이면 없음.
pub fn language_lines(
    rows: &[Row],
    added: &Added,
    expected: Script,
    labels: &Labels,
) -> Vec<usize> {
    let mut hits = Vec::new();
    let mut words = 0;
    for &i in added {
        let Some(row) = rows.get(i) else { continue };
        if labels.contains(&i) || row.c.is_empty() || has_directive(row) {
            continue;
        }
        let joined = row.c.join(" ");
        if CODE_LIKE.is_match(&joined) {
            continue;
        }
        let counts = word_counts(&joined);
        let other: usize = Script::ALL
            .iter()
            .filter(|s| **s != expected)
            .map(|s| counts[*s as usize])
            .sum();
        if other >= 2 && other > counts[expected as usize] {
            hits.push(i + 1);
            words += other;
        }
    }
    if words >= LANG_MIN_WORDS {
        hits
    } else {
        Vec::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 체계별 낱말 수에서 URL 과 인라인 코드를 빼고, 비기면 체계가 없다.
    #[test]
    fn counts_and_script() {
        // URLs and inline code are not words; latin words need 3 letters
        assert_eq!(
            word_counts("hello wonderful 세상 `code here` https://x.y/z"),
            [2, 1, 0, 0]
        );

        // A tie has no script
        assert_eq!(line_script(&[1, 1, 0, 0]), None);
        assert_eq!(line_script(&[0, 2, 0, 0]), Some(Script::Hangul));
        assert_eq!(Script::of_lang("KO-kr"), Some(Script::Hangul));
    }

    /// 이 모듈의 고정 패턴이 모두 regex crate 로 옮겨지고 엔진이 만들어진다.
    #[test]
    fn fixed_patterns_build() {
        for r in SCRIPT_WORDS.iter() {
            r.check();
        }
        LABEL_LATIN.check();
        LABEL_REASON.check();
        CODE_LIKE.check();
    }
}
