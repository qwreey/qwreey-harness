//! python `shlex.shlex(text, posix=True)` 에 `whitespace_split = True` 를 준 낱말 읽기. 구두점, 공백, 주석은 [`Syntax`] 로 고른다.
//!
//! 상태 기계는 python `shlex.read_token` 을 그대로 옮겼다. `#` 은 그 줄 끝(줄바꿈까지 먹는다)까지 주석이고,
//! 큰따옴표 안의 `\` 는 `"` 와 `\` 앞에서만 escape 다. 구두점 낱말은 이어진 구두점 글자를 한 낱말로 모은다.
//! qwreey-proc-guard 의 `shell/shlex.rs` 는 이 가운데 `punctuation_chars=True` 한 갈래다.
//!
//! why not shlex crate: python `shlex.shlex` 의 구두점 모드와 주석 규칙(줄바꿈까지 먹기)을 따르지 않아 낱말이 갈린다.

/// 읽는 규칙. python 의 `punctuation_chars`, `whitespace`, `commenters`.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Syntax {
    pub punctuation: &'static str,
    pub whitespace: &'static str,
    pub comments: bool,
}

impl Syntax {
    /// python `shlex.split(text, comments=True)`.
    pub const SPLIT_COMMENTS: Syntax = Syntax {
        punctuation: "",
        whitespace: " \t\r\n",
        comments: true,
    };
}

const QUOTES: &str = "'\"";

/// 낱말을 읽지 못한 이유(python 은 ValueError).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum LexError {
    NoClosingQuotation,
    NoEscapedCharacter,
}

/// 낱말을 하나씩 내는 읽개. python 처럼 앞에서부터 필요한 만큼만 읽는다(뒤의 따옴표 오류는 그 낱말까지 가야 난다).
pub struct Lexer {
    syntax: Syntax,
    chars: Vec<char>,
    pos: usize,
    /// 구두점 낱말 뒤에서 되돌려 둔 글자 하나(python `_pushback_chars`).
    pushback: Option<char>,
    state: State,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum State {
    /// 낱말 사이(python `' '`).
    Space,
    /// 낱말 안(`'a'`).
    Word,
    /// 구두점 낱말 안(`'c'`).
    Punct,
    /// 따옴표 안. 값은 여는 따옴표.
    Quote(char),
    /// `\` 다음. 값은 돌아갈 상태.
    Escape(Escaped),
    /// 글 끝(`None`).
    Eof,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Escaped {
    Word,
    Quote(char),
}

/// 한 글자를 읽은 뒤 할 일.
enum Flow {
    Read,
    Emit,
}

/// 만드는 중의 낱말과, 따옴표를 거쳤는지(따옴표만 있던 빈 낱말도 낱말이다).
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
    /// `text` 를 `syntax` 로 읽는 읽개.
    pub fn new(text: &str, syntax: Syntax) -> Lexer {
        Lexer {
            syntax,
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
        while let Some(&c) = self.chars.get(self.pos) {
            self.pos += 1;
            if c == '\n' {
                break;
            }
        }
    }

    fn is_space(&self, c: char) -> bool {
        self.syntax.whitespace.contains(c)
    }

    fn is_punct(&self, c: char) -> bool {
        self.syntax.punctuation.contains(c)
    }

    fn is_comment(&self, c: char) -> bool {
        self.syntax.comments && c == '#'
    }

    /// 다음 낱말. 글 끝이면 `Ok(None)`. 따옴표만 있던 빈 낱말은 `Some("")`.
    pub fn next_token(&mut self) -> Result<Option<String>, LexError> {
        let mut token = Token::default();
        while self.state != State::Eof {
            let next = self.read();
            let flow = match self.state {
                State::Space => self.space(next, &mut token),
                State::Quote(q) => self.quote(q, next, &mut token)?,
                State::Escape(back) => self.escape(back, next, &mut token)?,
                State::Word | State::Punct => self.word(next, &mut token),
                State::Eof => Flow::Emit,
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
        let Some(c) = next else {
            self.state = State::Eof;
            return Flow::Emit;
        };
        if self.is_space(c) {
            return token.emit_if_any();
        }

        // Open a word, a punctuation run, a quote or an escape
        if self.is_comment(c) {
            self.skip_line();
        } else if c == '\\' {
            self.state = State::Escape(Escaped::Word);
        } else if self.is_punct(c) {
            token.text.push(c);
            self.state = State::Punct;
        } else if QUOTES.contains(c) {
            self.state = State::Quote(c);
        } else {
            // whitespace_split: 나머지 글자는 모두 낱말을 연다
            token.text.push(c);
            self.state = State::Word;
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
        let Some(c) = next else {
            self.state = State::Eof;
            return Flow::Emit;
        };
        if self.is_space(c) {
            self.state = State::Space;
            return token.emit_if_any();
        }
        if self.is_comment(c) {
            self.skip_line();
            self.state = State::Space;
            return token.emit_if_any();
        }

        // 구두점 낱말은 구두점만 잇고, 다른 글자는 다음 낱말로 되돌린다(공백이 아닌 것은 위에서 걸렀다)
        if self.state == State::Punct {
            if self.is_punct(c) {
                token.text.push(c);
                return Flow::Read;
            }
            self.pushback = Some(c);
            self.state = State::Space;
            return Flow::Emit;
        }

        if QUOTES.contains(c) {
            self.state = State::Quote(c);
        } else if c == '\\' {
            self.state = State::Escape(Escaped::Word);
        } else if !self.is_punct(c) {
            token.text.push(c);
        } else {
            // 낱말 뒤의 구두점은 다음 낱말
            self.pushback = Some(c);
            self.state = State::Space;
            return token.emit_if_any();
        }
        Flow::Read
    }
}

/// python `list(lexer)`: 모든 낱말. 따옴표 오류는 `Err`.
pub fn split(text: &str, syntax: Syntax) -> Result<Vec<String>, LexError> {
    let mut lexer = Lexer::new(text, syntax);
    let mut out = Vec::new();
    while let Some(token) = lexer.next_token()? {
        out.push(token);
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    const COMMIT: Syntax = Syntax {
        punctuation: ";&|<>\n",
        whitespace: " \t\r",
        comments: true,
    };

    fn words(text: &str, syntax: Syntax) -> Vec<String> {
        split(text, syntax).expect("lexes")
    }

    /// `shlex.split(comments=True)` 와 같은 낱말: 따옴표, escape, 주석, 빈 따옴표 낱말.
    #[test]
    fn splits_like_python_split_with_comments() {
        // Quotes and escapes join into one word
        assert_eq!(
            words(r#"-f "a b" c\ d;x"#, Syntax::SPLIT_COMMENTS),
            ["-f", "a b", "c d;x"],
            "without punctuation chars `;` stays inside the word"
        );
        assert_eq!(
            words(r#""a\"b\x" 'q\'"#, Syntax::SPLIT_COMMENTS),
            ["a\"b\\x", "q\\"]
        );

        // A comment runs to the end of its line
        assert_eq!(words("a#b c\nd", Syntax::SPLIT_COMMENTS), ["a", "d"]);

        // An empty quoted word is still a word
        assert_eq!(words("\"\" z", Syntax::SPLIT_COMMENTS), ["", "z"]);

        // An open quote is an error, as in python
        assert_eq!(
            split("\"abc", Syntax::SPLIT_COMMENTS),
            Err(LexError::NoClosingQuotation)
        );
        assert_eq!(
            split("abc\\", Syntax::SPLIT_COMMENTS),
            Err(LexError::NoEscapedCharacter)
        );
    }

    /// commit_scope 의 구두점 모드: 구두점이 이어지면 한 낱말, 줄바꿈도 구두점, 주석은 줄바꿈까지 먹는다.
    #[test]
    fn punctuation_mode_like_commit_scope() {
        // Runs of punctuation form one word
        assert_eq!(
            words("git add x&&git commit 2>&1", COMMIT),
            ["git", "add", "x", "&&", "git", "commit", "2", ">&", "1"]
        );

        // A newline is punctuation here, and joins with a run before it
        assert_eq!(words("a &&\nb", COMMIT), ["a", "&&\n", "b"]);

        // The comment eats the newline, so no separator is left
        assert_eq!(words("a # c\nb", COMMIT), ["a", "b"]);
    }

    /// 읽개는 앞에서부터만 읽는다: 멈춘 뒤의 따옴표 오류는 나지 않는다(python 의 for 문과 break).
    #[test]
    fn lazy_reading_stops_before_later_errors() {
        let mut lexer = Lexer::new("a << 'b", COMMIT);
        assert_eq!(lexer.next_token(), Ok(Some("a".to_owned())));
        assert_eq!(lexer.next_token(), Ok(Some("<<".to_owned())));
        assert_eq!(lexer.next_token(), Err(LexError::NoClosingQuotation));
    }
}
