//! 되돌아가며 찾는 기계(sre 의 `SRE(match)` 자리). 갈림길은 명시한 스택에 쌓아 긴 글에서도 호출 스택이 깊어지지 않는다.

use super::Match;
use super::class::literal;
use super::compile::{At, Inst, Program};
use crate::py::unicode::{is_word, lower};

/// 스택에 쌓는 것: 갈 다른 길, 또는 되돌아갈 때 되돌릴 칸 값.
#[derive(Clone, Copy, Debug)]
enum Frame {
    Retry { pc: usize, pos: usize },
    Slot { slot: usize, old: Option<usize> },
    Mark { mark: usize, old: usize },
}

/// 일치를 끝낼 조건.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
enum Accept {
    /// 아무 데서나(search, match, 앞 보기).
    Anywhere,
    /// 글 끝에서만(fullmatch).
    TextEnd,
    /// 이 위치에서 끝나는 빈 일치는 안 된다(빈 일치 다음의 finditer).
    NotEmptyAt(usize),
}

struct Vm<'p, 't> {
    prog: &'p Program,
    text: &'t str,
    stack: Vec<Frame>,
    slots: Vec<Option<usize>>,
    marks: Vec<usize>,
}

/// 찾는 방식.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub(super) enum Mode {
    /// `from` 부터 시작 위치를 옮겨 가며(search).
    Search,
    /// 빈 일치 바로 뒤의 search: `from` 에서 시작하는 빈 일치는 건너뛴다(python 의 must_advance).
    SearchAdvance,
    /// `from` 에서 글 끝까지(fullmatch).
    Full,
}

/// `from` 부터 찾는다.
pub(super) fn search(prog: &Program, text: &str, from: usize, mode: Mode) -> Option<Match> {
    let mut vm = Vm::new(prog, text);
    let mut start = from;
    let full = mode == Mode::Full;
    loop {
        let end = match mode {
            Mode::Full => Accept::TextEnd,
            Mode::SearchAdvance if start == from => Accept::NotEmptyAt(from),
            _ => Accept::Anywhere,
        };
        if vm.start(start, end) {
            return Some(Match { slots: vm.slots });
        }
        if full || start >= text.len() {
            return None;
        }
        start += text[start..].chars().next().map_or(1, char::len_utf8);
    }
}

/// `pos` 에서만 시작하는 일치(python `pattern.match`).
pub(super) fn match_at(prog: &Program, text: &str, pos: usize) -> Option<Match> {
    let mut vm = Vm::new(prog, text);
    let matched = vm.start(pos, Accept::Anywhere);
    matched.then_some(Match { slots: vm.slots })
}

impl<'p, 't> Vm<'p, 't> {
    fn new(prog: &'p Program, text: &'t str) -> Vm<'p, 't> {
        Vm {
            prog,
            text,
            stack: Vec::new(),
            slots: vec![None; prog.slots],
            marks: vec![usize::MAX; prog.marks],
        }
    }

    fn start(&mut self, pos: usize, end: Accept) -> bool {
        self.slots.iter_mut().for_each(|s| *s = None);
        self.marks.iter_mut().for_each(|m| *m = usize::MAX);
        self.stack.clear();
        self.run(0, pos, end).is_some()
    }

    // pc 에서 pos 로 돌린다. 맞으면 끝 위치. 스택은 들어올 때의 높이 위만 쓴다
    fn run(&mut self, pc: usize, pos: usize, end: Accept) -> Option<usize> {
        let base = self.stack.len();
        let (mut pc, mut pos) = (pc, pos);
        loop {
            match self.step(pc, pos, end) {
                Step::Next(next_pc, next_pos) => {
                    pc = next_pc;
                    pos = next_pos;
                }
                Step::Done => return Some(pos),
                Step::Fail => match self.backtrack(base) {
                    Some((retry_pc, retry_pos)) => {
                        pc = retry_pc;
                        pos = retry_pos;
                    }
                    None => return None,
                },
            }
        }
    }

    // 다른 길을 꺼낸다. 그 사이의 칸 값은 되돌린다. base 아래로는 내려가지 않는다
    fn backtrack(&mut self, base: usize) -> Option<(usize, usize)> {
        while self.stack.len() > base {
            match self.stack.pop().expect("above base") {
                Frame::Retry { pc, pos } => return Some((pc, pos)),
                Frame::Slot { slot, old } => self.slots[slot] = old,
                Frame::Mark { mark, old } => self.marks[mark] = old,
            }
        }
        None
    }

    fn step(&mut self, pc: usize, pos: usize, end: Accept) -> Step {
        let next_char = self.text[pos..].chars().next();
        match self.prog.insts[pc] {
            // 글자 하나를 먹는 명령
            Inst::Lit(p) => match next_char {
                Some(c) if literal(p, c, self.prog.ignore_case) => {
                    Step::Next(pc + 1, pos + c.len_utf8())
                }
                _ => Step::Fail,
            },
            Inst::Any => match next_char {
                Some(c) if c != '\n' || self.prog.dotall => Step::Next(pc + 1, pos + c.len_utf8()),
                _ => Step::Fail,
            },
            Inst::Class(i) => match next_char {
                Some(c) if self.prog.classes[i].matches(c) => {
                    Step::Next(pc + 1, pos + c.len_utf8())
                }
                _ => Step::Fail,
            },

            // 갈림길과 칸 기록
            Inst::Split(first, second) => {
                self.stack.push(Frame::Retry { pc: second, pos });
                Step::Next(first, pos)
            }
            Inst::Jmp(to) => Step::Next(to, pos),
            Inst::Save(slot) => {
                self.stack.push(Frame::Slot {
                    slot,
                    old: self.slots[slot],
                });
                self.slots[slot] = Some(pos);
                Step::Next(pc + 1, pos)
            }
            Inst::Mark(mark) => {
                self.stack.push(Frame::Mark {
                    mark,
                    old: self.marks[mark],
                });
                self.marks[mark] = pos;
                Step::Next(pc + 1, pos)
            }
            Inst::Progress(mark) => step_if(self.marks[mark] != pos, pc, pos),

            // 자리 검사, 괄호 참조, 앞뒤 보기, 끝
            Inst::At(at) => step_if(self.at(at, pos), pc, pos),
            Inst::Backref(g) => match self.backref(g, pos) {
                Some(len) => Step::Next(pc + 1, pos + len),
                None => Step::Fail,
            },
            Inst::Look(i) => step_if(self.look(i, pos), pc, pos),
            Inst::Atomic(i) => match self.atomic(i, pos) {
                Some(end) => Step::Next(pc + 1, end),
                None => Step::Fail,
            },
            Inst::Match if end == Accept::TextEnd && pos != self.text.len() => Step::Fail,
            Inst::Match if end == Accept::NotEmptyAt(pos) => Step::Fail,
            Inst::Match => Step::Done,
        }
    }

    fn at(&self, at: At, pos: usize) -> bool {
        let text = self.text.as_bytes();
        match at {
            At::Begin | At::BeginString => pos == 0,
            At::BeginLine => pos == 0 || text[pos - 1] == b'\n',
            At::End => pos == text.len() || (pos + 1 == text.len() && text[pos] == b'\n'),
            At::EndLine => pos == text.len() || text[pos] == b'\n',
            At::EndString => pos == text.len(),
            At::Boundary => !text.is_empty() && self.word_before(pos) != self.word_after(pos),
            At::NotBoundary => !text.is_empty() && self.word_before(pos) == self.word_after(pos),
        }
    }

    fn word_before(&self, pos: usize) -> bool {
        self.text[..pos]
            .chars()
            .next_back()
            .is_some_and(|c| is_word(u32::from(c)))
    }

    fn word_after(&self, pos: usize) -> bool {
        self.text[pos..]
            .chars()
            .next()
            .is_some_and(|c| is_word(u32::from(c)))
    }

    // 괄호 g 가 잡은 글이 pos 에 또 있으면 그 길이. 맞지 않은 괄호는 실패
    fn backref(&self, g: usize, pos: usize) -> Option<usize> {
        let (a, b) = (
            self.slots.get(2 * g)?.as_ref()?,
            self.slots.get(2 * g + 1)?.as_ref()?,
        );
        let want = &self.text[*a..*b];
        let rest = &self.text[pos..];
        if !self.prog.ignore_case {
            return rest.starts_with(want).then_some(want.len());
        }

        // IGNORECASE: 글자마다 소문자로
        let mut len = 0;
        let mut got = rest.chars();
        for w in want.chars() {
            let c = got.next()?;
            if lower(u32::from(c)) != lower(u32::from(w)) {
                return None;
            }
            len += c.len_utf8();
        }
        Some(len)
    }

    // 앞뒤 보기. 긍정 검사가 맞으면 안에서 잡은 칸은 남기고(되돌아갈 때 되돌릴 기록과 함께), 부정 검사는 모두 되돌린다
    fn look(&mut self, i: usize, pos: usize) -> bool {
        let info = self.prog.looks[i];
        let start = if info.behind {
            match back_chars(self.text, pos, info.width) {
                Some(start) => start,
                None => return info.negate,
            }
        } else {
            pos
        };

        let base = self.stack.len();
        let matched = self.run(info.start, start, Accept::Anywhere).is_some();
        if matched && !info.negate {
            self.commit(base);
        } else {
            while self.backtrack(base).is_some() {}
        }
        matched != info.negate
    }

    // 원자 괄호: 몸이 처음 맞은 끝. 안에서 잡은 칸은 남긴다
    fn atomic(&mut self, i: usize, pos: usize) -> Option<usize> {
        let base = self.stack.len();
        let end = self.run(self.prog.looks[i].start, pos, Accept::Anywhere)?;
        self.commit(base);
        Some(end)
    }

    // base 위의 갈림길은 버리고, 칸을 되돌릴 기록만 남긴다(바깥이 되돌아가면 그때 되돌린다)
    fn commit(&mut self, base: usize) {
        let mut kept = self.stack.split_off(base);
        kept.retain(|f| !matches!(f, Frame::Retry { .. }));
        self.stack.extend(kept);
    }
}

enum Step {
    Next(usize, usize),
    Done,
    Fail,
}

fn step_if(ok: bool, pc: usize, pos: usize) -> Step {
    if ok {
        Step::Next(pc + 1, pos)
    } else {
        Step::Fail
    }
}

// pos 에서 n 글자 앞의 바이트 위치. 글자가 모자라면 None
fn back_chars(text: &str, pos: usize, n: usize) -> Option<usize> {
    let mut start = pos;
    let mut chars = text[..pos].chars();
    for _ in 0..n {
        start -= chars.next_back()?.len_utf8();
    }
    Some(start)
}
