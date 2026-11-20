//! 패턴 글을 [`Node`] 나무로(python `re._parser.parse`). 오류는 python 이 내는 자리와 순서를 따른다.
//!
//! python 이 받지만 여기서 옮기지 않은 문법은 끝까지 읽은 뒤 [`Error::Unsupported`] 로 알린다(읽는 도중의 python 오류가 먼저다).

use std::collections::HashMap;

use super::ast::{Anchor, Category, Class, ClassItem, Look, Node, Repeat};
use super::{Error, Flags};

/// python `_sre.MAXREPEAT`. 되풀이 수가 이 이상이면 python 은 re.error 가 아닌 OverflowError 를 낸다.
const MAX_REPEAT: u64 = 4_294_967_295;
/// 이보다 큰 되풀이 수는 프로그램이 커져 옮기지 않았다.
const REPEAT_LIMIT: u32 = 1000;
const SPECIAL: &str = ".\\[{()*+?^$|";
const FLAG_CHARS: &str = "aiLmsux";

/// 패턴 글의 토큰. python 토크나이저처럼 `\` 와 다음 글자는 한 토큰이다.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Tok {
    Ch(char),
    Esc(char),
}

/// `(?` 다음을 읽은 결과.
enum Ext {
    /// 괄호를 다 읽었다. 나무에 더할 것이 없으면 `None`.
    Done(Option<Node>),
    /// 괄호 안을 이어 읽는다. `atomic` 은 `(?>...)`.
    Group {
        capture: bool,
        name: Option<String>,
        atomic: bool,
    },
}

/// 읽은 결과: 나무, 잡는 괄호 수(0 번 포함), 인라인 플래그를 더한 플래그.
pub(super) struct Parsed {
    pub node: Node,
    pub groups: usize,
    pub flags: Flags,
}

/// 패턴을 읽는다(python `re._parser.parse`).
pub(super) fn parse(pattern: &str, flags: Flags) -> Result<Parsed, Error> {
    let mut p = Parser {
        src: pattern.chars().collect(),
        pos: 0,
        groups: 1,
        open: Vec::new(),
        names: HashMap::new(),
        flags,
        lookbehind: 0,
        unsupported: None,
    };

    // 끝까지 읽고, 남은 `)` 는 짝이 없다
    let node = p.parse_sub(0)?;
    if p.peek()?.is_some() {
        return Err(Error::Syntax("unbalanced parenthesis".into()));
    }
    if let Some(what) = p.unsupported {
        return Err(Error::Unsupported(what));
    }
    Ok(Parsed {
        node,
        groups: p.groups,
        flags: p.flags,
    })
}

struct Parser {
    src: Vec<char>,
    pos: usize,
    /// 다음 괄호 번호(python `state.groups`).
    groups: usize,
    /// 아직 닫히지 않은 괄호 번호.
    open: Vec<usize>,
    names: HashMap<String, usize>,
    flags: Flags,
    /// 지금 읽는 lookbehind 의 깊이.
    lookbehind: usize,
    unsupported: Option<&'static str>,
}

fn syntax(msg: impl Into<String>) -> Error {
    Error::Syntax(msg.into())
}

impl Parser {
    // 토큰 읽기

    fn peek(&self) -> Result<Option<Tok>, Error> {
        match self.src.get(self.pos) {
            None => Ok(None),
            Some('\\') => match self.src.get(self.pos + 1) {
                Some(&c) => Ok(Some(Tok::Esc(c))),
                None => Err(syntax("bad escape (end of pattern)")),
            },
            Some(&c) => Ok(Some(Tok::Ch(c))),
        }
    }

    fn next(&mut self) -> Result<Option<Tok>, Error> {
        let tok = self.peek()?;
        self.pos += match tok {
            None => 0,
            Some(Tok::Ch(_)) => 1,
            Some(Tok::Esc(_)) => 2,
        };
        Ok(tok)
    }

    fn eat(&mut self, c: char) -> Result<bool, Error> {
        if self.peek()? == Some(Tok::Ch(c)) {
            self.pos += 1;
            return Ok(true);
        }
        Ok(false)
    }

    // python getwhile(n, chars): 글자 토큰만 n 개까지
    fn take_while(&mut self, n: usize, ok: impl Fn(char) -> bool) -> Result<String, Error> {
        let mut out = String::new();
        while out.chars().count() < n {
            match self.peek()? {
                Some(Tok::Ch(c)) if ok(c) => {
                    out.push(c);
                    self.pos += 1;
                }
                _ => break,
            }
        }
        Ok(out)
    }

    // python getuntil 자리: end 까지 읽는다. escape 토큰은 두 글자로 붙는다
    fn take_until(&mut self, end: char, name: &str) -> Result<String, Error> {
        let mut out = String::new();
        loop {
            match self.next()? {
                None if out.is_empty() => return Err(syntax(format!("missing {name}"))),
                None => return Err(syntax(format!("missing {end}, unterminated name"))),
                Some(Tok::Ch(c)) if c == end => {
                    if out.is_empty() {
                        return Err(syntax(format!("missing {name}")));
                    }
                    return Ok(out);
                }
                Some(Tok::Ch(c)) => out.push(c),
                Some(Tok::Esc(c)) => {
                    out.push('\\');
                    out.push(c);
                }
            }
        }
    }

    fn unsupported(&mut self, what: &'static str) {
        self.unsupported.get_or_insert(what);
    }

    // 갈래와 이어 붙이기

    fn parse_sub(&mut self, nested: usize) -> Result<Node, Error> {
        let mut items = Vec::new();
        loop {
            let first = nested == 0 && items.is_empty();
            items.push(self.parse_seq(first)?);
            if !self.eat('|')? {
                break;
            }
        }
        Ok(if items.len() == 1 {
            items.pop().expect("one item")
        } else {
            Node::Alt(items)
        })
    }

    fn parse_seq(&mut self, first: bool) -> Result<Node, Error> {
        let mut seq: Vec<Node> = Vec::new();
        while let Some(tok) = self.peek()? {
            if matches!(tok, Tok::Ch('|' | ')')) {
                break;
            }
            self.next()?;

            match tok {
                Tok::Esc(c) => seq.push(self.escape(c)?),
                Tok::Ch(c) if !SPECIAL.contains(c) => seq.push(Node::Lit(u32::from(c))),
                Tok::Ch('[') => seq.push(self.class()?),
                Tok::Ch(c @ ('*' | '+' | '?' | '{')) => self.repeat(c, &mut seq)?,
                Tok::Ch('.') => seq.push(Node::Any),
                Tok::Ch('(') => {
                    if let Some(node) = self.group(first && seq.is_empty())? {
                        seq.push(node);
                    }
                }
                Tok::Ch('^') => seq.push(Node::At(Anchor::Begin)),
                Tok::Ch('$') => seq.push(Node::At(Anchor::End)),
                Tok::Ch(c) => unreachable!("special character {c:?} handled above"),
            }
        }
        Ok(if seq.len() == 1 {
            seq.pop().expect("one item")
        } else {
            Node::Concat(seq)
        })
    }

    // 되풀이

    fn repeat(&mut self, c: char, seq: &mut Vec<Node>) -> Result<(), Error> {
        let (min, max) = match c {
            '?' => (0, Some(1)),
            '*' => (0, None),
            '+' => (1, None),
            _ => match self.braces()? {
                Some(bounds) => bounds,
                None => {
                    seq.push(Node::Lit(u32::from('{')));
                    return Ok(());
                }
            },
        };

        // 앞 조각
        match seq.last() {
            None | Some(Node::At(_)) => return Err(syntax("nothing to repeat")),
            Some(Node::Repeat(_)) => return Err(syntax("multiple repeat")),
            Some(_) => {}
        }
        let node = seq.pop().expect("checked above");

        // 게으른, 소유 되풀이
        let greedy = !self.eat('?')?;
        let possessive = greedy && self.eat('+')?;
        if min > REPEAT_LIMIT || max.is_some_and(|m| m > REPEAT_LIMIT) {
            self.unsupported("repeat count over 1000");
        }
        seq.push(Node::Repeat(Box::new(Repeat {
            node,
            min,
            max,
            greedy,
            possessive,
        })));
        Ok(())
    }

    // `{` 다음: `Some((최소, 최대))`, 되풀이 꼴이 아니면 `None`(그 `{` 는 글자, 읽던 자리로 돌아간다)
    fn braces(&mut self) -> Result<Option<(u32, Option<u32>)>, Error> {
        if self.peek()? == Some(Tok::Ch('}')) {
            return Ok(None);
        }
        let here = self.pos;
        let lo = self.take_while(usize::MAX, |c| c.is_ascii_digit())?;
        let hi = if self.eat(',')? {
            self.take_while(usize::MAX, |c| c.is_ascii_digit())?
        } else {
            lo.clone()
        };
        if !self.eat('}')? {
            self.pos = here;
            return Ok(None);
        }

        let min = if lo.is_empty() { 0 } else { repeat_count(&lo)? };
        let max = if hi.is_empty() {
            None
        } else {
            Some(repeat_count(&hi)?)
        };
        if max.is_some_and(|m| m < min) {
            return Err(syntax("min repeat greater than max repeat"));
        }
        Ok(Some((min, max)))
    }

    // 괄호

    // `(` 다음. 나무에 더할 것이 없으면(주석, 전역 플래그) `None`
    fn group(&mut self, at_start: bool) -> Result<Option<Node>, Error> {
        let (capture, name, atomic) = if self.eat('?')? {
            match self.extension(at_start)? {
                Ext::Done(node) => return Ok(node),
                Ext::Group {
                    capture,
                    name,
                    atomic,
                } => (capture, name, atomic),
            }
        } else {
            (true, None, false)
        };

        // 괄호 안
        let gid = if capture {
            Some(self.open_group(name)?)
        } else {
            None
        };
        let inner = self.parse_sub(1)?;
        if !self.eat(')')? {
            return Err(syntax("missing ), unterminated subpattern"));
        }

        if let Some(gid) = gid {
            self.open.retain(|&g| g != gid);
        }
        if atomic {
            return Ok(Some(Node::Atomic(Box::new(inner))));
        }
        Ok(Some(Node::Group(gid, Box::new(inner))))
    }

    // `(?` 다음 글자로 갈린다
    fn extension(&mut self, at_start: bool) -> Result<Ext, Error> {
        let c = match self.next()? {
            None => return Err(syntax("unexpected end of pattern")),
            Some(Tok::Esc(_)) => return Err(syntax("unknown extension")),
            Some(Tok::Ch(c)) => c,
        };
        let plain = Ext::Group {
            capture: false,
            name: None,
            atomic: false,
        };
        match c {
            'P' => self.python_extension(),
            ':' => Ok(plain),
            '#' => {
                // 주석은 `)` 까지 버린다
                loop {
                    match self.next()? {
                        None => return Err(syntax("missing ), unterminated comment")),
                        Some(Tok::Ch(')')) => return Ok(Ext::Done(None)),
                        Some(_) => {}
                    }
                }
            }
            '=' | '!' | '<' => Ok(Ext::Done(Some(self.look(c)?))),
            '(' => {
                self.take_until(')', "group name")?;
                self.unsupported("conditional group");
                Ok(plain)
            }
            '>' => Ok(Ext::Group {
                capture: false,
                name: None,
                atomic: true,
            }),
            c if FLAG_CHARS.contains(c) || c == '-' => {
                if self.flags_group(c, at_start)? {
                    return Ok(Ext::Done(None));
                }
                Ok(plain)
            }
            _ => Err(syntax(format!("unknown extension ?{c}"))),
        }
    }

    // `(?P<name>...)` 와 `(?P=name)`
    fn python_extension(&mut self) -> Result<Ext, Error> {
        if self.eat('<')? {
            let name = self.group_name('>')?;
            return Ok(Ext::Group {
                capture: true,
                name: Some(name),
                atomic: false,
            });
        }
        if !self.eat('=')? {
            return Err(syntax("unknown extension ?P"));
        }
        let name = self.group_name(')')?;
        let Some(&gid) = self.names.get(&name) else {
            return Err(syntax(format!("unknown group name {name:?}")));
        };
        Ok(Ext::Done(Some(self.backref(gid)?)))
    }

    fn look(&mut self, c: char) -> Result<Node, Error> {
        let (behind, kind) = if c == '<' {
            match self.next()? {
                Some(Tok::Ch(k @ ('=' | '!'))) => (true, k),
                None => return Err(syntax("unexpected end of pattern")),
                Some(_) => return Err(syntax("unknown extension ?<")),
            }
        } else {
            (false, c)
        };

        self.lookbehind += usize::from(behind);
        let node = self.parse_sub(1)?;
        self.lookbehind -= usize::from(behind);
        if !self.eat(')')? {
            return Err(syntax("missing ), unterminated subpattern"));
        }

        // python: 빈 부정 검사는 늘 실패
        let negate = kind == '!';
        if negate && node == Node::Concat(Vec::new()) {
            return Ok(Node::Fail);
        }
        Ok(Node::Look(Box::new(Look {
            behind,
            negate,
            node,
        })))
    }

    // python _parse_flags 자리. 전역 플래그(`(?i)`)면 true
    fn flags_group(&mut self, first: char, at_start: bool) -> Result<bool, Error> {
        // 켜는 플래그
        let mut c = first;
        while c != '-' {
            match c {
                'L' => {
                    return Err(syntax(
                        "bad inline flags: cannot use 'L' flag with a str pattern",
                    ));
                }
                'i' => self.flags.ignore_case = true,
                'm' => self.flags.multiline = true,
                's' => self.flags.dotall = true,
                'u' => {}
                _ => self.unsupported("inline flag a or x"),
            }
            match self.next()? {
                None => return Err(syntax("missing -, : or )")),
                Some(Tok::Ch(next)) if ")-:".contains(next) => {
                    c = next;
                    if next != '-' {
                        break;
                    }
                }
                Some(Tok::Ch(next)) if FLAG_CHARS.contains(next) => c = next,
                Some(_) => return Err(syntax("unknown flag")),
            }
        }

        // 전역 플래그는 패턴 맨 앞에서만
        if c == ')' {
            if !at_start {
                return Err(syntax("global flags not at the start of the expression"));
            }
            return Ok(true);
        }

        // 범위 플래그(`(?i:...)`, `(?-i:...)`)는 옮기지 않았다. `:` 까지 읽고 묶음 괄호로 읽는다
        self.unsupported("scoped inline flags");
        if c == '-' {
            loop {
                match self.next()? {
                    Some(Tok::Ch(':')) => break,
                    Some(Tok::Ch(f)) if FLAG_CHARS.contains(f) => {}
                    None => return Err(syntax("missing flag")),
                    Some(_) => return Err(syntax("missing :")),
                }
            }
        }
        Ok(false)
    }

    fn group_name(&mut self, end: char) -> Result<String, Error> {
        let name = self.take_until(end, "group name")?;
        let mut chars = name.chars();
        let head_ok = chars.next().is_some_and(|c| c == '_' || c.is_alphabetic());
        if !head_ok || !chars.all(|c| c == '_' || c.is_alphanumeric()) {
            return Err(syntax(format!("bad character in group name {name:?}")));
        }
        Ok(name)
    }

    fn open_group(&mut self, name: Option<String>) -> Result<usize, Error> {
        let gid = self.groups;
        if let Some(name) = name {
            if self.names.contains_key(&name) {
                return Err(syntax(format!("redefinition of group name {name:?}")));
            }
            self.names.insert(name, gid);
        }
        self.groups += 1;
        self.open.push(gid);
        Ok(gid)
    }

    fn backref(&mut self, gid: usize) -> Result<Node, Error> {
        if self.open.contains(&gid) {
            return Err(syntax("cannot refer to an open group"));
        }
        if self.lookbehind > 0 {
            self.unsupported("group reference in a lookbehind");
        }
        Ok(Node::Backref(gid))
    }

    // escape

    // python _escape: 괄호 밖의 `\c`
    fn escape(&mut self, c: char) -> Result<Node, Error> {
        let cat = |cat| {
            Node::Class(Class {
                negate: false,
                items: vec![ClassItem::Cat(cat)],
            })
        };
        Ok(match c {
            'A' => Node::At(Anchor::BeginString),
            'Z' => Node::At(Anchor::EndString),
            'b' => Node::At(Anchor::Boundary),
            'B' => Node::At(Anchor::NotBoundary),
            'd' => cat(Category::Digit),
            'D' => cat(Category::NotDigit),
            's' => cat(Category::Space),
            'S' => cat(Category::NotSpace),
            'w' => cat(Category::Word),
            'W' => cat(Category::NotWord),
            '0' => {
                let digits = self.take_while(2, is_octal)?;
                Node::Lit(u32::from_str_radix(&format!("0{digits}"), 8).expect("octal digits"))
            }
            '1'..='9' => return self.digit_escape(c),
            _ => Node::Lit(self.common_escape(c)?),
        })
    }

    // `\1`..`\99` 는 괄호 참조, 8진수 세 자리면 글자
    fn digit_escape(&mut self, c: char) -> Result<Node, Error> {
        let mut digits = String::from(c);
        if let Some(Tok::Ch(d)) = self.peek()?
            && d.is_ascii_digit()
        {
            self.pos += 1;
            digits.push(d);
            if let Some(Tok::Ch(e)) = self.peek()?
                && is_octal(c)
                && is_octal(d)
                && is_octal(e)
            {
                self.pos += 1;
                digits.push(e);
                let value = u32::from_str_radix(&digits, 8).expect("octal digits");
                if value > 0o377 {
                    return Err(syntax("octal escape value outside of range 0-0o377"));
                }
                return Ok(Node::Lit(value));
            }
        }
        let gid: usize = digits.parse().expect("decimal digits");
        if gid < self.groups {
            return self.backref(gid);
        }
        Err(syntax(format!("invalid group reference {gid}")))
    }

    // 괄호 안팎이 같은 escape: 제어 글자, \x \u \U \N, 기호 그대로. 그 밖의 ASCII 글자는 오류
    fn common_escape(&mut self, c: char) -> Result<u32, Error> {
        let hex = |p: &mut Parser, n: usize| -> Result<u32, Error> {
            let digits = p.take_while(n, |d| d.is_ascii_hexdigit())?;
            if digits.chars().count() != n {
                return Err(syntax(format!("incomplete escape \\{c}{digits}")));
            }
            Ok(u32::from_str_radix(&digits, 16).expect("hex digits"))
        };
        Ok(match c {
            'a' => 7,
            'f' => 12,
            'n' => 10,
            'r' => 13,
            't' => 9,
            'v' => 11,
            '\\' => 92,
            'x' => hex(self, 2)?,
            'u' => hex(self, 4)?,
            'U' => {
                let value = hex(self, 8)?;
                if value > 0x10ffff {
                    return Err(syntax("bad escape \\U"));
                }
                value
            }
            'N' => {
                if !self.eat('{')? {
                    return Err(syntax("missing {"));
                }
                self.take_until('}', "character name")?;
                self.unsupported("named character escape");
                0
            }
            c if c.is_ascii_alphabetic() || c.is_ascii_digit() => {
                return Err(syntax(format!("bad escape \\{c}")));
            }
            c => u32::from(c),
        })
    }

    // 문자 집합

    fn class(&mut self) -> Result<Node, Error> {
        let negate = self.eat('^')?;
        let mut items: Vec<ClassItem> = Vec::new();
        loop {
            let Some(tok) = self.next()? else {
                return Err(syntax("unterminated character set"));
            };
            if tok == Tok::Ch(']') && !items.is_empty() {
                break;
            }
            let first = self.class_atom(tok)?;
            if !self.eat('-')? {
                items.push(first);
                continue;
            }

            // 범위, 또는 끝의 `-`
            let Some(tok) = self.next()? else {
                return Err(syntax("unterminated character set"));
            };
            if tok == Tok::Ch(']') {
                items.push(first);
                items.push(ClassItem::Range(45, 45));
                break;
            }
            let second = self.class_atom(tok)?;
            match (first, second) {
                (ClassItem::Range(lo, _), ClassItem::Range(hi, _)) if hi >= lo => {
                    items.push(ClassItem::Range(lo, hi));
                }
                _ => return Err(syntax("bad character range")),
            }
        }
        Ok(Node::Class(Class { negate, items }))
    }

    // python _class_escape 와 글자 하나
    fn class_atom(&mut self, tok: Tok) -> Result<ClassItem, Error> {
        let c = match tok {
            Tok::Ch(c) => return Ok(ClassItem::Range(u32::from(c), u32::from(c))),
            Tok::Esc(c) => c,
        };
        let value = match c {
            'b' => 8,
            'd' => return Ok(ClassItem::Cat(Category::Digit)),
            'D' => return Ok(ClassItem::Cat(Category::NotDigit)),
            's' => return Ok(ClassItem::Cat(Category::Space)),
            'S' => return Ok(ClassItem::Cat(Category::NotSpace)),
            'w' => return Ok(ClassItem::Cat(Category::Word)),
            'W' => return Ok(ClassItem::Cat(Category::NotWord)),
            c if is_octal(c) => {
                let digits = self.take_while(2, is_octal)?;
                let value = u32::from_str_radix(&format!("{c}{digits}"), 8).expect("octal digits");
                if value > 0o377 {
                    return Err(syntax("octal escape value outside of range 0-0o377"));
                }
                value
            }
            _ => self.common_escape(c)?,
        };
        Ok(ClassItem::Range(value, value))
    }
}

fn is_octal(c: char) -> bool {
    ('0'..='7').contains(&c)
}

// `{m,n}` 의 수. python 은 MAXREPEAT 이상이면 OverflowError
fn repeat_count(digits: &str) -> Result<u32, Error> {
    match digits.parse::<u64>() {
        Ok(n) if n < MAX_REPEAT => Ok(n as u32),
        _ => Err(Error::Overflow),
    }
}
