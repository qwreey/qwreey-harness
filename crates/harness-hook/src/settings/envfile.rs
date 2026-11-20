//! harness.env 파일 형식: 한 줄에 `KEY=VALUE`(python `harness_env.parse`, `_value`, `expand`).
//!
//! why not dotenvy: 따옴표, 줄 끝 주석, `$NAME` 풀기, 환경 변수 우선이 python 판과 바이트로 같아야 한다.
//!
//! - `#` 로 시작하는 줄과 빈 줄은 무시한다. 맞지 않는 줄도 조용히 건너뛴다. `export ` 접두는 떼어 낸다.
//! - 값의 바깥 따옴표(`'...'`, `"..."`)는 벗긴다. 따옴표가 없으면 공백 뒤 `#` 부터가 줄 끝 주석이다.
//! - `${NAME}`, `$NAME` 은 앞에서 정한 키(아래 층 포함), 없으면 환경 변수, 없으면 빈 값. 작은따옴표 안에서도 푼다.
//! - 풀고 난 값이 `~` 로 시작하면 홈으로 바꾼다.
//! - 같은 이름의 환경 변수가 있으면 파일 값 대신 그것이다.
//! - `skip` 에 든 키의 줄은 통째로 건너뛴다. 저장소 층이 사용자 전용 키를 정하지 못하게 할 때, 그 줄의 값이
//!   같은 파일의 `$NAME` 으로 새지 않게 한다(`$NAME` 은 아래 층의 값을 본다).

use std::collections::{BTreeMap, BTreeSet};

use crate::env::Env;
use crate::py::path::expanduser;
use crate::py::text::{is_space, splitlines, strip};

/// 키 -> 값.
pub type Values = BTreeMap<String, String>;

/// 파일 글 하나를 읽은 키와 값(python `parse`). `base` 는 아래 층까지 합친 값으로, `$NAME` 을 풀 때 본다.
///
/// `skip` 은 이 파일이 정하지 못하는 키다. 그 줄은 결과에도 `$NAME` 에도 들어가지 않는다.
pub fn parse(text: &str, base: &Values, env: &Env, skip: &BTreeSet<&str>) -> Values {
    let mut scope = base.clone();
    let mut out = Values::new();
    for line in splitlines(text) {
        // 빈 줄, 주석, 맞지 않는 줄은 건너뛴다
        if strip(line).is_empty() || line.trim_start_matches(is_space).starts_with('#') {
            continue;
        }
        let Some((key, raw)) = split_assignment(line).filter(|(key, _)| !skip.contains(key)) else {
            continue;
        };

        // 환경 변수가 이긴다
        let value = match env.get(key) {
            Some(from_env) => from_env.to_owned(),
            None => expand(&unquote(raw), &scope, env),
        };
        scope.insert(key.to_owned(), value.clone());
        out.insert(key.to_owned(), value);
    }
    out
}

// python 정규식 ^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$
fn split_assignment(line: &str) -> Option<(&str, &str)> {
    let rest = line.trim_start_matches(is_space);
    if let Some(after) = rest.strip_prefix("export") {
        let name_start = after.trim_start_matches(is_space);
        if name_start.len() < after.len()
            && let Some(hit) = key_and_raw(name_start)
        {
            return Some(hit);
        }
    }
    key_and_raw(rest)
}

fn key_and_raw(s: &str) -> Option<(&str, &str)> {
    let len = name_len(s);
    if len == 0 {
        return None;
    }
    let raw = s[len..].trim_start_matches(is_space).strip_prefix('=')?;
    Some((&s[..len], raw))
}

// [A-Za-z_][A-Za-z0-9_]* 의 길이(바이트)
fn name_len(s: &str) -> usize {
    let bytes = s.as_bytes();
    if !bytes
        .first()
        .is_some_and(|b| b.is_ascii_alphabetic() || *b == b'_')
    {
        return 0;
    }
    bytes
        .iter()
        .take_while(|b| b.is_ascii_alphanumeric() || **b == b'_')
        .count()
}

/// 값 자리의 글에서 따옴표와 줄 끝 주석을 걷어 낸다(python `_value`).
pub fn unquote(raw: &str) -> String {
    let raw = strip(raw);

    // 바깥 따옴표: 닫는 따옴표가 없으면 끝까지
    if let Some(quote) = raw.chars().next().filter(|c| *c == '\'' || *c == '"') {
        let inner = &raw[1..];
        return inner
            .find(quote)
            .map_or(inner, |end| &inner[..end])
            .to_owned();
    }

    // 공백 뒤 # 부터 주석
    let cut = raw
        .char_indices()
        .zip(raw.chars().skip(1))
        .find(|((_, c), next)| is_space(*c) && *next == '#')
        .map_or(raw.len(), |((i, _), _)| i);
    strip(&raw[..cut]).to_owned()
}

/// `${NAME}`, `$NAME` 을 풀고 맨 앞 `~` 를 홈으로(python `expand`). 이름은 `scope`, 없으면 환경 변수에서 찾는다.
pub fn expand(s: &str, scope: &Values, env: &Env) -> String {
    let mut out = String::with_capacity(s.len());
    let mut rest = s;
    while let Some(dollar) = rest.find('$') {
        out.push_str(&rest[..dollar]);
        let after = &rest[dollar + 1..];
        match reference(after) {
            Some((name, used)) => {
                let value = scope
                    .get(name)
                    .map(String::as_str)
                    .or_else(|| env.get(name))
                    .unwrap_or("");
                out.push_str(value);
                rest = &after[used..];
            }
            None => {
                out.push('$');
                rest = after;
            }
        }
    }
    out.push_str(rest);

    if out.starts_with('~') {
        expanduser(&out, env)
    } else {
        out
    }
}

// `$` 뒤의 (이름, 쓴 바이트 수). `${NAME}` 을 먼저 보고, 아니면 `$NAME`
fn reference(after: &str) -> Option<(&str, usize)> {
    if let Some(inner) = after.strip_prefix('{') {
        let len = name_len(inner);
        if len > 0 && inner[len..].starts_with('}') {
            return Some((&inner[..len], len + 2));
        }
    }
    let len = name_len(after);
    (len > 0).then(|| (&after[..len], len))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_quotes_comments_and_references() {
        let env = Env::from_pairs([("HOME", "/h"), ("FROM_ENV", "e")]);
        let text = "# c\nexport A=1 # note\nB='$A x' #k\nexportC=${A}${MISSING}$A_\nD = ~/x\nFROM_ENV=file\n bad line\n";
        let got = parse(text, &Values::new(), &env, &BTreeSet::new());
        let want: Values = [
            ("A", "1"),
            ("B", "1 x"),
            ("exportC", "1"),
            ("D", "/h/x"),
            ("FROM_ENV", "e"),
        ]
        .into_iter()
        .map(|(k, v)| (k.to_owned(), v.to_owned()))
        .collect();
        assert_eq!(got, want);
    }
}
