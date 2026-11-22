//! TOML 의 날짜, 시각, 수(python `tomllib._re` 의 RE_DATETIME, RE_LOCALTIME, RE_NUMBER 와 그 값 바꾸기).
//!
//! 정규식 대신 자리마다 글자를 본다. 고를 갈래가 정규식과 같은 순서다(빠진 꼬리 갈래는 일치에서 빠진다).

use super::{Item, MAX_INT_DIGITS, Parsed, TomlError};

// 자리 pos 에서 ASCII 숫자 n 개를 읽는다
fn digits_at(src: &[char], pos: usize, n: usize) -> Option<u32> {
    let mut value = 0;
    for i in 0..n {
        let d = src
            .get(pos + i)?
            .to_digit(10)
            .filter(|_| src[pos + i].is_ascii_digit())?;
        value = value * 10 + d;
    }
    Some(value)
}

// python RE_LOCALTIME 의 일치 끝: HH:MM:SS(.소수)?
pub(super) fn time_at(src: &[char], pos: usize) -> Option<usize> {
    let hour = digits_at(src, pos, 2)?;
    let minute = digits_at(src, pos + 3, 2)?;
    let second = digits_at(src, pos + 6, 2)?;
    let colons = src.get(pos + 2) == Some(&':') && src.get(pos + 5) == Some(&':');
    if !colons || hour > 23 || minute > 59 || second > 59 {
        return None;
    }

    // An optional fraction needs one digit after the dot
    let mut end = pos + 8;
    if src.get(end) == Some(&'.') && src.get(end + 1).is_some_and(char::is_ascii_digit) {
        end += 1;
        while src.get(end).is_some_and(char::is_ascii_digit) {
            end += 1;
        }
    }
    Some(end)
}

// python RE_DATETIME 의 일치 끝과 match_to_datetime 의 검사. 꼴이 맞는데 없는 날짜면 거절한다
pub(super) fn datetime_at(src: &[char], pos: usize) -> Parsed<Option<usize>> {
    let date = (|| {
        let year = digits_at(src, pos, 4)?;
        let month = digits_at(src, pos + 5, 2)?;
        let day = digits_at(src, pos + 8, 2)?;
        let dashes = src.get(pos + 4) == Some(&'-') && src.get(pos + 7) == Some(&'-');
        (dashes && (1..=12).contains(&month) && (1..=31).contains(&day))
            .then_some((year, month, day))
    })();
    let Some((year, month, day)) = date else {
        return Ok(None);
    };
    if year < 1 || day > days_in_month(year, month) {
        return Err(TomlError);
    }

    // An optional time and offset after T, t or a space
    let mut end = pos + 10;
    if src.get(end).is_some_and(|c| matches!(c, 'T' | 't' | ' '))
        && let Some(time_end) = time_at(src, end + 1)
    {
        end = time_end;
        if src.get(end).is_some_and(|c| matches!(c, 'Z' | 'z')) {
            end += 1;
        } else if src.get(end).is_some_and(|c| matches!(c, '+' | '-'))
            && let (Some(h), Some(m)) = (digits_at(src, end + 1, 2), digits_at(src, end + 4, 2))
            && src.get(end + 3) == Some(&':')
            && h <= 23
            && m <= 59
        {
            end += 6;
        }
    }
    Ok(Some(end))
}

fn days_in_month(year: u32, month: u32) -> u32 {
    let leap = year % 4 == 0 && (year % 100 != 0 || year % 400 == 0);
    match month {
        2 if leap => 29,
        2 => 28,
        4 | 6 | 9 | 11 => 30,
        _ => 31,
    }
}

// (?:_?D)* 를 pos 부터: 끝 자리
fn digit_run(src: &[char], mut pos: usize, is_digit: fn(char) -> bool) -> usize {
    loop {
        match src.get(pos) {
            Some(&c) if is_digit(c) => pos += 1,
            Some('_') if src.get(pos + 1).is_some_and(|&c| is_digit(c)) => pos += 2,
            _ => return pos,
        }
    }
}

// python RE_NUMBER 의 일치와 match_to_number. 꼴이 아니면 None, int() 가 받지 않으면(4300 자리 넘는 10진) 거절
pub(super) fn number_at(src: &[char], pos: usize) -> Parsed<Option<(usize, Item)>> {
    // Hex, binary, octal
    let radix: Option<(u32, fn(char) -> bool)> = match (src.get(pos), src.get(pos + 1)) {
        (Some('0'), Some('x')) => Some((16, |c| c.is_ascii_hexdigit())),
        (Some('0'), Some('b')) => Some((2, |c| matches!(c, '0' | '1'))),
        (Some('0'), Some('o')) => Some((8, |c| matches!(c, '0'..='7'))),
        _ => None,
    };
    if let Some((radix, is_digit)) = radix
        && src.get(pos + 2).is_some_and(|&c| is_digit(c))
    {
        let end = digit_run(src, pos + 3, is_digit);
        let body: String = src[pos + 2..end].iter().filter(|&&c| c != '_').collect();
        let value = match i128::from_str_radix(&body, radix) {
            Ok(v) => Item::Int(v),
            Err(_) => Item::BigInt(src[pos..end].iter().filter(|&&c| c != '_').collect()),
        };
        return Ok(Some((end, value)));
    }

    // Decimal integer part
    let mut end = pos;
    if src.get(end).is_some_and(|c| matches!(c, '+' | '-')) {
        end += 1;
    }
    match src.get(end) {
        Some('0') => end += 1,
        Some(c) if matches!(c, '1'..='9') => end = digit_run(src, end + 1, |c| c.is_ascii_digit()),
        _ => return Ok(None),
    }

    // Optional fraction and exponent
    let int_end = end;
    if src.get(end) == Some(&'.') && src.get(end + 1).is_some_and(char::is_ascii_digit) {
        end = digit_run(src, end + 2, |c| c.is_ascii_digit());
    }
    if src.get(end).is_some_and(|c| matches!(c, 'e' | 'E')) {
        let mut e = end + 1;
        if src.get(e).is_some_and(|c| matches!(c, '+' | '-')) {
            e += 1;
        }
        if src.get(e).is_some_and(char::is_ascii_digit) {
            end = digit_run(src, e + 1, |c| c.is_ascii_digit());
        }
    }

    // Float or int, like python float() and int(text, 0)
    let text: String = src[pos..end].iter().filter(|&&c| c != '_').collect();
    if end > int_end {
        let value = text.parse::<f64>().map_err(|_| TomlError)?;
        return Ok(Some((end, Item::Float(value))));
    }
    if text.chars().filter(char::is_ascii_digit).count() > MAX_INT_DIGITS {
        return Err(TomlError);
    }
    let value = match text.parse::<i128>() {
        Ok(v) => Item::Int(v),
        Err(_) => Item::BigInt(text),
    };
    Ok(Some((end, value)))
}
