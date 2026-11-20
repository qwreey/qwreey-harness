//! python 낱말: 이름, 수, 문자열(f-string 의 칸 포함), 연산자, 논리 줄 끝.

use harness_hook::py::surrogate::placeholder;

use super::parse::Parser;
use super::{R, Unsure, names};

// 긴 것부터: 맨 앞에서 가장 길게 맞는 연산자
const OPS: &[&str] = &[
    "**=", "//=", ">>=", "<<=", "...", "->", ":=", "**", "//", ">>", "<<", "<=", ">=", "==", "!=",
    "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "@=", "+", "-", "*", "/", "%", "@", "&", "|",
    "^", "~", "<", ">", "(", ")", "[", "]", "{", "}", ",", ":", ".", ";", "=", "!",
];

/// 낱말 하나. 줄 끝(`Newline`)은 논리 줄의 끝이다.
#[derive(Clone, Debug, PartialEq)]
pub enum Tok {
    Name(String),
    Num,
    Str(StrTok),
    Op(&'static str),
    Newline,
}

/// 문자열 리터럴 하나: 보통 글(값), bytes, f-string(조각들).
#[derive(Clone, Debug, PartialEq)]
pub enum StrTok {
    Plain(String),
    Bytes,
    F(Vec<FItem>),
}

// f-string 의 조각: 글(옆 글과 합친다), 칸 경계, 칸 안에서 따로 나온 상수들
#[derive(Clone, Debug, PartialEq)]
pub enum FItem {
    Lit(String),
    Break,
    Consts(Vec<String>),
}

// 칸 안 식이 끝난 자리의 글자
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum FieldEnd {
    Close,
    Bang,
    Colon,
    Debug,
}

/// 글자 배열을 앞에서부터 읽는 렉서.
pub struct Lexer<'a> {
    src: &'a [char],
    i: usize,
}

impl<'a> Lexer<'a> {
    /// 맨 앞에서 시작한다.
    pub fn new(src: &'a [char]) -> Lexer<'a> {
        Lexer { src, i: 0 }
    }

    fn peek(&self, k: usize) -> Option<char> {
        self.src.get(self.i + k).copied()
    }

    /// 모듈 전체: 논리 줄 끝마다 Newline. 괄호 안 줄바꿈과 `\` 줄 잇기는 줄을 끊지 않는다
    pub fn module(&mut self) -> R<Vec<Tok>> {
        let mut out = Vec::new();
        let mut depth = 0usize;
        let mut line_start = true;

        while let Some(c) = self.peek(0) {
            // An indented statement line is python's IndentationError
            if line_start && depth == 0 {
                line_start = false;
                if c == ' ' || c == '\t' || c == '\u{c}' {
                    let rest = self.src[self.i..].iter().take_while(|&&c| c != '\n');
                    let first = rest
                        .clone()
                        .find(|&&c| c != ' ' && c != '\t' && c != '\u{c}');
                    if !matches!(first, None | Some('#')) {
                        return Err(Unsure);
                    }
                }
            }

            match c {
                '\n' => {
                    self.i += 1;
                    if depth == 0 {
                        if !matches!(out.last(), None | Some(Tok::Newline)) {
                            out.push(Tok::Newline);
                        }
                        line_start = true;
                    }
                }
                '\\' if self.peek(1) == Some('\n') => self.i += 2,
                _ => {
                    let Some(tok) = self.token()? else { continue };
                    match tok {
                        Tok::Op("(" | "[" | "{") => depth += 1,
                        Tok::Op(")" | "]" | "}") => depth = depth.checked_sub(1).ok_or(Unsure)?,
                        _ => {}
                    }
                    out.push(tok);
                }
            }
        }
        if depth != 0 {
            return Err(Unsure);
        }
        if !matches!(out.last(), None | Some(Tok::Newline)) {
            out.push(Tok::Newline);
        }
        Ok(out)
    }

    // 낱말 하나. 빈칸과 주석이면 None
    fn token(&mut self) -> R<Option<Tok>> {
        let c = self.peek(0).ok_or(Unsure)?;
        match c {
            ' ' | '\t' | '\u{c}' => {
                self.i += 1;
                Ok(None)
            }
            '#' => {
                while self.peek(0).is_some_and(|c| c != '\n') {
                    self.i += 1;
                }
                Ok(None)
            }
            '"' | '\'' => Ok(Some(Tok::Str(self.string("")?))),
            '0'..='9' => self.number().map(Some),
            '.' if self.peek(1).is_some_and(|d| d.is_ascii_digit()) => self.number().map(Some),
            c if c.is_ascii_alphabetic() || c == '_' => self.name_or_string().map(Some),
            c if !c.is_ascii() => Err(Unsure),
            _ => {
                let op = OPS
                    .iter()
                    .find(|op| op.chars().enumerate().all(|(k, o)| self.peek(k) == Some(o)))
                    .ok_or(Unsure)?;
                self.i += op.chars().count();
                Ok(Some(Tok::Op(op)))
            }
        }
    }

    // 이름, 또는 머리 글자(r, u, b, f 와 그 짝)가 붙은 문자열
    fn name_or_string(&mut self) -> R<Tok> {
        let at = self.i;
        while self
            .peek(0)
            .is_some_and(|c| c.is_ascii_alphanumeric() || c == '_')
        {
            self.i += 1;
        }
        let word: String = self.src[at..self.i].iter().collect();
        if self.peek(0).is_some_and(|c| !c.is_ascii()) {
            return Err(Unsure);
        }
        if matches!(self.peek(0), Some('"' | '\'')) {
            let prefix = word.to_ascii_lowercase();
            if !matches!(
                prefix.as_str(),
                "r" | "u" | "b" | "br" | "rb" | "f" | "fr" | "rf"
            ) {
                return Err(Unsure);
            }
            return Ok(Tok::Str(self.string(&prefix)?));
        }
        Ok(Tok::Name(word))
    }

    // 수 하나. python 이 받는 꼴만(아니면 Unsure)
    fn number(&mut self) -> R<Tok> {
        let at = self.i;
        let digits = |lx: &mut Self, ok: fn(char) -> bool| -> R<usize> {
            let mut n = 0;
            while let Some(c) = lx.peek(0) {
                if ok(c) {
                    n += 1;
                    lx.i += 1;
                } else if c == '_' && lx.peek(1).is_some_and(ok) && n > 0 {
                    lx.i += 1;
                } else {
                    break;
                }
            }
            Ok(n)
        };

        // Prefixed integers
        if self.peek(0) == Some('0')
            && let Some(kind) = self.peek(1).map(|c| c.to_ascii_lowercase())
            && matches!(kind, 'x' | 'o' | 'b')
        {
            self.i += 2;
            if self.peek(0) == Some('_') {
                self.i += 1;
            }
            let ok: fn(char) -> bool = match kind {
                'x' => |c| c.is_ascii_hexdigit(),
                'o' => |c| ('0'..='7').contains(&c),
                _ => |c| c == '0' || c == '1',
            };
            if digits(self, ok)? == 0 {
                return Err(Unsure);
            }
            return self.number_end();
        }

        // Decimal, float, exponent, imaginary
        let int_digits = digits(self, |c| c.is_ascii_digit())?;
        let int_text: String = self.src[at..self.i].iter().filter(|&&c| c != '_').collect();
        let mut is_int = true;
        if self.peek(0) == Some('.') {
            self.i += 1;
            is_int = false;
            let frac = digits(self, |c| c.is_ascii_digit())?;
            if int_digits == 0 && frac == 0 {
                return Err(Unsure);
            }
        }
        if matches!(self.peek(0), Some('e' | 'E')) {
            self.i += 1;
            if matches!(self.peek(0), Some('+' | '-')) {
                self.i += 1;
            }
            if digits(self, |c| c.is_ascii_digit())? == 0 {
                return Err(Unsure);
            }
            is_int = false;
        }
        if matches!(self.peek(0), Some('j' | 'J')) {
            self.i += 1;
            is_int = false;
        }

        // python rejects leading zeros in a decimal integer
        if is_int
            && int_text.len() > 1
            && int_text.starts_with('0')
            && int_text.chars().any(|c| c != '0')
        {
            return Err(Unsure);
        }
        self.number_end()
    }

    // 수 바로 뒤에 이름 글자가 붙으면 python 이 다르게 읽거나 경고한다
    fn number_end(&mut self) -> R<Tok> {
        match self.peek(0) {
            Some(c) if c.is_ascii_alphanumeric() || c == '_' || c == '.' || !c.is_ascii() => {
                Err(Unsure)
            }
            _ => Ok(Tok::Num),
        }
    }

    // `self.i` 의 따옴표부터 닫는 따옴표 다음까지
    fn string(&mut self, prefix: &str) -> R<StrTok> {
        let raw = prefix.contains('r');
        let bytes = prefix.contains('b');
        let fstr = prefix.contains('f');
        let q = self.peek(0).ok_or(Unsure)?;
        let triple = self.peek(1) == Some(q) && self.peek(2) == Some(q);
        self.i += if triple { 3 } else { 1 };

        if fstr {
            let items = self.fstring_body(q, triple, raw, false)?;
            return Ok(StrTok::F(items));
        }
        let mut value = String::new();
        loop {
            if self.at_close(q, triple) {
                self.i += if triple { 3 } else { 1 };
                break;
            }
            let c = self.peek(0).ok_or(Unsure)?;
            if c == '\n' && !triple {
                return Err(Unsure);
            }
            if bytes && !c.is_ascii() {
                return Err(Unsure);
            }
            if c != '\\' {
                value.push(c);
                self.i += 1;
                continue;
            }
            if raw {
                let next = self.peek(1).ok_or(Unsure)?;
                value.push('\\');
                value.push(next);
                self.i += 2;
                continue;
            }
            value.push_str(&self.escape(bytes)?);
        }
        Ok(if bytes {
            StrTok::Bytes
        } else {
            StrTok::Plain(value)
        })
    }

    fn at_close(&self, q: char, triple: bool) -> bool {
        self.peek(0) == Some(q) && (!triple || (self.peek(1) == Some(q) && self.peek(2) == Some(q)))
    }

    // `\` 하나에서 시작하는 escape 의 값
    fn escape(&mut self, bytes: bool) -> R<String> {
        let e = self.peek(1).ok_or(Unsure)?;
        let simple = match e {
            '\n' => Some(""),
            '\\' => Some("\\"),
            '\'' => Some("'"),
            '"' => Some("\""),
            'a' => Some("\u{7}"),
            'b' => Some("\u{8}"),
            'f' => Some("\u{c}"),
            'n' => Some("\n"),
            'r' => Some("\r"),
            't' => Some("\t"),
            'v' => Some("\u{b}"),
            _ => None,
        };
        if let Some(s) = simple {
            self.i += 2;
            return Ok(s.to_owned());
        }

        // Octal, hex, unicode and named escapes
        let take = |lx: &Self, from: usize, max: usize, radix: u32| -> String {
            lx.src[(lx.i + from).min(lx.src.len())..]
                .iter()
                .take(max)
                .take_while(|c| c.is_digit(radix))
                .collect()
        };
        let code = match e {
            '0'..='7' => {
                let d = take(self, 1, 3, 8);
                self.i += 1 + d.len();
                u32::from_str_radix(&d, 8).map_err(|_| Unsure)?
            }
            'x' => self.fixed_hex(&take(self, 2, 2, 16), 2)?,
            'u' | 'U' if !bytes => {
                let width = if e == 'u' { 4 } else { 8 };
                self.fixed_hex(&take(self, 2, width, 16), width)?
            }
            'N' if !bytes => {
                if self.peek(2) != Some('{') {
                    return Err(Unsure);
                }
                let close = self.src[self.i + 3..]
                    .iter()
                    .position(|&c| c == '}')
                    .ok_or(Unsure)?;
                let name: String = self.src[self.i + 3..self.i + 3 + close]
                    .iter()
                    .collect::<String>()
                    .to_ascii_uppercase();
                self.i += 4 + close;
                names::NAMES
                    .iter()
                    .find(|(n, _)| *n == name)
                    .map(|&(_, c)| c)
                    .ok_or(Unsure)?
            }
            // python 이 경고만 내고 그대로 두는 escape
            _ => {
                self.i += 2;
                return Ok(format!("\\{e}"));
            }
        };
        let c = char::from_u32(code)
            .or_else(|| placeholder(code))
            .ok_or(Unsure)?;
        Ok(c.to_string())
    }

    fn fixed_hex(&mut self, digits: &str, width: usize) -> R<u32> {
        if digits.len() != width {
            return Err(Unsure);
        }
        self.i += 2 + width;
        u32::from_str_radix(digits, 16).map_err(|_| Unsure)
    }

    // f-string 몸(여는 따옴표 다음부터). `spec` 이면 형식 지정 안이라 `}` 에서 끝난다
    fn fstring_body(&mut self, q: char, triple: bool, raw: bool, spec: bool) -> R<Vec<FItem>> {
        let mut items = Vec::new();
        let mut lit = String::new();
        loop {
            // The end of the string or of the format spec
            if spec && self.peek(0) == Some('}') {
                break;
            }
            if self.at_close(q, triple) {
                if spec {
                    return Err(Unsure);
                }
                self.i += if triple { 3 } else { 1 };
                break;
            }
            let c = self.peek(0).ok_or(Unsure)?;
            if c == '\n' && !triple {
                return Err(Unsure);
            }

            match c {
                // Doubled braces and fields
                '{' if !spec && self.peek(1) == Some('{') => {
                    lit.push('{');
                    self.i += 2;
                }
                '}' if self.peek(1) == Some('}') && !spec => {
                    lit.push('}');
                    self.i += 2;
                }
                '}' => return Err(Unsure),
                '{' => {
                    if !lit.is_empty() {
                        items.push(FItem::Lit(std::mem::take(&mut lit)));
                    }
                    self.i += 1;
                    let field = self.field(q, triple, raw, spec)?;
                    items.extend(field);
                }

                // Text and escapes
                '\\' if raw => {
                    let next = self.peek(1).ok_or(Unsure)?;
                    lit.push('\\');
                    if next != '{' && next != '}' {
                        lit.push(next);
                        self.i += 2;
                    } else {
                        self.i += 1;
                    }
                }
                '\\' => lit.push_str(&self.escape(false)?),
                _ => {
                    lit.push(c);
                    self.i += 1;
                }
            }
        }
        if !lit.is_empty() {
            items.push(FItem::Lit(lit));
        }
        Ok(items)
    }

    // `{` 다음부터 칸 하나: 식, `=`, `!r`, `:형식`, `}`. 조각들을 돌려준다
    fn field(&mut self, q: char, triple: bool, raw: bool, in_spec: bool) -> R<Vec<FItem>> {
        let start = self.i;

        // The expression tokens up to the first top-level end mark
        let mut toks = Vec::new();
        let mut depth = 0usize;
        let end = loop {
            let c = self.peek(0).ok_or(Unsure)?;
            if c == '\n' || c == '\\' || c == '#' {
                return Err(Unsure);
            }
            if c == q && !triple {
                // 3.12 부터는 같은 따옴표의 안쪽 문자열이 되지만 옛 판은 닫는 따옴표로 읽는다
                return Err(Unsure);
            }
            // A top-level `:` starts the format spec even before `=` (`{x:=^10}`)
            if c == ':' && depth == 0 {
                self.i += 1;
                break FieldEnd::Colon;
            }
            let Some(tok) = self.token()? else { continue };
            match tok {
                Tok::Op("(" | "[" | "{") => depth += 1,
                Tok::Op(")" | "]") if depth > 0 => depth -= 1,
                Tok::Op("}") if depth > 0 => depth -= 1,
                Tok::Op("}") => break FieldEnd::Close,
                Tok::Op("!") if depth == 0 => break FieldEnd::Bang,
                Tok::Op(":") if depth == 0 => break FieldEnd::Colon,
                Tok::Op("=") if depth == 0 => break FieldEnd::Debug,
                Tok::Op(")" | "]") => return Err(Unsure),
                _ => {}
            }
            toks.push(tok);
        };
        if toks.is_empty() {
            return Err(Unsure);
        }
        toks.push(Tok::Newline);
        let mut p = Parser::new(&toks);
        p.expression_only()?;
        let mut consts = p.into_constants();

        // `=` keeps the source text, with the spaces after it, as a literal before the field
        let mut items = Vec::new();
        let mut end = end;
        if end == FieldEnd::Debug {
            while matches!(self.peek(0), Some(' ' | '\t')) {
                self.i += 1;
            }
            end = match self.peek(0) {
                Some('}') => FieldEnd::Close,
                Some('!') => FieldEnd::Bang,
                Some(':') => FieldEnd::Colon,
                _ => return Err(Unsure),
            };
            self.i += 1;
            let text: String = self.src[start..self.i - 1].iter().collect();
            items.push(FItem::Lit(text));
        }

        // Conversion
        if end == FieldEnd::Bang {
            if !matches!(self.peek(0), Some('r' | 's' | 'a')) {
                return Err(Unsure);
            }
            self.i += 1;
            end = match self.peek(0) {
                Some('}') => FieldEnd::Close,
                Some(':') => FieldEnd::Colon,
                _ => return Err(Unsure),
            };
            self.i += 1;
        }

        // Format spec: its own pieces, never merged with the outer text
        if end == FieldEnd::Colon {
            if in_spec {
                return Err(Unsure);
            }
            for item in self.fstring_body(q, triple, raw, true)? {
                match item {
                    FItem::Lit(s) => consts.push(s),
                    FItem::Consts(c) => consts.extend(c),
                    FItem::Break => {}
                }
            }
            if self.peek(0) != Some('}') {
                return Err(Unsure);
            }
            self.i += 1;
        }
        items.push(FItem::Break);
        items.push(FItem::Consts(consts));
        Ok(items)
    }
}
