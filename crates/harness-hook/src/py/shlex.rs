//! python `shlex.split(text)`(posix, 주석 없음): 공백으로 나눈 낱말, 따옴표와 `\` 를 푼 글.
//!
//! 상태 기계는 python `shlex.read_token` 을 그대로 옮겼다(`whitespace_split=True`, `commenters=""`).
//! 작은따옴표 안은 그대로, 큰따옴표 안의 `\` 는 `"` 와 `\` 앞에서만 escape 다. 따옴표만 있던 빈 낱말(`''`)도 낱말이다.

use std::fmt;

const QUOTES: &str = "'\"";
const WHITESPACE: &str = " \t\r\n";

/// 낱말을 읽지 못한 이유(python ValueError). 글은 python 의 예외 글과 같다.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SplitError {
    NoClosingQuotation,
    NoEscapedCharacter,
}

impl fmt::Display for SplitError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(match self {
            SplitError::NoClosingQuotation => "No closing quotation",
            SplitError::NoEscapedCharacter => "No escaped character",
        })
    }
}

impl std::error::Error for SplitError {}

#[derive(Clone, Copy, PartialEq, Eq)]
enum State {
    /// 낱말 사이.
    Space,
    /// 낱말 안.
    Word,
    /// 따옴표 안. 값은 여는 따옴표.
    Quote(char),
    /// `\` 다음. 값은 돌아갈 따옴표(낱말 안이면 `None`).
    Escape(Option<char>),
}

/// python `shlex.split(text)`.
pub fn split(text: &str) -> Result<Vec<String>, SplitError> {
    let mut out = Vec::new();
    let mut token = String::new();
    let mut quoted = false;
    let mut state = State::Space;

    for c in text.chars() {
        match state {
            // Outside quotes: whitespace ends a word, quotes and `\` change state
            State::Space | State::Word if WHITESPACE.contains(c) => {
                if state == State::Word {
                    out.push(std::mem::take(&mut token));
                    quoted = false;
                }
                state = State::Space;
            }
            State::Space | State::Word if c == '\\' => state = State::Escape(None),
            State::Space | State::Word if QUOTES.contains(c) => state = State::Quote(c),
            State::Space | State::Word => {
                token.push(c);
                state = State::Word;
            }

            // Inside quotes
            State::Quote(q) => {
                quoted = true;
                if c == q {
                    state = State::Word;
                } else if c == '\\' && q == '"' {
                    state = State::Escape(Some(q));
                } else {
                    token.push(c);
                }
            }

            // After a backslash
            State::Escape(back) => {
                // 큰따옴표 안에서는 따옴표와 `\` 만 escape 된다
                if let Some(q) = back
                    && c != '\\'
                    && c != q
                {
                    token.push('\\');
                }
                token.push(c);
                state = back.map_or(State::Word, State::Quote);
            }
        }
    }

    // End of text
    match state {
        State::Quote(_) => Err(SplitError::NoClosingQuotation),
        State::Escape(_) => Err(SplitError::NoEscapedCharacter),
        State::Word => {
            if !token.is_empty() || quoted {
                out.push(token);
            }
            Ok(out)
        }
        State::Space => Ok(out),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 따옴표, escape, 빈 낱말, 오류 글이 python `shlex.split` 과 같다.
    #[test]
    fn splits_like_python() {
        // Quotes and escapes join words
        assert_eq!(split(r#"a "b c" d\ e"#).unwrap(), ["a", "b c", "d e"]);
        assert_eq!(split(r#""a\"b\x" 'q\'"#).unwrap(), ["a\"b\\x", "q\\"]);

        // Comments are off in shlex.split, and quoted empty words stay
        assert_eq!(split("x#y '' \"\"").unwrap(), ["x#y", "", ""]);
        assert_eq!(split("  ").unwrap(), Vec::<String>::new());
        assert_eq!(split("a'b'c").unwrap(), ["abc"]);

        // Errors carry python's ValueError text
        assert_eq!(split("\"abc"), Err(SplitError::NoClosingQuotation));
        assert_eq!(split("abc\\"), Err(SplitError::NoEscapedCharacter));
        assert_eq!(
            SplitError::NoClosingQuotation.to_string(),
            "No closing quotation"
        );
    }
}
