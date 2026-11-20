//! 되돌아가며 찾는 기계(sre 의 `SRE(match)` 자리). 갈림길은 명시한 스택에 쌓아 긴 글에서도 호출 스택이 깊어지지 않는다.

use super::Match;
use super::class::literal;
use super::compile::{At, Inst, One, Program};
use crate::py::unicode::{is_word, lower};

/// 스택에 쌓는 것: 갈 다른 길, 또는 되돌아갈 때 되돌릴 칸 값.
#[derive(Clone, Copy, Debug)]
enum Frame {
    Retry {
        pc: usize,
        pos: usize,
    },
    Slot {
        slot: usize,
        old: Option<usize>,
    },
    Mark {
        mark: usize,
        old: usize,
    },
    /// 탐욕 RepeatOne: 지금 `cur` 까지 먹었고 `floor`(최소 횟수의 끝)까지 하나씩 돌려줄 수 있다.
    Greedy {
        pc: usize,
        floor: usize,
        cur: usize,
    },
    /// 게으른 RepeatOne: 지금 `cur` 까지 `count` 번 먹었고 하나씩 더 먹을 수 있다.
    Lazy {
        pc: usize,
        cur: usize,
        count: u32,
    },
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
    /// 끝없는 탐욕 RepeatOne 마다 마지막으로 센 글자 줄(시작, 끝). 줄 안 어디서 세어도 끝은 같다.
    runs: Vec<(usize, usize)>,
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
    if let Some(c) = prog.prefix
        && !full
    {
        start += text[start..].find(c)?;
    }
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

        // 패턴이 글자로 시작하면 그 글자가 있는 자리로 건너뛴다
        if let Some(c) = prog.prefix {
            start += text[start..].find(c)?;
        }
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
            runs: vec![(usize::MAX, 0); prog.repeats.len()],
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

                // 글자 되풀이: 하나 돌려주거나 하나 더 먹고 뒤를 다시 해 본다
                Frame::Greedy { pc, floor, cur } => {
                    let back = prev_char(self.text, cur);
                    if let Some(pos) = self.give_back(pc, floor, back) {
                        return Some((pc + 1, pos));
                    }
                }
                Frame::Lazy { pc, cur, count } => {
                    if let Some(pos) = self.take_more(pc, cur, count) {
                        return Some((pc + 1, pos));
                    }
                }
            }
        }
        None
    }

    // base 위를 모두 버리고 칸 값만 되돌린다(다른 길은 해 보지 않는다)
    fn unwind(&mut self, base: usize) {
        while self.stack.len() > base {
            match self.stack.pop().expect("above base") {
                Frame::Slot { slot, old } => self.slots[slot] = old,
                Frame::Mark { mark, old } => self.marks[mark] = old,
                Frame::Retry { .. } | Frame::Greedy { .. } | Frame::Lazy { .. } => {}
            }
        }
    }

    // RepeatOne 의 글자 하나가 pos 에 맞으면 그 뒤 위치
    fn one(&self, item: One, pos: usize) -> Option<usize> {
        let c = self.text[pos..].chars().next()?;
        let ok = match item {
            One::Lit(p) => literal(p, c, self.prog.ignore_case),
            One::Any => c != '\n' || self.prog.dotall,
            One::Class(i) => self.prog.classes[i].matches(c),
        };
        ok.then(|| pos + c.len_utf8())
    }

    // pos 에서 뒤의 첫 글자가 맞을 수 있는가(뒤가 글자가 아니면 늘 true)
    fn tail_may_match(&self, tail_lit: Option<u32>, pos: usize) -> bool {
        let Some(p) = tail_lit else {
            return true;
        };
        self.text[pos..]
            .chars()
            .next()
            .is_some_and(|c| literal(p, c, self.prog.ignore_case))
    }

    // RepeatOne(pc) 를 시작한다: 최소 횟수를 먹고, 탐욕이면 끝까지 먹은 뒤 돌려주며, 게으르면 최소에서 뒤를 해 본다
    fn repeat_one(&mut self, pc: usize, pos: usize) -> Option<usize> {
        let Inst::RepeatOne(i) = self.prog.insts[pc] else {
            unreachable!("RepeatOne at pc");
        };
        let info = self.prog.repeats[i];
        let mut cur = pos;
        for _ in 0..info.min {
            cur = self.one(info.item, cur)?;
        }
        if !info.greedy {
            return self.lazy_from(pc, cur, info.min);
        }

        // 탐욕: 상한까지 먹는다. 끝이 없으면 같은 줄을 다시 세지 않는다
        let floor = cur;
        let end = if info.max == u32::MAX {
            let (start, end) = self.runs[i];
            if (start..=end).contains(&floor) {
                end
            } else {
                let end = self.scan(i, floor, u32::MAX);
                self.runs[i] = (floor, end);
                end
            }
        } else {
            self.scan(i, floor, info.max - info.min)
        };
        self.give_back(pc, floor, end)
    }

    // RepeatOne i 의 글자를 from 부터 limit 개까지 먹은 끝. ASCII 는 바이트 표로 센다
    fn scan(&self, i: usize, from: usize, limit: u32) -> usize {
        let info = &self.prog.repeats[i];
        let bytes = self.text.as_bytes();
        let (mut cur, mut count) = (from, 0);
        while count < limit {
            match bytes.get(cur) {
                None => break,

                // ASCII 는 표로, 나머지는 글자를 풀어 본다
                Some(&b) if b < 128 => {
                    if info.ascii & (1 << b) == 0 {
                        break;
                    }
                    cur += 1;
                }
                Some(_) => match self.one(info.item, cur) {
                    Some(next) => cur = next,
                    None => break,
                },
            }
            count += 1;
        }
        cur
    }

    // 탐욕 RepeatOne 이 cur 에서 뒤를 해 볼 자리. 뒤의 글자가 없는 자리는 돌려주며 건너뛴다. 더 돌려줄 수 있으면 갈림길을 쌓는다
    fn give_back(&mut self, pc: usize, floor: usize, cur: usize) -> Option<usize> {
        let Inst::RepeatOne(i) = self.prog.insts[pc] else {
            unreachable!("RepeatOne at pc");
        };
        let info = &self.prog.repeats[i];
        let tail_lit = info.tail_lit;

        // 되풀이 글자가 뒤 글자일 수 없으면 먹은 끝에서만 해 본다(처음 부를 때만 오고 갈림길을 쌓지 않는다)
        if info.disjoint_tail {
            return self.tail_may_match(tail_lit, cur).then_some(cur);
        }

        // 뒤 글자가 있는 자리까지 돌려준다. ASCII 글자는 바이트로 찾는다(ASCII 바이트는 늘 글자 경계다)
        let mut cur = cur;
        match tail_lit {
            Some(p) if p < 128 && !self.prog.ignore_case => {
                let bytes = self.text.as_bytes();
                let hi = (cur + 1).min(bytes.len());
                cur = floor
                    + bytes
                        .get(floor..hi)?
                        .iter()
                        .rposition(|&b| u32::from(b) == p)?;
            }
            _ => {
                while !self.tail_may_match(tail_lit, cur) {
                    if cur == floor {
                        return None;
                    }
                    cur = prev_char(self.text, cur);
                }
            }
        }

        // 더 돌려줄 수 있으면 다음 시도
        if cur > floor {
            self.stack.push(Frame::Greedy { pc, floor, cur });
        }
        Some(cur)
    }

    // 게으른 RepeatOne 이 cur(count 번 먹음)에서 뒤를 해 볼 자리. 뒤의 글자가 없는 자리는 더 먹으며 건너뛴다
    fn lazy_from(&mut self, pc: usize, cur: usize, count: u32) -> Option<usize> {
        let Inst::RepeatOne(i) = self.prog.insts[pc] else {
            unreachable!("RepeatOne at pc");
        };
        let info = self.prog.repeats[i];
        let (mut cur, mut count) = (cur, count);
        while !self.tail_may_match(info.tail_lit, cur) {
            if count >= info.max {
                return None;
            }
            cur = self.one(info.item, cur)?;
            count += 1;
        }
        self.stack.push(Frame::Lazy { pc, cur, count });
        Some(cur)
    }

    // 게으른 RepeatOne 이 뒤에 실패했다: 하나 더 먹는다
    fn take_more(&mut self, pc: usize, cur: usize, count: u32) -> Option<usize> {
        let Inst::RepeatOne(i) = self.prog.insts[pc] else {
            unreachable!("RepeatOne at pc");
        };
        let info = self.prog.repeats[i];
        if count >= info.max {
            return None;
        }
        let next = self.one(info.item, cur)?;
        self.lazy_from(pc, next, count + 1)
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
            // 빈 바퀴: 되풀이를 끝내고 뒤로(그 바퀴가 잡은 칸은 남는다)
            Inst::Progress(mark, exit) if self.marks[mark] == pos => Step::Next(exit, pos),
            Inst::Progress(..) => Step::Next(pc + 1, pos),
            Inst::RepeatOne(_) => match self.repeat_one(pc, pos) {
                Some(next) => Step::Next(pc + 1, next),
                None => Step::Fail,
            },

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
            // python 3.14 부터 빈 글에도 맞는다(늘 `\b` 의 반대)
            At::NotBoundary => self.word_before(pos) == self.word_after(pos),
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
            self.unwind(base);
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
        kept.retain(|f| matches!(f, Frame::Slot { .. } | Frame::Mark { .. }));
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

// pos 바로 앞 글자의 시작(맨 앞이면 0)
fn prev_char(text: &str, pos: usize) -> usize {
    pos - text[..pos].chars().next_back().map_or(0, char::len_utf8)
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
