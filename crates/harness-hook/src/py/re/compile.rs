//! 나무를 되돌아가며 찾는 기계의 명령 목록으로(python `re._compiler` 자리).

use super::Error;
use super::ast::{Anchor, Node, Repeat};
use super::class::{CompiledClass, literal};
use super::parse::Parsed;

/// 기계 명령 하나.
#[derive(Clone, Copy, Debug)]
pub(super) enum Inst {
    /// 글자 하나(IGNORECASE 는 프로그램 플래그로).
    Lit(u32),
    /// `.`: DOTALL 이 아니면 줄바꿈을 뺀다.
    Any,
    Class(usize),
    At(At),
    /// 앞을 먼저, 실패하면 뒤를.
    Split(usize, usize),
    Jmp(usize),
    /// 잡기 칸에 지금 위치를 적는다.
    Save(usize),
    /// 되풀이 한 바퀴의 시작 위치를 적는다.
    Mark(usize),
    /// 이 바퀴가 아무것도 먹지 않았으면 되풀이를 끝내고 뒤로(두 번째 값) 간다. 빈 바퀴가 끝없이 돌지 않게 하되, 그 바퀴가
    /// 잡은 칸은 남긴다(sre 의 MAX_UNTIL, MIN_UNTIL, POSSESSIVE_REPEAT 가 `ptr == last_ptr` 에서 하는 일).
    Progress(usize, usize),
    /// 글자 하나의 되풀이(sre REPEAT_ONE, MIN_REPEAT_ONE). 뒤는 다음 명령이다.
    RepeatOne(usize),
    Backref(usize),
    /// 앞뒤 보기. 몸은 다음 명령(Jmp) 뒤에 있다.
    Look(usize),
    /// 원자 괄호: 몸이 처음 맞은 끝으로 가고 갈림길은 버린다. 몸은 Look 처럼 놓인다.
    Atomic(usize),
    Match,
}

/// 자리 검사(MULTILINE 을 반영한 꼴).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(super) enum At {
    Begin,
    BeginLine,
    End,
    EndLine,
    BeginString,
    EndString,
    Boundary,
    NotBoundary,
}

/// 되풀이하는 글자 하나.
#[derive(Clone, Copy, Debug)]
pub(super) enum One {
    Lit(u32),
    Any,
    Class(usize),
}

/// 글자 하나의 되풀이.
#[derive(Clone, Copy, Debug)]
pub(super) struct RepeatOne {
    pub item: One,
    pub min: u32,
    /// 끝없음은 `u32::MAX`(python 의 상한은 그보다 하나 작다).
    pub max: u32,
    pub greedy: bool,
    /// 바로 뒤 명령이 글자면 그 글자. 그 글자가 없는 자리에서는 뒤를 해 보지 않는다.
    pub tail_lit: Option<u32>,
    /// 되풀이 글자가 뒤 글자일 수 없다(`" *z"` 의 공백과 z). 그러면 돌려준 자리에서는 뒤가 맞을 수 없다.
    pub disjoint_tail: bool,
    /// ASCII 바이트 b 가 되풀이 글자에 맞으면 b 번째 비트가 켜진다. 글을 바이트로 빨리 센다.
    pub ascii: u128,
}

/// 앞뒤 보기 또는 원자 괄호 하나.
#[derive(Clone, Copy, Debug)]
pub(super) struct LookInfo {
    pub behind: bool,
    pub negate: bool,
    /// 몸의 첫 명령.
    pub start: usize,
    /// lookbehind 가 거슬러 갈 글자 수.
    pub width: usize,
}

/// 읽어 둔 패턴.
#[derive(Clone, Debug)]
pub(super) struct Program {
    pub insts: Vec<Inst>,
    pub classes: Vec<CompiledClass>,
    pub looks: Vec<LookInfo>,
    pub repeats: Vec<RepeatOne>,
    /// 일치가 늘 이 글자로 시작한다(IGNORECASE 가 아닐 때). search 가 시작 자리를 건너뛰는 데 쓴다.
    pub prefix: Option<char>,
    /// 잡기 칸 수(괄호마다 둘, 0 번 포함).
    pub slots: usize,
    /// Mark 칸 수.
    pub marks: usize,
    pub ignore_case: bool,
    pub dotall: bool,
}

// 프로그램이 이보다 커지면(큰 되풀이 수를 겹친 패턴) 옮기지 않는다
const MAX_INSTS: usize = 100_000;

/// 나무를 명령 목록으로. lookbehind 의 폭이 정해지지 않으면 python 처럼 오류다.
pub(super) fn compile(parsed: &Parsed) -> Result<Program, Error> {
    let mut c = Compiler {
        prog: Program {
            insts: Vec::new(),
            classes: Vec::new(),
            looks: Vec::new(),
            repeats: Vec::new(),
            prefix: None,
            slots: parsed.groups * 2,
            marks: 0,
            ignore_case: parsed.flags.ignore_case,
            dotall: parsed.flags.dotall,
        },
        multiline: parsed.flags.multiline,
    };

    // 0 번 괄호가 일치 전체
    c.emit(Inst::Save(0));
    c.node(&parsed.node)?;
    c.emit(Inst::Save(1));
    c.emit(Inst::Match);
    c.link_tails();
    Ok(c.prog)
}

struct Compiler {
    prog: Program,
    multiline: bool,
}

impl Compiler {
    // 글자 되풀이마다 바로 뒤 글자, 그리고 패턴 첫 글자
    fn link_tails(&mut self) {
        // 글자 되풀이 바로 뒤의 글자
        for pc in 0..self.prog.insts.len() {
            let (Inst::RepeatOne(i), Some(&Inst::Lit(c))) =
                (self.prog.insts[pc], self.prog.insts.get(pc + 1))
            else {
                continue;
            };

            // IGNORECASE 의 짝은 넓어서 겹치지 않는다고 보지 않는다
            let item = self.prog.repeats[i].item;
            let disjoint = !self.prog.ignore_case
                && char::from_u32(c).is_some_and(|ch| !self.one_matches(item, ch));
            let rep = &mut self.prog.repeats[i];
            rep.tail_lit = Some(c);
            rep.disjoint_tail = disjoint;
        }

        // 패턴 첫 글자(0 번 명령은 Save(0))
        if let Some(Inst::Lit(c)) = self.prog.insts.get(1)
            && !self.prog.ignore_case
        {
            self.prog.prefix = char::from_u32(*c);
        }
    }

    // 되풀이 글자 하나가 c 에 맞는가(vm 의 판정과 같다)
    fn one_matches(&self, item: One, c: char) -> bool {
        match item {
            One::Lit(p) => literal(p, c, self.prog.ignore_case),
            One::Any => c != '\n' || self.prog.dotall,
            One::Class(i) => self.prog.classes[i].matches(c),
        }
    }

    fn emit(&mut self, inst: Inst) -> usize {
        self.prog.insts.push(inst);
        self.prog.insts.len() - 1
    }

    fn pc(&self) -> usize {
        self.prog.insts.len()
    }

    // 뒤에 채울 Split, Jmp 의 대상
    fn patch(&mut self, at: usize, inst: Inst) {
        self.prog.insts[at] = inst;
    }

    fn node(&mut self, node: &Node) -> Result<(), Error> {
        if self.prog.insts.len() > MAX_INSTS {
            return Err(Error::Unsupported("pattern too large"));
        }
        match node {
            Node::Lit(c) => {
                self.emit(Inst::Lit(*c));
            }
            Node::Any => {
                self.emit(Inst::Any);
            }
            Node::Class(class) => {
                let compiled = CompiledClass::new(class, self.prog.ignore_case);
                self.prog.classes.push(compiled);
                self.emit(Inst::Class(self.prog.classes.len() - 1));
            }
            Node::At(anchor) => {
                let at = self.anchor(*anchor);
                self.emit(Inst::At(at));
            }
            Node::Group(gid, inner) => match gid {
                Some(g) => {
                    self.emit(Inst::Save(2 * g));
                    self.node(inner)?;
                    self.emit(Inst::Save(2 * g + 1));
                }
                None => self.node(inner)?,
            },
            Node::Concat(items) => {
                for item in items {
                    self.node(item)?;
                }
            }
            Node::Alt(items) => self.alt(items)?,
            Node::Repeat(r) => self.repeat(r)?,
            Node::Backref(g) => {
                self.emit(Inst::Backref(*g));
            }
            Node::Look(look) => self.look(look.behind, look.negate, &look.node)?,
            Node::Atomic(inner) => self.atomic(inner)?,
            Node::Fail => {
                // 늘 실패: 맞을 수 없는 빈 집합
                let never = CompiledClass::new(
                    &super::ast::Class {
                        negate: false,
                        items: Vec::new(),
                    },
                    false,
                );
                self.prog.classes.push(never);
                self.emit(Inst::Class(self.prog.classes.len() - 1));
            }
        }
        Ok(())
    }

    fn anchor(&self, anchor: Anchor) -> At {
        match anchor {
            Anchor::Begin if self.multiline => At::BeginLine,
            Anchor::Begin => At::Begin,
            Anchor::End if self.multiline => At::EndLine,
            Anchor::End => At::End,
            Anchor::BeginString => At::BeginString,
            Anchor::EndString => At::EndString,
            Anchor::Boundary => At::Boundary,
            Anchor::NotBoundary => At::NotBoundary,
        }
    }

    // a|b|c: Split(a, 다음) ... 마지막 갈래는 Split 없이, 갈래 끝마다 Jmp(끝)
    fn alt(&mut self, items: &[Node]) -> Result<(), Error> {
        let mut jumps = Vec::new();
        for (i, item) in items.iter().enumerate() {
            if i + 1 == items.len() {
                self.node(item)?;
                break;
            }
            let split = self.emit(Inst::Split(0, 0));
            self.node(item)?;
            jumps.push(self.emit(Inst::Jmp(0)));
            let next = self.pc();
            self.patch(split, Inst::Split(split + 1, next));
        }
        let end = self.pc();
        for j in jumps {
            self.patch(j, Inst::Jmp(end));
        }
        Ok(())
    }

    // 글자 하나면 RepeatOne. 아니면 최소 횟수만큼 펼치고, 나머지는 선택 조각을 겹치거나(상한) 고리(끝없음)로.
    // 소유 되풀이는 원자 괄호로 감싼다
    fn repeat(&mut self, r: &Repeat) -> Result<(), Error> {
        if r.possessive {
            let plain = Node::Repeat(Box::new(Repeat {
                possessive: false,
                ..r.clone()
            }));
            return self.atomic(&plain);
        }
        if let Some(item) = self.one(&r.node) {
            let ascii = (0u8..128)
                .filter(|&b| self.one_matches(item, char::from(b)))
                .fold(0u128, |bits, b| bits | (1 << b));
            self.prog.repeats.push(RepeatOne {
                item,
                min: r.min,
                max: r.max.unwrap_or(u32::MAX),
                greedy: r.greedy,
                tail_lit: None,
                disjoint_tail: false,
                ascii,
            });
            self.emit(Inst::RepeatOne(self.prog.repeats.len() - 1));
            return Ok(());
        }

        // 빈 몸(`(?:){99999}`)은 명령이 늘지 않아 크기 검사에 걸리지 않는다
        if r.min as usize > MAX_INSTS {
            return Err(Error::Unsupported("pattern too large"));
        }
        for _ in 0..r.min {
            self.node(&r.node)?;
        }
        match r.max {
            Some(max) => self.optional_copies(r, max),
            None => self.star(r),
        }
    }

    // python _simple: 글자 하나를 먹는 조각(잡지 않는 괄호로 감싼 것도)
    fn one(&mut self, node: &Node) -> Option<One> {
        match node {
            Node::Lit(c) => Some(One::Lit(*c)),
            Node::Any => Some(One::Any),
            Node::Class(class) => {
                let compiled = CompiledClass::new(class, self.prog.ignore_case);
                self.prog.classes.push(compiled);
                Some(One::Class(self.prog.classes.len() - 1))
            }
            Node::Group(None, inner) => self.one(inner),
            _ => None,
        }
    }

    // 빈 글에도 맞는 몸이면 바퀴마다 시작 위치를 적을 Mark 칸
    fn progress_mark(&mut self, r: &Repeat) -> Option<usize> {
        if !r.node.nullable() {
            return None;
        }
        self.prog.marks += 1;
        Some(self.prog.marks - 1)
    }

    // 상한까지의 선택 조각: Split(몸, 끝); [Mark]; 몸; [Progress(끝)] 을 겹친다
    fn optional_copies(&mut self, r: &Repeat, max: u32) -> Result<(), Error> {
        let mark = self.progress_mark(r);
        let mut exits = Vec::new();
        let mut progress = Vec::new();
        for _ in r.min..max {
            exits.push(self.emit(Inst::Split(0, 0)));
            if let Some(m) = mark {
                self.emit(Inst::Mark(m));
            }
            self.node(&r.node)?;
            if let Some(m) = mark {
                progress.push((self.emit(Inst::Progress(m, 0)), m));
            }
        }

        // 끝을 채운다
        let end = self.pc();
        for split in exits {
            self.patch(split, self.choice(r.greedy, split + 1, end));
        }
        for (at, m) in progress {
            self.patch(at, Inst::Progress(m, end));
        }
        Ok(())
    }

    // L: Split(몸, 끝); [Mark]; 몸; [Progress(끝)]; Jmp(L)
    fn star(&mut self, r: &Repeat) -> Result<(), Error> {
        let mark = self.progress_mark(r);
        let split = self.emit(Inst::Split(0, 0));
        if let Some(m) = mark {
            self.emit(Inst::Mark(m));
        }
        self.node(&r.node)?;
        let progress = mark.map(|m| (self.emit(Inst::Progress(m, 0)), m));
        self.emit(Inst::Jmp(split));

        // 끝을 채운다
        let end = self.pc();
        self.patch(split, self.choice(r.greedy, split + 1, end));
        if let Some((at, m)) = progress {
            self.patch(at, Inst::Progress(m, end));
        }
        Ok(())
    }

    fn choice(&self, greedy: bool, body: usize, skip: usize) -> Inst {
        if greedy {
            Inst::Split(body, skip)
        } else {
            Inst::Split(skip, body)
        }
    }

    // Atomic(i); Jmp(끝); 몸; Match
    fn atomic(&mut self, body: &Node) -> Result<(), Error> {
        let index = self.prog.looks.len();
        self.prog.looks.push(LookInfo {
            behind: false,
            negate: false,
            start: 0,
            width: 0,
        });
        self.emit(Inst::Atomic(index));
        self.body(index, body)
    }

    // Look(i); Jmp(끝); 몸; Match
    fn look(&mut self, behind: bool, negate: bool, body: &Node) -> Result<(), Error> {
        let width = if behind {
            match body.width() {
                (lo, Some(hi)) if lo == hi => lo as usize,
                _ => {
                    return Err(Error::Syntax(
                        "look-behind requires fixed-width pattern".into(),
                    ));
                }
            }
        } else {
            0
        };
        let index = self.prog.looks.len();
        self.prog.looks.push(LookInfo {
            behind,
            negate,
            start: 0,
            width,
        });

        self.emit(Inst::Look(index));
        self.body(index, body)
    }

    // Look, Atomic 다음: Jmp(끝); 몸; Match
    fn body(&mut self, index: usize, body: &Node) -> Result<(), Error> {
        let jump = self.emit(Inst::Jmp(0));
        self.prog.looks[index].start = self.pc();
        self.node(body)?;
        self.emit(Inst::Match);
        let end = self.pc();
        self.patch(jump, Inst::Jmp(end));
        Ok(())
    }
}
