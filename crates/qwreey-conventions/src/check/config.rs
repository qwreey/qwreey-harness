//! 저장소 설정 `conventions.json`(python `load_cfg`, `compile_patterns`, `excluded`).
//!
//! 설정은 사람이 쓴 JSON 이라 값의 타입이 틀릴 수 있다. 값은 python dict 그대로 들고, 읽는 곳마다 python 이 그 값을 쓰는
//! 꼴(`x or []`, `int(x)`, `isinstance`)을 따른다. python 이 예외로 끝나는 값은 [`Halt::PyError`] 다.

use harness_hook::py::fnmatch::fnmatch;
use harness_hook::py::fs;
use harness_hook::py::json_load::loads;
use harness_hook::py::num::parse_int;
use harness_hook::py::path::{basename, join};
use harness_hook::py::re::{self, Flags, Regex};
use harness_hook::py::value::{Dict, Value};

use super::chars::Allow;
use crate::edit::{SKIP_PARTS, SKIP_SUFFIX};
use crate::halt::{Halt, Result};

/// 이력 표지 패턴(python `PATTERNS`). 이름 순서가 곧 검사와 지우기 순서다.
pub fn builtin_patterns() -> Vec<(&'static str, String)> {
    // 과거 시제 음절: 받침이 ㅆ 인 한글 음절(했, 였, 었 ...)에서 현재를 말하는 있, 겠을 뺀 것
    let past: String = (0..19 * 21)
        .filter_map(|i| char::from_u32(0xAC00 + i * 28 + 20))
        .filter(|c| !"있겠".contains(*c))
        .collect();
    let clause_start = r"(?:^|[.;:!?]\s+|\(\s*)";
    vec![
        ("ledger", r"\b[A-Z]{1,2}-?\d{2,4}\b".to_owned()),
        ("date", r"\b20\d\d-\d\d-\d\d\b".to_owned()),
        ("round", r"\bround\s*\d+\b|라운드\s*\d+|감사\s*\d+\s*차".to_owned()),
        ("path", r"\.claude/|(?<![\w-])session/|(?<![\w-])audit/".to_owned()),
        (
            "decision",
            r"사용자\s*(?:결정|지시|요청|합의|말)|\bper (?:the )?user\b|\bas (?:the user )?(?:discussed|decided|agreed)\b|\bthe user (?:decided|asked|wanted|requested)\b".to_owned(),
        ),
        (
            "narration",
            format!(
                r"{clause_start}(?:Previously(?=,|\s+\w)|(?:[Ii]t|[Tt]his|[Ww]e|[Tt]hey)\s+used\s+to\b)|예전(?:에는|엔)|(?:^|[.;:!?,(]\s*)이전(?:에는|엔)|기존(?:에는|엔)[^.\n]*?[{past}](?:다|습니다|어요|죠|던|지만|는데)"
            ),
        ),
    ]
}

/// 내장 공개 식별자, 표준 번호(python `BUILTIN_PUBLIC`): 줄에서 먼저 지운 뒤 검사한다.
const BUILTIN_PUBLIC: &[&str] = &[
    r"error-code:\s*\S+",
    r"\bR(?:6|15)\b",
    r"\bES\d{4}\b",
    r"\bH26[45]\b",
    r"\bUTF-?\d+\b",
    r"\bSHA-?\d+\b",
    r"\bP\d{2,3}\b(?=\s*(?:p|fps|hz))",
    r"\b[A-Z]{1,2}\d{2,4}(?=px|pt|ms|hz|fps|kb|mb|gb)",
    r"\b[FIUS](?:8|16|32|64|128)\b",
    r"\bX86\b",
    r"\bC(?:89|90|99|11|17|23)\b",
    r"\bTS\d{4}\b",
    r"\bE0\d{3}\b",
];

/// 읽어 둔 저장소 설정(python `DEFAULTS` 에 사용자 dict 를 덮은 것).
#[derive(Clone, Debug, PartialEq)]
pub struct Cfg {
    dict: Dict,
}

/// 컴파일한 이력 패턴과 공개 식별자(python `compile_patterns` 의 결과).
#[derive(Debug)]
pub struct Patterns {
    /// (이름, 정규식), python dict 순서.
    pub history: Vec<(String, Regex)>,
    pub public: Vec<Regex>,
}

impl Patterns {
    /// 이름의 패턴(python `pats[k]`).
    pub fn get(&self, name: &str) -> Option<&Regex> {
        self.history.iter().find(|(k, _)| k == name).map(|(_, r)| r)
    }
}

fn defaults() -> Dict {
    let mut d = Dict::new();
    d.insert("allow_ref_tail", Value::Bool(true));
    d.insert("public_ids", Value::List(Vec::new()));
    d.insert("exclude", Value::List(Vec::new()));
    d.insert("patterns", Value::Dict(Dict::new()));
    d.insert("min_reason_words", Value::Int(3));
    d.insert("comment_language", Value::Null);
    d.insert("allow_chars", Value::List(Vec::new()));
    d.insert("label_language", Value::Str("en".to_owned()));
    d.insert("layout", Value::Dict(Dict::new()));
    d
}

// python 의 `for x in value` 가 도는 값들(목록 원소, dict 키, 글자). 돌 수 없는 참 값은 TypeError
fn iter_items(value: Option<&Value>) -> Result<Vec<Value>> {
    Ok(match value {
        None => Vec::new(),
        Some(v) if !v.truthy() => Vec::new(),
        Some(Value::List(items)) => items.clone(),
        Some(Value::Dict(d)) => d.iter().map(|(k, _)| Value::Str(k.to_owned())).collect(),
        Some(Value::Str(s)) => s.chars().map(|c| Value::Str(c.to_string())).collect(),
        Some(_) => return Err(Halt::PyError("a setting is not iterable")),
    })
}

/// 사람이 쓴 정규식 하나를 python 처럼 읽는다. `re.error` 는 `Ok(None)`(python 이 건너뛴다).
fn compile_user(pattern: &Value, flags: Flags) -> Result<Option<Regex>> {
    let Value::Str(p) = pattern else {
        return Err(Halt::PyError("a pattern is not a string"));
    };
    match Regex::with_flags(p, flags) {
        Ok(r) => Ok(Some(r)),
        Err(re::Error::Syntax(_)) => Ok(None),
        Err(re::Error::Overflow) => Err(Halt::PyError("OverflowError in a pattern")),
        Err(re::Error::Unsupported(_) | re::Error::TooDeep) => {
            Err(Halt::Unported("a pattern this regex engine does not read"))
        }
    }
}

impl Cfg {
    /// python `load_cfg(root)`: 저장소 설정 파일을 덮은 값. 읽지 못하면 기본값.
    ///
    /// 파일은 `.claude` 폴더의 `conventions.json`, 없으면 예전 이름 `comments.json` 이다.
    pub fn load(root: &str) -> Cfg {
        let mut dict = defaults();
        for name in ["conventions.json", "comments.json"] {
            let fp = join(&join(root, ".claude"), name);
            if !fs::exists(&fp) {
                continue;
            }
            if let Some(Value::Dict(user)) = fs::read_text(&fp)
                .ok()
                .and_then(|t| loads(&t).ok())
                .as_ref()
            {
                for (k, v) in user.iter() {
                    dict.insert(k, v.clone());
                }
            }
            break;
        }
        Cfg { dict }
    }

    /// 기본값만(python `DEFAULTS`, 형제 파일 통계에 cfg 가 없을 때).
    pub fn defaults() -> Cfg {
        Cfg { dict: defaults() }
    }

    /// 값 하나(python `cfg.get(key)`).
    pub fn get(&self, key: &str) -> Option<&Value> {
        self.dict.get(key)
    }

    /// python `cfg.get("allow_ref_tail", True)` 의 참거짓.
    pub fn allow_ref_tail(&self) -> bool {
        self.get("allow_ref_tail").is_none_or(Value::truthy)
    }

    /// python `int(cfg.get("min_reason_words", 3))`.
    pub fn min_reason_words(&self) -> Result<i128> {
        let fail = Halt::PyError("min_reason_words is not an int");
        match self.get("min_reason_words") {
            None => Ok(3),
            Some(Value::Int(i)) => Ok(*i),
            Some(Value::Bool(b)) => Ok(i128::from(*b)),
            Some(Value::Float(f)) if f.is_finite() => Ok(f.trunc() as i128),
            Some(Value::Str(s)) => parse_int(s).ok_or(fail),
            Some(Value::BigInt(_)) => Err(Halt::Unported("a huge min_reason_words")),
            Some(_) => Err(fail),
        }
    }

    /// python `cfg.get("allow_chars") or []`.
    pub fn allow(&self) -> Result<Allow> {
        Allow::from_value(self.get("allow_chars"))
    }

    /// python `compile_patterns(cfg)`: 이름별로 덮어쓴 이력 패턴과 공개 식별자. 읽지 못하는 패턴(`re.error`)은 뺀다.
    pub fn patterns(&self) -> Result<Patterns> {
        let mut pats: Vec<(String, Value)> = builtin_patterns()
            .into_iter()
            .map(|(k, v)| (k.to_owned(), Value::Str(v)))
            .collect();

        // Overrides by name, null removes
        match self.get("patterns") {
            Some(Value::Dict(over)) => {
                for (k, v) in over.iter() {
                    let slot = pats.iter().position(|(name, _)| name == k);
                    match (v.truthy(), slot) {
                        (true, Some(i)) => pats[i].1 = v.clone(),
                        (true, None) => pats.push((k.to_owned(), v.clone())),
                        (false, Some(i)) => {
                            pats.remove(i);
                        }
                        (false, None) => {}
                    }
                }
            }
            Some(v) if v.truthy() => return Err(Halt::PyError("patterns is not a dict")),
            _ => {}
        }

        // Compile both lists
        let mut history = Vec::new();
        for (k, v) in pats {
            let flags = if k == "round" || k == "decision" {
                Flags::IGNORECASE
            } else {
                Flags::NONE
            };
            if let Some(r) = compile_user(&v, flags)? {
                history.push((k, r));
            }
        }
        let mut public = Vec::new();
        let user_public = iter_items(self.get("public_ids"))?;
        let builtin = BUILTIN_PUBLIC.iter().map(|p| Value::Str((*p).to_owned()));
        for v in builtin.chain(user_public) {
            if let Some(r) = compile_user(&v, Flags::NONE)? {
                public.push(r);
            }
        }
        Ok(Patterns { history, public })
    }

    /// python `excluded(path, rel, cfg)`: 건너뛸 폴더 조각, 생성 파일 접미사, 설정의 exclude 글롭.
    pub fn excluded(&self, path: &str, rel: &str) -> Result<bool> {
        if pathlib_parts(rel).iter().any(|p| SKIP_PARTS.contains(p))
            || SKIP_SUFFIX.iter().any(|s| path.ends_with(s))
        {
            return Ok(true);
        }
        for g in iter_items(self.get("exclude"))? {
            let Value::Str(g) = &g else {
                return Err(Halt::PyError("an exclude glob is not a string"));
            };
            let hit = glob(rel, g)? || glob(basename(rel), g)? || glob(rel, &format!("*/{g}"))?;
            if hit {
                return Ok(true);
            }
        }
        Ok(false)
    }
}

fn glob(name: &str, pat: &str) -> Result<bool> {
    fnmatch(name, pat).map_err(|e| match e {
        re::Error::Unsupported(_) | re::Error::TooDeep => {
            Halt::Unported("a glob this regex engine does not read")
        }
        _ => Halt::PyError("a glob python cannot compile"),
    })
}

/// python `Path(rel).parts`(POSIX): 빈 조각과 `.` 을 뺀 조각들, 절대 경로면 맨 앞에 `/`.
pub fn pathlib_parts(rel: &str) -> Vec<&str> {
    let mut parts: Vec<&str> = Vec::new();
    if rel.starts_with("//") && !rel.starts_with("///") {
        parts.push("//");
    } else if rel.starts_with('/') {
        parts.push("/");
    }
    parts.extend(rel.split('/').filter(|p| !p.is_empty() && *p != "."));
    parts
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 내장 패턴이 모두 읽히고 대표 글에 python 과 같게 맞는다.
    #[test]
    fn builtin_patterns_compile() {
        // All builtin patterns compile
        let cfg = Cfg::defaults();
        let pats = cfg.patterns().unwrap();
        assert_eq!(pats.history.len(), 6);
        assert_eq!(pats.public.len(), BUILTIN_PUBLIC.len());

        // Dates and past-tense change narration match
        assert!(pats.get("date").unwrap().is_match("on 2026-11-20 we"));
        assert!(
            pats.get("narration")
                .unwrap()
                .is_match("기존에는 키가 있었다")
        );
        assert!(
            !pats
                .get("narration")
                .unwrap()
                .is_match("기존에는 키가 있을 수 있다")
        );
    }

    /// 경로 조각과 exclude 글롭이 python excluded 와 같게 거른다.
    #[test]
    fn parts_and_excludes() {
        // pathlib drops empty and `.` parts
        assert_eq!(pathlib_parts("a//b/./c"), vec!["a", "b", "c"]);

        // An exclude glob, a skipped folder, and a plain path
        let mut cfg = Cfg::defaults();
        cfg.dict
            .insert("exclude", Value::List(vec![Value::Str("docs/**".into())]));
        assert!(cfg.excluded("/r/docs/x/y.py", "docs/x/y.py").unwrap());
        assert!(
            cfg.excluded("/r/node_modules/a.py", "node_modules/a.py")
                .unwrap()
        );
        assert!(!cfg.excluded("/r/src/a.py", "src/a.py").unwrap());
    }
}
