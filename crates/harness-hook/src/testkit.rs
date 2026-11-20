//! 플러그인 crate 의 시험이 같이 쓰는 것: 결정적 의사 난수, 조각을 이어 만든 글, 고정 패턴과 py::re 의 대조.
//!
//! 시험 코드끼리는 `#[cfg(test)]` 를 crate 너머로 나눌 수 없어 여기 둔다. 훅 바이너리는 부르지 않으므로 링크에서 빠진다.

use crate::rx;

/// 결정적 의사 난수(xorshift64). 같은 `seed` 면 같은 수열이다.
pub fn xorshift(mut seed: u64) -> impl FnMut() -> u64 {
    move || {
        seed ^= seed << 13;
        seed ^= seed >> 7;
        seed ^= seed << 17;
        seed
    }
}

/// `pieces` 를 이어 붙인 글 `n` 개(결정적 의사 난수, 한 글에 1..12 조각).
pub fn corpus(pieces: &[&str], n: usize) -> Vec<String> {
    let mut next = xorshift(0x2545_f491_4f6c_dd1d);
    (0..n)
        .map(|_| {
            let count = (next() % 12) as usize + 1;
            (0..count)
                .map(|_| pieces[(next() % pieces.len() as u64) as usize])
                .collect()
        })
        .collect()
}

/// 이름 붙인 패턴마다 [`corpus`] 의 글 3000 개에서 [`rx::Regex::agrees_with_py`] 인지 본다. 어긋나면 이름과 글로 멈춘다.
pub fn assert_agree(patterns: &[(&str, &rx::Regex)], pieces: &[&str]) {
    for (_, re) in patterns {
        re.check();
    }
    for text in corpus(pieces, 3000) {
        for (name, re) in patterns {
            assert!(
                re.agrees_with_py(&text),
                "{name} differs from python on {text:?}"
            );
        }
    }
}
