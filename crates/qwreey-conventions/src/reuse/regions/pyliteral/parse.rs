//! python 문장과 식의 부분 집합을 읽어 str 상수를 모은다(`ast.walk` 의 str `Constant`).

use super::lex::{FItem, StrTok, Tok};
use super::{KEYWORDS, R, Unsure};

// 대입 대상인지 가리는 데 쓰는 식의 꼴
#[derive(Clone, Debug, PartialEq)]
enum Kind {
    Name,
    Attr,
    Subscript,
    Starred(Box<Kind>),
    Tuple(Vec<Kind>),
    List(Vec<Kind>),
    Other,
}

fn assignable(k: &Kind) -> bool {
    match k {
        Kind::Name | Kind::Attr | Kind::Subscript => true,
        Kind::Starred(inner) => assignable(inner),
        Kind::Tuple(items) | Kind::List(items) => {
            items.iter().all(assignable)
                && items
                    .iter()
                    .filter(|k| matches!(k, Kind::Starred(_)))
                    .count()
                    <= 1
        }
        Kind::Other => false,
    }
}

/// 낱말들을 읽으며 str 상수를 모은다.
pub struct Parser<'a> {
    toks: &'a [Tok],
    i: usize,
    out: Vec<String>,
}

impl<'a> Parser<'a> {
    /// 맨 앞에서 시작한다.
    pub fn new(toks: &'a [Tok]) -> Parser<'a> {
        Parser {
            toks,
            i: 0,
            out: Vec::new(),
        }
    }

    /// 모은 str 상수들.
    pub fn into_constants(self) -> Vec<String> {
        self.out
    }

    fn peek(&self) -> Option<&Tok> {
        self.toks.get(self.i)
    }

    fn is_op(&self, op: &str) -> bool {
        matches!(self.peek(), Some(Tok::Op(o)) if *o == op)
    }

    fn is_word(&self, w: &str) -> bool {
        matches!(self.peek(), Some(Tok::Name(n)) if n == w)
    }

    fn eat_op(&mut self, op: &str) -> bool {
        let hit = self.is_op(op);
        if hit {
            self.i += 1;
        }
        hit
    }

    fn eat_word(&mut self, w: &str) -> bool {
        let hit = self.is_word(w);
        if hit {
            self.i += 1;
        }
        hit
    }

    fn expect_op(&mut self, op: &str) -> R<()> {
        if self.eat_op(op) { Ok(()) } else { Err(Unsure) }
    }

    // 낱말이 식을 끝내는 자리인가(닫는 괄호, 쉼표, 줄 끝 등)
    fn at_end(&self) -> bool {
        matches!(
            self.peek(),
            None | Some(Tok::Newline) | Some(Tok::Op(")" | "]" | "}" | "," | ":" | "=" | ";"))
        )
    }

    /// 모듈 전체: 문장들.
    pub fn module(&mut self) -> R<()> {
        while self.peek().is_some() {
            if self.eat_tok_newline() {
                continue;
            }
            self.statement()?;
            if !(self.eat_op(";") || self.eat_tok_newline()) {
                return Err(Unsure);
            }
        }
        Ok(())
    }

    fn eat_tok_newline(&mut self) -> bool {
        let hit = matches!(self.peek(), Some(Tok::Newline));
        if hit {
            self.i += 1;
        }
        hit
    }

    // 식 문장, 대입(`a = b = c`), 주석 대입(`a: T = v`)
    fn statement(&mut self) -> R<()> {
        let first = self.testlist(true)?;

        // Annotated assignment
        if self.eat_op(":") {
            if !matches!(first, Kind::Name | Kind::Attr | Kind::Subscript) {
                return Err(Unsure);
            }
            self.test()?;
            if self.eat_op("=") {
                self.testlist(true)?;
            }
            return Ok(());
        }

        // Assignment chain: every part but the last is a target
        let mut last = first;
        while self.eat_op("=") {
            if !assignable(&last) {
                return Err(Unsure);
            }
            last = self.testlist(true)?;
        }

        // python 의 ast.parse 는 `X = *y` 와 `*y` 문장을 받는다(막는 것은 그 뒤의 compile 이다)
        Ok(())
    }

    /// f-string 칸: 식 하나(쉼표로 이은 꼴도)가 모든 낱말을 쓴다.
    pub fn expression_only(&mut self) -> R<()> {
        let k = self.testlist(true)?;
        if matches!(k, Kind::Starred(_)) || !self.eat_tok_newline() || self.peek().is_some() {
            return Err(Unsure);
        }
        Ok(())
    }

    // 쉼표로 이은 식들(꼬리 쉼표가 있으면 튜플)
    fn testlist(&mut self, star: bool) -> R<Kind> {
        let first = self.test_or_star(star)?;
        if !self.is_op(",") {
            return Ok(first);
        }
        let mut items = vec![first];
        while self.eat_op(",") {
            if self.at_end() {
                break;
            }
            items.push(self.test_or_star(star)?);
        }
        Ok(Kind::Tuple(items))
    }

    fn test_or_star(&mut self, star: bool) -> R<Kind> {
        if self.is_op("*") {
            if !star {
                return Err(Unsure);
            }
            self.i += 1;
            let inner = self.or_expr()?;
            return Ok(Kind::Starred(Box::new(inner)));
        }
        self.test()
    }

    // 조건식 `a if c else b`
    fn test(&mut self) -> R<Kind> {
        let k = self.or_test()?;
        if self.eat_word("if") {
            self.or_test()?;
            if !self.eat_word("else") {
                return Err(Unsure);
            }
            self.test()?;
            return Ok(Kind::Other);
        }
        Ok(k)
    }

    fn or_test(&mut self) -> R<Kind> {
        let mut k = self.and_test()?;
        while self.eat_word("or") {
            self.and_test()?;
            k = Kind::Other;
        }
        Ok(k)
    }

    fn and_test(&mut self) -> R<Kind> {
        let mut k = self.not_test()?;
        while self.eat_word("and") {
            self.not_test()?;
            k = Kind::Other;
        }
        Ok(k)
    }

    fn not_test(&mut self) -> R<Kind> {
        if self.eat_word("not") {
            self.not_test()?;
            return Ok(Kind::Other);
        }
        self.comparison()
    }

    fn comparison(&mut self) -> R<Kind> {
        let mut k = self.or_expr()?;
        loop {
            let op = if ["<", ">", "==", ">=", "<=", "!="]
                .iter()
                .any(|o| self.is_op(o))
            {
                self.i += 1;
                true
            } else if self.eat_word("in") {
                true
            } else if self.is_word("not")
                && matches!(self.toks.get(self.i + 1), Some(Tok::Name(n)) if n == "in")
            {
                self.i += 2;
                true
            } else if self.eat_word("is") {
                self.eat_word("not");
                true
            } else {
                false
            };
            if !op {
                return Ok(k);
            }
            self.or_expr()?;
            k = Kind::Other;
        }
    }

    // `|`, `^`, `&`, 자리 옮김, 더하기, 곱하기 차례(이항 연산자는 판정에 상관없어 한 사다리로 읽는다)
    fn or_expr(&mut self) -> R<Kind> {
        const BINARY: &[&str] = &[
            "|", "^", "&", "<<", ">>", "+", "-", "*", "/", "//", "%", "@",
        ];
        let mut k = self.factor()?;
        while BINARY.iter().any(|o| self.is_op(o)) {
            self.i += 1;
            self.factor()?;
            k = Kind::Other;
        }
        Ok(k)
    }

    fn factor(&mut self) -> R<Kind> {
        if ["+", "-", "~"].iter().any(|o| self.is_op(o)) {
            self.i += 1;
            self.factor()?;
            return Ok(Kind::Other);
        }
        let k = self.atom_expr()?;
        if self.eat_op("**") {
            self.factor()?;
            return Ok(Kind::Other);
        }
        Ok(k)
    }

    // 원자 뒤의 호출, 첨자, 속성
    fn atom_expr(&mut self) -> R<Kind> {
        let mut k = self.atom()?;
        loop {
            if self.eat_op("(") {
                self.arguments()?;
                k = Kind::Other;
            } else if self.eat_op("[") {
                self.subscripts()?;
                k = Kind::Subscript;
            } else if self.eat_op(".") {
                match self.peek() {
                    Some(Tok::Name(n)) if !KEYWORDS.contains(&n.as_str()) => self.i += 1,
                    _ => return Err(Unsure),
                }
                k = Kind::Attr;
            } else {
                return Ok(k);
            }
        }
    }

    fn atom(&mut self) -> R<Kind> {
        let tok = self.peek().cloned().ok_or(Unsure)?;
        match tok {
            Tok::Num => {
                self.i += 1;
                Ok(Kind::Other)
            }
            Tok::Name(n) if matches!(n.as_str(), "None" | "True" | "False") => {
                self.i += 1;
                Ok(Kind::Other)
            }
            Tok::Name(n) if KEYWORDS.contains(&n.as_str()) => Err(Unsure),
            Tok::Name(_) => {
                self.i += 1;
                Ok(Kind::Name)
            }
            Tok::Str(_) => {
                self.strings()?;
                Ok(Kind::Other)
            }
            Tok::Op("...") => {
                self.i += 1;
                Ok(Kind::Other)
            }
            Tok::Op("(") => {
                self.i += 1;
                if self.eat_op(")") {
                    return Ok(Kind::Tuple(Vec::new()));
                }
                let k = self.testlist(true)?;
                self.expect_op(")")?;
                if matches!(k, Kind::Starred(_)) {
                    return Err(Unsure);
                }
                Ok(k)
            }
            Tok::Op("[") => {
                self.i += 1;
                let items = self.display_items("]")?;
                Ok(Kind::List(items))
            }
            Tok::Op("{") => {
                self.i += 1;
                self.dict_or_set()?;
                Ok(Kind::Other)
            }
            _ => Err(Unsure),
        }
    }

    // 옆에 붙은 문자열들을 상수로(python 의 이어 붙이기와 f-string 합치기)
    fn strings(&mut self) -> R<()> {
        let mut run = Vec::new();
        while let Some(Tok::Str(s)) = self.peek() {
            run.push(s.clone());
            self.i += 1;
        }
        let bytes = run.iter().filter(|s| **s == StrTok::Bytes).count();
        if bytes == run.len() {
            return Ok(());
        }
        if bytes > 0 {
            return Err(Unsure);
        }

        // Plain strings make one constant, even an empty one
        if !run.iter().any(|s| matches!(s, StrTok::F(_))) {
            let mut value = String::new();
            for s in &run {
                if let StrTok::Plain(v) = s {
                    value.push_str(v);
                }
            }
            self.out.push(value);
            return Ok(());
        }

        // With an f-string: text runs between fields, and the constants inside fields
        let mut cur = String::new();
        for s in run {
            let items = match s {
                StrTok::Plain(v) => vec![FItem::Lit(v)],
                StrTok::F(items) => items,
                StrTok::Bytes => return Err(Unsure),
            };
            for item in items {
                match item {
                    FItem::Lit(v) => cur.push_str(&v),
                    FItem::Break => {
                        if !cur.is_empty() {
                            self.out.push(std::mem::take(&mut cur));
                        }
                    }
                    FItem::Consts(c) => self.out.extend(c),
                }
            }
        }
        if !cur.is_empty() {
            self.out.push(cur);
        }
        Ok(())
    }

    // `[`, `(` 안의 원소들(꼬리 쉼표 가능, 내포는 옮기지 않는다)
    fn display_items(&mut self, close: &str) -> R<Vec<Kind>> {
        let mut items = Vec::new();
        while !self.eat_op(close) {
            items.push(self.test_or_star(true)?);
            if self.is_word("for") || self.is_word("async") {
                return Err(Unsure);
            }
            if !self.eat_op(",") {
                self.expect_op(close)?;
                break;
            }
        }
        Ok(items)
    }

    // `{...}`: dict(`k: v`, `**d`) 또는 set
    fn dict_or_set(&mut self) -> R<()> {
        if self.eat_op("}") {
            return Ok(());
        }
        let mut dict: Option<bool> = None;
        loop {
            if self.eat_op("**") {
                if dict == Some(false) {
                    return Err(Unsure);
                }
                dict = Some(true);
                self.or_expr()?;
            } else {
                let star = self.is_op("*");
                self.test_or_star(true)?;
                let pair = self.eat_op(":");
                if star && pair {
                    return Err(Unsure);
                }
                match dict {
                    None => dict = Some(pair),
                    Some(d) if d != pair => return Err(Unsure),
                    _ => {}
                }
                if pair {
                    self.test()?;
                }
            }
            if self.is_word("for") || self.is_word("async") {
                return Err(Unsure);
            }
            if !self.eat_op(",") {
                return self.expect_op("}");
            }
            if self.eat_op("}") {
                return Ok(());
            }
        }
    }

    // 호출 인자: 자리 인자, `이름=값`, `*a`, `**k`. python 이 막는 차례(이름 인자 뒤 자리 인자, 같은 이름 둘)는 Unsure
    fn arguments(&mut self) -> R<()> {
        let mut keywords: Vec<String> = Vec::new();
        // 이름 인자 뒤에는 자리 인자가, `**` 뒤에는 `*` 도 올 수 없다
        let mut after_keyword = false;
        let mut after_double_star = false;
        while !self.eat_op(")") {
            if self.eat_op("**") {
                self.test()?;
                after_keyword = true;
                after_double_star = true;
            } else if self.eat_op("*") {
                if after_double_star {
                    return Err(Unsure);
                }
                self.test()?;
            } else if let (Some(Tok::Name(n)), Some(Tok::Op("="))) =
                (self.peek().cloned(), self.toks.get(self.i + 1))
            {
                if KEYWORDS.contains(&n.as_str()) || keywords.contains(&n) {
                    return Err(Unsure);
                }
                self.i += 2;
                self.test()?;
                keywords.push(n);
                after_keyword = true;
            } else {
                if after_keyword {
                    return Err(Unsure);
                }
                self.test()?;
            }

            // A comprehension argument is not read here
            if self.is_word("for") || self.is_word("async") {
                return Err(Unsure);
            }
            if !self.eat_op(",") {
                return self.expect_op(")");
            }
        }
        Ok(())
    }

    // 첨자: 식이나 `a:b:c` 조각, 쉼표로 여럿
    fn subscripts(&mut self) -> R<()> {
        loop {
            if !self.is_op(":") {
                self.test_or_star(true)?;
            }
            if self.eat_op(":") {
                if !self.at_end() {
                    self.test()?;
                }
                if self.eat_op(":") && !self.at_end() {
                    self.test()?;
                }
            }
            if !self.eat_op(",") {
                return self.expect_op("]");
            }
            if self.eat_op("]") {
                return Ok(());
            }
        }
    }
}
