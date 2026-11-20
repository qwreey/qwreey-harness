//! 문자 집합과 글자 하나의 비교(IGNORECASE 포함). sre 의 `IN`, `IN_UNI_IGNORE`, `LITERAL_UNI_IGNORE` 자리다.
//!
//! IGNORECASE 에서 python 은 집합의 글자마다 소문자(와 `re._casefix` 짝)를 표에 넣고, 글의 글자를 소문자로 바꿔 표에서 찾는다.
//! 범위도 글자마다 바꿔 넣는다. 그래서 `[A-Z]` 는 U+212A(켈빈, 소문자 k)에도 맞는다.

use super::ast::{Category, Class, ClassItem};
use crate::py::text::is_space;
use crate::py::unicode::{case_fixes, in_ranges, is_decimal, is_word, lower};

/// 맞출 준비를 마친 집합.
#[derive(Clone, Debug)]
pub(super) struct CompiledClass {
    negate: bool,
    ignore_case: bool,
    /// 정렬해 합친 코드 범위. IGNORECASE 면 소문자로 바꾼 값이다.
    ranges: Vec<(u32, u32)>,
    cats: Vec<Category>,
}

impl CompiledClass {
    /// `class` 를 표로 만든다. IGNORECASE 면 범위의 글자마다 소문자를 넣는다(큰 범위는 그만큼 오래 걸린다).
    pub fn new(class: &Class, ignore_case: bool) -> CompiledClass {
        let mut ranges = Vec::new();
        let mut cats = Vec::new();
        for item in &class.items {
            match *item {
                ClassItem::Cat(cat) => cats.push(cat),
                ClassItem::Range(lo, hi) if ignore_case => {
                    for c in lo..=hi {
                        let l = lower(c);
                        ranges.push((l, l));
                        ranges.extend(case_fixes(l).iter().map(|&f| (f, f)));
                    }
                }
                ClassItem::Range(lo, hi) => ranges.push((lo, hi)),
            }
        }
        CompiledClass {
            negate: class.negate,
            ignore_case,
            ranges: merge(ranges),
            cats,
        }
    }

    /// 글자 `c` 가 집합에 드는가(부정 집합이면 반대).
    pub fn matches(&self, c: char) -> bool {
        let code = if self.ignore_case {
            lower(u32::from(c))
        } else {
            u32::from(c)
        };

        let inside =
            in_ranges(&self.ranges, code) || self.cats.iter().any(|&cat| category(cat, code));
        inside != self.negate
    }
}

/// 패턴 글자 `p` 가 글 글자 `c` 에 맞는가. IGNORECASE 면 소문자와 `re._casefix` 짝으로 견준다.
pub(super) fn literal(p: u32, c: char, ignore_case: bool) -> bool {
    if !ignore_case {
        return p == u32::from(c);
    }
    let lo = lower(p);
    let got = lower(u32::from(c));
    got == lo || case_fixes(lo).contains(&got)
}

fn category(cat: Category, code: u32) -> bool {
    let space = || char::from_u32(code).is_some_and(is_space);
    match cat {
        Category::Digit => is_decimal(code),
        Category::NotDigit => !is_decimal(code),
        Category::Word => is_word(code),
        Category::NotWord => !is_word(code),
        Category::Space => space(),
        Category::NotSpace => !space(),
    }
}

// 겹치거나 붙은 범위를 합친다
fn merge(mut ranges: Vec<(u32, u32)>) -> Vec<(u32, u32)> {
    ranges.sort_unstable();
    let mut out: Vec<(u32, u32)> = Vec::with_capacity(ranges.len());
    for (lo, hi) in ranges {
        match out.last_mut() {
            Some(last) if lo <= last.1.saturating_add(1) => last.1 = last.1.max(hi),
            _ => out.push((lo, hi)),
        }
    }
    out
}
