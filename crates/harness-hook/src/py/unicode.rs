//! python 의 문자 분류(정규식 `\w`, `\d`, `str.isalnum`, `str.isdecimal`)와 정규식 IGNORECASE 의 대소문자 접기.
//!
//! why not `char::is_alphanumeric`: Rust 는 Unicode Alphabetic(모음 기호 같은 결합 문자 포함)을 보고 python 은
//! 일반 범주 L*, N* 만 본다(273 범위가 다르다). 그래서 분류는 python 이 만든 표(`unicode_tables.rs`)로 본다.
//! 대소문자는 Rust 의 매핑을 쓴다. 그 매핑의 Unicode 판이 python 보다 새로우면 새로 생긴 문자만 다르다.

use super::unicode_tables::{CASE_FIXES, DECIMAL, WORD};

/// `c` 가 정렬된 겹치지 않는 범위 목록 `table` 안에 있는가.
pub(crate) fn in_ranges(table: &[(u32, u32)], c: u32) -> bool {
    table
        .binary_search_by(|&(lo, hi)| {
            if hi < c {
                std::cmp::Ordering::Less
            } else if lo > c {
                std::cmp::Ordering::Greater
            } else {
                std::cmp::Ordering::Equal
            }
        })
        .is_ok()
}

/// 정규식 `\w`(python `c.isalnum() or c == "_"`). 코드 포인트로 받는다(서로게이트는 아니다).
pub fn is_word(c: u32) -> bool {
    in_ranges(WORD, c)
}

/// python `str.isalnum()`(한 글자).
pub fn is_alnum(c: char) -> bool {
    c != '_' && is_word(u32::from(c))
}

/// 정규식 `\d`(python `str.isdecimal()`).
pub fn is_decimal(c: u32) -> bool {
    in_ranges(DECIMAL, c)
}

/// 십진 숫자의 값(python `int("٣")` 의 한 자리). 십진 숫자가 아니면 `None`.
///
/// 표의 범위는 모두 0 부터 열 개씩 이어진 묶음이다(생성기가 python 에서 확인한 성질).
pub fn decimal_value(c: char) -> Option<u32> {
    let code = u32::from(c);
    let i = DECIMAL.partition_point(|&(_, hi)| hi < code);
    let &(lo, hi) = DECIMAL.get(i)?;
    (lo <= code && code <= hi).then(|| (code - lo) % 10)
}

/// 정규식 IGNORECASE 가 견주는 소문자(sre `unicode_tolower`, 한 글자 매핑). 문자가 아닌 코드(서로게이트)는 그대로.
pub fn lower(c: u32) -> u32 {
    // 전체 매핑이 두 글자인 것은 U+0130 하나다. 한 글자 매핑은 i
    if c == 0x130 {
        return u32::from('i');
    }
    let Some(ch) = char::from_u32(c) else {
        return c;
    };
    let mut it = ch.to_lowercase();
    match (it.next(), it.next()) {
        (Some(one), None) => u32::from(one),
        _ => c,
    }
}

/// IGNORECASE 에서 소문자 `lo` 와 같게 보는 다른 소문자들(`re._casefix`, 예: `s` 와 U+017F).
pub fn case_fixes(lo: u32) -> &'static [u32] {
    CASE_FIXES
        .binary_search_by_key(&lo, |&(k, _)| k)
        .map_or(&[], |i| CASE_FIXES[i].1)
}

#[cfg(test)]
mod tests {
    use super::*;

    /// 낱말 글자 판정은 밑줄과 한글을 받고, Rust 에서 alphabetic 인 U+0903 은 python `\w` 가 아니라 뺀다.
    #[test]
    fn word_class_follows_python() {
        assert!(is_word(u32::from('_')) && is_word(u32::from('\u{d55c}')));
        assert!(
            !is_word(0x903) && '\u{903}'.is_alphabetic(),
            "U+0903 is alphabetic in Rust but not \\w in python"
        );
    }

    /// 십진 숫자 판정은 다른 문자의 숫자를 받고 위 첨자 숫자는 뺀다.
    #[test]
    fn decimal_class_follows_python() {
        assert!(is_decimal(0x663) && !is_decimal(u32::from('\u{b2}')));
    }

    /// `lower` 는 점 있는 `I`(U+0130)를 `i` 로 내린다.
    #[test]
    fn lower_maps_dotted_capital_i_to_i() {
        assert_eq!(lower(0x130), 0x69);
    }

    /// IGNORECASE 가 `s` 와 같게 보는 `ſ`(U+017F) 는 `case_fixes` 에 있고, `a` 에는 없다.
    #[test]
    fn case_fixes_lists_extra_ignorecase_pairs() {
        assert_eq!(case_fixes(u32::from('s')), &[0x17f]);
        assert!(case_fixes(u32::from('a')).is_empty());
    }
}
