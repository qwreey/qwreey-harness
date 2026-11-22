//! 답변 언어와 그 문자 체계(python `reply_language.py` 의 `SCRIPTS`, `LANG_SCRIPT`, `script_for`, 언어 출처).
//!
//! 언어 출처(좁은 쪽이 이김): 저장소 `.claude/settings.local.json` > `.claude/settings.json` > 사용자 `<config>/settings.json` 의
//! `language`, 없으면 `${CLAUDE_PLUGIN_DATA}/language.json`.

use std::sync::LazyLock;

use harness_hook::HookEnv;
use harness_hook::py::path::{expanduser, join};
use harness_hook::py::surrogate::from_os;
use harness_hook::py::text::strip;
use harness_hook::py::value::Value;
use harness_hook::rx::Regex;

use crate::pyval::{parse_object, py_cmp, read_bytes};

/// 라틴 문자가 아닌 문자 체계. 라틴 문자 언어는 감지하지 않는다.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Script {
    Hangul,
    Japanese,
    Han,
    Cyrillic,
    Arabic,
    Hebrew,
    Thai,
    Greek,
    Devanagari,
}

impl Script {
    /// python `SCRIPTS[script]` 의 글자 범위(정규식 문자 집합 그대로).
    fn ranges(self) -> &'static [(char, char)] {
        match self {
            Script::Hangul => &[
                ('\u{1100}', '\u{11ff}'),
                ('\u{3130}', '\u{318f}'),
                ('\u{ac00}', '\u{d7a3}'),
            ],
            Script::Japanese => &[
                ('\u{3040}', '\u{30ff}'),
                ('\u{31f0}', '\u{31ff}'),
                ('\u{3400}', '\u{4dbf}'),
                ('\u{4e00}', '\u{9fff}'),
            ],
            Script::Han => &[('\u{3400}', '\u{4dbf}'), ('\u{4e00}', '\u{9fff}')],
            Script::Cyrillic => &[('\u{0400}', '\u{04ff}')],
            Script::Arabic => &[('\u{0600}', '\u{06ff}'), ('\u{0750}', '\u{077f}')],
            Script::Hebrew => &[('\u{0590}', '\u{05ff}')],
            Script::Thai => &[('\u{0e00}', '\u{0e7f}')],
            Script::Greek => &[('\u{0370}', '\u{03ff}')],
            Script::Devanagari => &[('\u{0900}', '\u{097f}')],
        }
    }

    /// python `len(SCRIPTS[script].findall(text))`: 이 문자 체계의 글자 수.
    pub fn count(self, text: &str) -> usize {
        let ranges = self.ranges();
        text.chars()
            .filter(|c| ranges.iter().any(|(lo, hi)| (lo..=hi).contains(&c)))
            .count()
    }
}

/// (이름이나 코드 조각, 문자 체계). 앞에서부터 처음 맞는 것(python `LANG_SCRIPT`).
const LANG_SCRIPT: &[(&[&str], Script)] = &[
    (&["korean", "한국어", "한글", "hangul"], Script::Hangul),
    (&["ko"], Script::Hangul),
    (
        &[
            "japanese",
            "\u{65e5}\u{672c}\u{8a9e}",
            "\u{65e5}\u{672c}",
            "\u{306b}\u{307b}\u{3093}\u{3054}",
        ],
        Script::Japanese,
    ),
    (&["ja", "jp"], Script::Japanese),
    (
        &[
            "chinese",
            "\u{4e2d}\u{6587}",
            "\u{6c49}\u{8bed}",
            "\u{6f22}\u{8a9e}",
            "mandarin",
            "cantonese",
        ],
        Script::Han,
    ),
    (&["zh"], Script::Han),
    (
        &[
            "russian",
            "\u{0440}\u{0443}\u{0441}\u{0441}\u{043a}\u{0438}\u{0439}",
            "ukrainian",
            "\u{0443}\u{043a}\u{0440}\u{0430}\u{0457}\u{043d}\u{0441}\u{044c}\u{043a}\u{0430}",
            "bulgarian",
            "serbian",
            "belarusian",
        ],
        Script::Cyrillic,
    ),
    (&["ru", "uk", "bg", "sr", "be"], Script::Cyrillic),
    (
        &[
            "arabic",
            "\u{0627}\u{0644}\u{0639}\u{0631}\u{0628}\u{064a}\u{0629}",
            "persian",
            "farsi",
            "urdu",
        ],
        Script::Arabic,
    ),
    (&["ar", "fa", "ur"], Script::Arabic),
    (
        &["hebrew", "\u{05e2}\u{05d1}\u{05e8}\u{05d9}\u{05ea}"],
        Script::Hebrew,
    ),
    (&["he"], Script::Hebrew),
    (&["thai", "\u{0e44}\u{0e17}\u{0e22}"], Script::Thai),
    (&["th"], Script::Thai),
    (
        &[
            "greek",
            "\u{03b5}\u{03bb}\u{03bb}\u{03b7}\u{03bd}\u{03b9}\u{03ba}\u{03ac}",
        ],
        Script::Greek,
    ),
    (&["el"], Script::Greek),
    (
        &[
            "hindi",
            "\u{0939}\u{093f}\u{0928}\u{094d}\u{0926}\u{0940}",
            "marathi",
            "nepali",
        ],
        Script::Devanagari,
    ),
    (&["hi", "mr", "ne"], Script::Devanagari),
];

static WORD: LazyLock<Regex> = LazyLock::new(|| Regex::new(r"[^\W\d_]+(?:-[^\W\d_]+)?"));

/// python `script_for(language)`: 언어 설정값(자유 글)의 문자 체계. 라틴 문자 언어나 모르는 값은 `None`.
///
/// 3자 이하 ASCII 코드(`ko`, `ja`)는 낱말 앞 조각(`ko-KR` 의 `ko`)과 같아야 맞고, 그 밖의 이름은 글 안에 있으면 맞는다.
pub fn script_for(language: &str) -> Option<Script> {
    let low = strip(language).to_lowercase();
    if low.is_empty() {
        return None;
    }
    let words: Vec<&str> = WORD
        .find_iter(&low)
        .into_iter()
        .map(|m| &low[m.start()..m.end()])
        .collect();
    for (keys, script) in LANG_SCRIPT {
        for key in *keys {
            let short_code = key.chars().count() <= 3 && key.is_ascii();
            let hit = if short_code {
                words.iter().any(|w| w.split('-').next() == Some(*key))
            } else {
                low.contains(key)
            };
            if hit {
                return Some(*script);
            }
        }
    }
    None
}

/// python `reply_env.config_dir()`: `$CLAUDE_CONFIG_DIR`, 없으면 `~/.claude`.
pub fn config_dir(ctx: &HookEnv) -> String {
    match ctx.env.get_os_nonempty("CLAUDE_CONFIG_DIR") {
        Some(dir) => from_os(dir),
        None => expanduser("~/.claude", &ctx.env),
    }
}

/// python `data_dir()`: `$CLAUDE_PLUGIN_DATA`, 없으면 `<config>/plugins/data/qwreey-reply-language*` 의 첫 폴더(이름 순서).
pub fn data_dir(ctx: &HookEnv) -> Option<String> {
    if let Some(dir) = ctx.env.get_os_nonempty("CLAUDE_PLUGIN_DATA") {
        return Some(from_os(dir));
    }
    let base = join(&join(&config_dir(ctx), "plugins"), "data");
    let entries = std::fs::read_dir(harness_hook::py::fs::os_path(&base)?).ok()?;
    let mut hits: Vec<String> = entries
        .flatten()
        .map(|e| from_os(&e.file_name()))
        .filter(|n| n.starts_with("qwreey-reply-language"))
        .collect();
    hits.sort_by(|a, b| py_cmp(a, b));
    hits.first().map(|name| join(&base, name))
}

// json.load(open(path)).get("language"): 글이고 공백이 아니면 앞뒤 공백을 뗀 것, 무엇이든 실패면 None
fn language_in(path: &str) -> Option<String> {
    let dict = parse_object(&read_bytes(path)?).ok()?;
    match dict.get("language") {
        Some(Value::Str(s)) if !strip(s).is_empty() => Some(strip(s).to_owned()),
        _ => None,
    }
}

/// python `settings_language(root)`: 저장소 local, 저장소, 사용자 settings 의 `language`.
pub fn settings_language(ctx: &HookEnv, root: &str) -> Option<String> {
    let claude = join(root, ".claude");
    let candidates = [
        join(&claude, "settings.local.json"),
        join(&claude, "settings.json"),
        join(&config_dir(ctx), "settings.json"),
    ];
    candidates.iter().find_map(|p| language_in(p))
}

/// python `stored_language()`: 이 플러그인이 물어 저장한 언어.
pub fn stored_language(ctx: &HookEnv) -> Option<String> {
    language_in(&join(&data_dir(ctx)?, "language.json"))
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 이름은 글 안에서, 짧은 코드는 낱말 앞 조각으로 찾고, 라틴 문자 언어는 없다.
    #[test]
    fn scripts_like_python() {
        // Names and native names anywhere in the text
        assert_eq!(script_for(" Korean "), Some(Script::Hangul));
        assert_eq!(script_for("한국어로"), Some(Script::Hangul));
        assert_eq!(
            script_for("\u{65e5}\u{672c}\u{8a9e}"),
            Some(Script::Japanese)
        );

        // Short codes only as a word head
        assert_eq!(script_for("ko-KR"), Some(Script::Hangul));
        assert_eq!(
            script_for("kokomo"),
            None,
            "`ko` inside a word is not the code"
        );
        assert_eq!(
            script_for("zh_TW"),
            Some(Script::Han),
            "`_` ends a word, so `zh` is one"
        );

        // Latin-script languages are not checked
        assert_eq!(script_for("English"), None);
        assert_eq!(script_for(""), None);
    }

    /// 문자 체계 글자 세기는 정규식 문자 집합과 같은 범위다.
    #[test]
    fn counts_script_letters() {
        assert_eq!(Script::Hangul.count("한글 abc ㄱ"), 3);
        assert_eq!(
            Script::Han.count("日本 \u{3042}"),
            2,
            "kana is Japanese, not Han"
        );
    }
}
