//! python `shlex.shlex(text, posix=True, punctuation_chars=True)` 에 `whitespace_split = True` 를 준 낱말 읽기.
//!
//! self-match-guard 가 pgrep, pkill 의 인자를 읽을 때 쓴다. 상태 기계는 python `shlex.read_token` 을 그대로 옮겼다:
//! `#` 은 그 줄 끝까지 주석이고, 큰따옴표 안의 `\` 는 `"` 와 `\` 앞에서만 escape 다.

const PUNCTUATION: &str = "();<>|&";
const QUOTES: &str = "'\"";
const WHITESPACE: &str = " \t\r\n";

/// 낱말을 읽지 못한 이유(python 은 ValueError).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum LexError {
    NoClosingQuotation,
    NoEscapedCharacter,
}

/// 낱말을 하나씩 내는 읽개.
pub struct Lexer {
    chars: Vec<char>,
    pos: usize,
    /// 구두점 낱말 뒤에서 되돌려 둔 글자 하나.
    pushback: Option<char>,
    state: State,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum State {
    /// 낱말 사이.
    Space,
    /// 낱말 안(`a`).
    Word,
    /// 구두점 낱말 안(`c`).
    Punct,
    /// 따옴표 안. 값은 여는 따옴표.
    Quote(char),
    /// `\` 다음. 값은 돌아갈 상태(낱말 또는 큰따옴표).
    Escape(Escaped),
    /// 글 끝.
    Eof,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Escaped {
    Word,
    Quote(char),
}

/// 한 글자를 읽은 뒤 할 일.
enum Flow {
    /// 다음 글자를 읽는다.
    Read,
    /// 지금까지의 낱말을 낸다.
    Emit,
}

/// 낱말을 만드는 중의 글과, 따옴표를 거쳤는지(따옴표만 있던 빈 낱말도 낱말이다).
#[derive(Default)]
struct Token {
    text: String,
    quoted: bool,
}

impl Token {
    // 공백, 주석, 구두점에서 끊을 때: 모은 것이 있으면 낸다
    fn emit_if_any(&self) -> Flow {
        if self.text.is_empty() && !self.quoted {
            Flow::Read
        } else {
            Flow::Emit
        }
    }
}

impl Lexer {
    /// `text` 를 읽는 읽개.
    pub fn new(text: &str) -> Lexer {
        Lexer {
            chars: text.chars().collect(),
            pos: 0,
            pushback: None,
            state: State::Space,
        }
    }

    fn read(&mut self) -> Option<char> {
        if let Some(c) = self.pushback.take() {
            return Some(c);
        }
        let c = self.chars.get(self.pos).copied();
        self.pos += usize::from(c.is_some());
        c
    }

    // python instream.readline(): 줄바꿈까지 버린다
    fn skip_line(&mut self) {
        while let Some(c) = self.chars.get(self.pos) {
            self.pos += 1;
            if *c == '\n' {
                break;
            }
        }
    }

    /// 다음 낱말. 글 끝이면 `Ok(None)`. 따옴표만 있던 빈 낱말은 `Some("")`.
    pub fn next_token(&mut self) -> Result<Option<String>, LexError> {
        let mut token = Token::default();
        loop {
            if self.state == State::Eof {
                break;
            }
            let next = self.read();
            let flow = match self.state {
                State::Space => self.space(next, &mut token),
                State::Quote(q) => self.quote(q, next, &mut token)?,
                State::Escape(back) => self.escape(back, next, &mut token)?,
                State::Word | State::Punct => self.word(next, &mut token),
                State::Eof => unreachable!("checked above"),
            };
            if let Flow::Emit = flow {
                break;
            }
        }

        // python posix: 따옴표 없는 빈 낱말은 끝(None)
        if token.text.is_empty() && !token.quoted {
            return Ok(None);
        }
        Ok(Some(token.text))
    }

    // 낱말 사이: 공백과 주석을 건너뛰고 낱말을 연다
    fn space(&mut self, next: Option<char>, token: &mut Token) -> Flow {
        match next {
            None => {
                self.state = State::Eof;
                return Flow::Emit;
            }
            Some(c) if WHITESPACE.contains(c) => return token.emit_if_any(),
            Some('#') => self.skip_line(),
            Some('\\') => self.state = State::Escape(Escaped::Word),
            Some(c) if PUNCTUATION.contains(c) => {
                token.text.push(c);
                self.state = State::Punct;
            }
            Some(c) if QUOTES.contains(c) => self.state = State::Quote(c),
            // whitespace_split: 나머지 글자는 모두 낱말을 연다
            Some(c) => {
                token.text.push(c);
                self.state = State::Word;
            }
        }
        Flow::Read
    }

    fn quote(&mut self, q: char, next: Option<char>, token: &mut Token) -> Result<Flow, LexError> {
        token.quoted = true;
        match next {
            None => return Err(LexError::NoClosingQuotation),
            Some(c) if c == q => self.state = State::Word,
            Some('\\') if q == '"' => self.state = State::Escape(Escaped::Quote(q)),
            Some(c) => token.text.push(c),
        }
        Ok(Flow::Read)
    }

    fn escape(
        &mut self,
        back: Escaped,
        next: Option<char>,
        token: &mut Token,
    ) -> Result<Flow, LexError> {
        let Some(c) = next else {
            return Err(LexError::NoEscapedCharacter);
        };

        // 큰따옴표 안에서는 따옴표와 `\` 만 escape 된다
        if let Escaped::Quote(q) = back
            && c != '\\'
            && c != q
        {
            token.text.push('\\');
        }
        token.text.push(c);
        self.state = match back {
            Escaped::Word => State::Word,
            Escaped::Quote(q) => State::Quote(q),
        };
        Ok(Flow::Read)
    }

    // 낱말 또는 구두점 낱말 안
    fn word(&mut self, next: Option<char>, token: &mut Token) -> Flow {
        let punct = self.state == State::Punct;
        match next {
            None => {
                self.state = State::Eof;
                return Flow::Emit;
            }
            Some(c) if WHITESPACE.contains(c) => {
                self.state = State::Space;
                return token.emit_if_any();
            }
            Some('#') => {
                self.skip_line();
                self.state = State::Space;
                return token.emit_if_any();
            }
            Some(c) if punct && PUNCTUATION.contains(c) => token.text.push(c),
            Some(c) if punct => {
                self.pushback = Some(c);
                self.state = State::Space;
                return Flow::Emit;
            }
            Some(c) if QUOTES.contains(c) => self.state = State::Quote(c),
            Some('\\') => self.state = State::Escape(Escaped::Word),
            Some(c) if !PUNCTUATION.contains(c) => token.text.push(c),
            // 낱말 뒤의 구두점은 다음 낱말
            Some(c) => {
                self.pushback = Some(c);
                self.state = State::Space;
                return token.emit_if_any();
            }
        }
        Flow::Read
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tokens(text: &str) -> Vec<String> {
        let mut lex = Lexer::new(text);
        let mut out = Vec::new();
        while let Ok(Some(t)) = lex.next_token() {
            out.push(t);
        }
        out
    }

    #[test]
    fn reads_like_python_shlex() {
        assert_eq!(tokens(r#"-f "a b" c\ d;x"#), ["-f", "a b", "c d", ";", "x"]);
        assert_eq!(tokens(r#""a\"b\x" 'q\'"#), ["a\"b\\x", "q\\"]);
        assert_eq!(tokens("a#b c\nd >/dev/null"), ["a", "d", ">", "/dev/null"]);
        assert_eq!(tokens("x)) y"), ["x", "))", "y"]);
        assert_eq!(tokens("\"\" z"), ["", "z"]);
        assert_eq!(
            Lexer::new("\"abc").next_token(),
            Err(LexError::NoClosingQuotation)
        );
    }
}
