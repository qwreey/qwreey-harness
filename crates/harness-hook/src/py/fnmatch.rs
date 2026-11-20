//! python `fnmatch.fnmatch(name, pat)`(POSIX, 3.14): 셸 글롭을 python 과 같은 정규식으로 옮겨 [`crate::py::re`] 로 맞춘다.
//!
//! why not glob, globset: python 은 글롭을 정규식(`fnmatch.translate`)으로 바꿔 맞춘다. `[` 가 닫히지 않을 때, 빈 범위,
//! `[!]`, `*` 가 `/` 를 넘는 것까지 그 번역을 따라야 저장소 설정(exclude, ignore)의 판정이 python 판과 같다.

use crate::py::re::{self, Flags, Regex};

/// python `fnmatch.fnmatch(name, pat)`. POSIX 라 대소문자를 그대로 본다(`os.path.normcase` 가 바꾸지 않는다).
///
/// 번역한 정규식을 python 이 읽지 못하면(`re.error`) python 도 예외로 끝난다: 그 오류를 돌려준다.
pub fn fnmatch(name: &str, pat: &str) -> Result<bool, re::Error> {
    Ok(compile(pat)?.match_start(name).is_some())
}

/// `pat` 을 맞출 정규식(python `re.compile(fnmatch.translate(pat))`).
///
/// python 은 `(?s:...)\z` 로 감싸지만 여기 정규식은 범위 플래그가 없어, 같은 뜻으로 DOTALL 을 주고 `(?:...)\z` 로 감싼다.
pub fn compile(pat: &str) -> Result<Regex, re::Error> {
    let flags = Flags {
        dotall: true,
        ..Flags::NONE
    };
    Regex::with_flags(&format!("(?:{})\\z", translate_body(pat)), flags)
}

/// python `fnmatch.translate` 의 `(?s:` 와 `)\z` 안쪽.
pub fn translate_body(pat: &str) -> String {
    let (parts, stars) = translate_parts(pat);
    let Some((&first, rest)) = stars.split_first() else {
        return parts.concat();
    };

    // STAR fixed STAR fixed ...: 안쪽 짝은 되돌아가지 않는 최소 일치
    let mut out = parts[..first].concat();
    let mut i = first + 1;
    for &j in rest {
        out.push_str("(?>.*?");
        out.push_str(&parts[i..j].concat());
        out.push(')');
        i = j + 1;
    }
    out.push_str(".*");
    out.push_str(&parts[i..].concat());
    out
}

// python fnmatch._translate(pat, "*", "."): 조각 목록과 `*` 조각의 자리
fn translate_parts(pat: &str) -> (Vec<String>, Vec<usize>) {
    let chars: Vec<char> = pat.chars().collect();
    let n = chars.len();
    let mut res: Vec<String> = Vec::new();
    let mut stars = Vec::new();

    let mut i = 0;
    while i < n {
        let c = chars[i];
        i += 1;
        match c {
            '*' => {
                stars.push(res.len());
                res.push("*".to_owned());
                while i < n && chars[i] == '*' {
                    i += 1;
                }
            }
            '?' => res.push(".".to_owned()),
            '[' => i = bracket(&chars, i, &mut res),
            _ => res.push(re::escape(&c.to_string())),
        }
    }
    (res, stars)
}

// `[` 다음 자리 i 부터 읽은 글자 묶음 조각을 res 에 넣고 다음 자리를 돌려준다
fn bracket(chars: &[char], start: usize, res: &mut Vec<String>) -> usize {
    let n = chars.len();
    let mut j = start;
    if j < n && chars[j] == '!' {
        j += 1;
    }
    if j < n && chars[j] == ']' {
        j += 1;
    }
    while j < n && chars[j] != ']' {
        j += 1;
    }
    if j >= n {
        res.push("\\[".to_owned());
        return start;
    }

    // 범위를 뺀 글자 묶음 본문
    let stuff_chars = &chars[start..j];
    let stuff: String = if !stuff_chars.contains(&'-') {
        stuff_chars.iter().collect::<String>().replace('\\', "\\\\")
    } else {
        range_chunks(chars, start, j)
            .iter()
            .map(|s| s.replace('\\', "\\\\").replace('-', "\\-"))
            .collect::<Vec<_>>()
            .join("-")
    };

    // 빈 묶음, 부정만 있는 묶음, 집합 연산 글자
    if stuff.is_empty() {
        res.push("(?!)".to_owned());
    } else if stuff == "!" {
        res.push(".".to_owned());
    } else {
        let mut stuff: String = stuff
            .chars()
            .flat_map(|c| {
                let escape = matches!(c, '&' | '~' | '|').then_some('\\');
                escape.into_iter().chain(std::iter::once(c))
            })
            .collect();
        if let Some(rest) = stuff.strip_prefix('!') {
            stuff = format!("^{rest}");
        } else if stuff.starts_with(['^', '[']) {
            stuff = format!("\\{stuff}");
        }
        res.push(format!("[{stuff}]"));
    }
    j + 1
}

// `-` 로 나눈 범위 조각. 뒤 조각의 첫 글자보다 큰 끝 글자를 가진 빈 범위는 합친다(python 판과 같은 순서)
fn range_chunks(chars: &[char], start: usize, j: usize) -> Vec<String> {
    let find_dash = |from: usize| (from..j).find(|&k| chars[k] == '-');
    let mut chunks: Vec<Vec<char>> = Vec::new();
    let mut i = start;
    let mut k = if chars[start] == '!' {
        start + 2
    } else {
        start + 1
    };
    while let Some(dash) = find_dash(k) {
        chunks.push(chars[i..dash].to_vec());
        i = dash + 1;
        k = dash + 3;
    }
    let tail = &chars[i..j];
    if !tail.is_empty() {
        chunks.push(tail.to_vec());
    } else if let Some(last) = chunks.last_mut() {
        last.push('-');
    }

    for k in (1..chunks.len()).rev() {
        let (Some(&end), Some(&next)) = (chunks[k - 1].last(), chunks[k].first()) else {
            continue;
        };
        if end > next {
            let merged: Vec<char> = chunks[k - 1][..chunks[k - 1].len() - 1]
                .iter()
                .chain(&chunks[k][1..])
                .copied()
                .collect();
            chunks[k - 1] = merged;
            chunks.remove(k);
        }
    }
    chunks
        .into_iter()
        .map(|c| c.into_iter().collect())
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn m(name: &str, pat: &str) -> bool {
        fnmatch(name, pat).unwrap()
    }

    /// 글롭이 python fnmatch 와 같은 이름에 맞는다(`*` 는 `/` 도 넘고, 닫히지 않은 `[` 는 글자다).
    #[test]
    fn matches_like_python() {
        assert!(m("docs/a/b.md", "docs/**"));
        assert!(m("a.md", "*.md"));
        assert!(m("x/a.md", "*.md"));
        assert!(!m("a.mdx", "*.md"));
        assert!(m("a\nb", "a?b"));
        assert!(m("[", "["));
        assert!(m("a", "[!b]"));
        assert!(!m("b", "[!b]"));
        assert!(m("-", "[a-]"));
        assert!(m("b", "[a-c]"));
        assert!(!m("b", "[c-a]"));
        assert!(!m("x", "[!]x"));
        assert!(m("abcxyzde", "a*x*e"));
        assert!(m("&", "[&&]"));
    }

    /// 번역한 정규식 본문이 python 3.14 `fnmatch.translate` 의 안쪽과 같은 글이다.
    #[test]
    fn translates_like_python() {
        assert_eq!(translate_body("*.py"), r".*\.py");
        assert_eq!(translate_body("a*b*c"), "a(?>.*?b).*c");
        assert_eq!(translate_body("[!a-c]"), "[^a-c]");
        assert_eq!(translate_body("[z-a]"), "(?!)");
        assert_eq!(translate_body("[!]"), r"\[!\]");
        assert_eq!(translate_body("[^x]"), r"[\^x]");
        assert_eq!(translate_body("[a-]"), r"[a\-]");
        assert_eq!(translate_body("[a-c-e]"), r"[a-c\-e]");
        assert_eq!(translate_body("[b-a-c]"), r"[\-c]");
        assert_eq!(translate_body("[&&]"), r"[\&\&]");
    }
}
