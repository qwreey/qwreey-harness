//! python 의 float 표기(`repr`, `str(int(x))`)와 float 몫(`//`).

/// python `repr(x)`(= `str(x)`)와 같은 float 표기.
///
/// 숫자열은 왕복하는 가장 짧은 것 가운데 참값에 가장 가까운 것이고, 소수점 위치가 -4 이하이거나 16 을 넘으면
/// 지수 꼴(`1e-05`, `1.5e+16`), 아니면 고정 꼴에 소수부가 없으면 `.0` 을 붙인다.
pub fn float_repr(x: f64) -> String {
    // 유한하지 않은 값과 0
    if x.is_nan() {
        return "nan".to_owned();
    }
    if x.is_infinite() {
        return if x > 0.0 { "inf" } else { "-inf" }.to_owned();
    }
    let sign = if x.is_sign_negative() { "-" } else { "" };
    if x == 0.0 {
        return format!("{sign}0.0");
    }

    // 가장 짧은 숫자열과 소수점 위치
    let sci = shortest_closest(x.abs());
    let (mantissa, exp) = sci.split_once('e').expect("{:e} always writes an exponent");
    let digits: String = mantissa.chars().filter(|c| *c != '.').collect();
    let exp: i32 = exp.parse().expect("{:e} writes an integer exponent");
    let point = exp + 1;

    // 지수 꼴
    if point <= -4 || point > 16 {
        let (head, tail) = digits.split_at(1);
        let frac = if tail.is_empty() {
            String::new()
        } else {
            format!(".{tail}")
        };
        let exp_sign = if exp < 0 { '-' } else { '+' };
        return format!("{sign}{head}{frac}e{exp_sign}{:02}", exp.abs());
    }

    // 고정 꼴
    let len = digits.len() as i32;
    let body = if point <= 0 {
        format!("0.{}{digits}", "0".repeat((-point) as usize))
    } else if point >= len {
        format!("{digits}{}.0", "0".repeat((point - len) as usize))
    } else {
        let (int, frac) = digits.split_at(point as usize);
        format!("{int}.{frac}")
    };
    format!("{sign}{body}")
}

// Rust 의 `{:e}` 는 같은 길이의 후보가 참값에서 똑같이 떨어져 있으면 python(짝수 쪽)과 다른 쪽을 고를 수 있다
// (1e15 + 0.3 은 python 1000000000000000.2, `{:e}` 는 ...3). 같은 자릿수로 올바르게 반올림한 값이 왕복하면 그것을 쓴다.
// 2 의 거듭제곱 바로 위처럼 아래쪽 간격이 좁은 곳에서는 반올림한 값이 왕복하지 않을 수 있어 그때는 `{:e}` 그대로다.
fn shortest_closest(x: f64) -> String {
    let shortest = format!("{x:e}");
    let digits = shortest
        .split('e')
        .next()
        .map_or(1, |m| m.chars().filter(char::is_ascii_digit).count());
    let rounded = format!("{x:.prec$e}", prec = digits - 1);
    if rounded.parse::<f64>() == Ok(x) {
        rounded
    } else {
        shortest
    }
}

/// python `str(int(x))`: 정수 값인 유한 float 의 정확한 십진 표기.
///
/// 2^53 이상은 float 가 가리키는 정수를 그대로 쓴다(`1e20` 은 `100000000000000000000`).
pub fn integral_float_text(x: f64) -> String {
    debug_assert!(x.is_finite() && x.fract() == 0.0);
    if x.abs() < 9_007_199_254_740_992.0 {
        return format!("{}", x as i64);
    }

    // 값이 2^53 이상이라 mantissa * 2^shift 의 shift 가 0 이상이다
    let bits = x.abs().to_bits();
    let exponent = ((bits >> 52) & 0x7ff) as i32;
    let mantissa = (bits & ((1u64 << 52) - 1)) | (1u64 << 52);
    let shift = exponent - 1075;

    // 십진 숫자(낮은 자리부터)를 shift 번 두 배로
    let mut digits: Vec<u8> = mantissa
        .to_string()
        .bytes()
        .rev()
        .map(|b| b - b'0')
        .collect();
    for _ in 0..shift {
        let mut carry = 0;
        for d in digits.iter_mut() {
            let v = *d * 2 + carry;
            *d = v % 10;
            carry = v / 10;
        }
        if carry > 0 {
            digits.push(carry);
        }
    }

    let sign = if x < 0.0 { "-" } else { "" };
    let text: String = digits.iter().rev().map(|d| char::from(b'0' + d)).collect();
    format!("{sign}{text}")
}

/// python 의 float 몫 `a // b`(내림, `divmod` 와 같은 계산). `a / b` 를 내림하면 경계에서 1 이 틀릴 수 있다.
pub fn floor_div(a: f64, b: f64) -> f64 {
    // CPython float_floor_div 를 따른다. 나머지는 몫을 고칠 때만 쓴다
    let rem = a % b;
    let mut div = (a - rem) / b;
    if rem != 0.0 && ((b < 0.0) != (rem < 0.0)) {
        div -= 1.0;
    }

    if div == 0.0 {
        return 0.0_f64.copysign(a / b);
    }
    let mut floor = div.floor();
    if div - floor > 0.5 {
        floor += 1.0;
    }
    floor
}

/// python `float(text)`. 읽지 못하면 `None`(python 은 ValueError).
///
/// 앞뒤 공백을 떼고, Unicode 십진 숫자를 ASCII 로 바꾸고, 숫자 사이의 `_` 를 받는다. `inf`, `infinity`, `nan` 은 대소문자와 부호를 가리지 않는다.
pub fn parse_float(text: &str) -> Option<f64> {
    let text = crate::py::text::strip(text);
    let chars: Vec<char> = text
        .chars()
        .map(|c| match crate::py::unicode::decimal_value(c) {
            Some(d) => char::from_digit(d, 10).expect("decimal digit"),
            None => c,
        })
        .collect();

    // `_` 는 숫자 사이에만
    let mut plain = String::with_capacity(chars.len());
    for (i, &c) in chars.iter().enumerate() {
        if c != '_' {
            plain.push(c);
            continue;
        }
        let digit_at = |j: Option<usize>| {
            j.and_then(|j| chars.get(j))
                .is_some_and(char::is_ascii_digit)
        };
        if !digit_at(i.checked_sub(1)) || !digit_at(Some(i + 1)) {
            return None;
        }
    }

    // Rust 가 python 과 달리 받는 꼴은 없다(둘 다 `1.`, `.5`, `1e5`, `inf`, `nan` 을 받는다)
    plain.parse::<f64>().ok()
}

/// python `"%g" % x`: 유효 숫자 6자리, 지수가 -4 미만이거나 6 이상이면 지수 꼴, 끝의 0 은 뗀다.
pub fn format_g(x: f64) -> String {
    if x.is_nan() {
        return "nan".to_owned();
    }
    if x.is_infinite() {
        return if x > 0.0 { "inf" } else { "-inf" }.to_owned();
    }

    // 6자리로 반올림한 지수
    let sci = format!("{x:.5e}");
    let (mantissa, exp) = sci.split_once('e').expect("{:e} writes an exponent");
    let exp: i32 = exp.parse().expect("{:e} writes an integer exponent");

    let trim = |s: &str| -> String {
        if s.contains('.') {
            s.trim_end_matches('0').trim_end_matches('.').to_owned()
        } else {
            s.to_owned()
        }
    };
    if !(-4..6).contains(&exp) {
        let sign = if exp < 0 { '-' } else { '+' };
        return format!("{}e{sign}{:02}", trim(mantissa), exp.abs());
    }
    trim(&format!("{x:.prec$}", prec = (5 - exp) as usize))
}

/// python `int(digits)` 의 값. 십진 숫자(Unicode 포함)만 받고, u128 을 넘으면 `None`.
pub fn parse_decimal(digits: &str) -> Option<u128> {
    if digits.is_empty() {
        return None;
    }
    digits.chars().try_fold(0u128, |acc, c| {
        let d = crate::py::unicode::decimal_value(c)?;
        acc.checked_mul(10)?.checked_add(u128::from(d))
    })
}

/// python `int(text)`(base 10). 읽지 못하거나 i128 을 넘으면 `None`(python 은 ValueError, 넘는 값은 python 만 읽는다).
///
/// 앞뒤 공백을 떼고, 부호 하나, Unicode 십진 숫자, 숫자 사이의 `_` 하나를 받는다(`" -1_000 "` 은 -1000).
pub fn parse_int(text: &str) -> Option<i128> {
    let text = crate::py::text::strip(text);
    let (negative, digits) = match text.as_bytes().first() {
        Some(b'-') => (true, &text[1..]),
        Some(b'+') => (false, &text[1..]),
        _ => (false, text),
    };
    if digits.starts_with('_') || digits.ends_with('_') || digits.contains("__") {
        return None;
    }
    let magnitude = parse_decimal(&digits.replace('_', ""))?;
    let value = i128::try_from(magnitude).ok()?;
    Some(if negative { -value } else { value })
}

/// python `int(text)` 을 i128 끝에서 멈춘 값. 읽지 못하면 `None`(python ValueError).
///
/// [`parse_int`] 와 같은 글을 받되 i128 을 넘는 수도 받아 `i128::MAX` 나 `i128::MIN` 으로 준다. 문턱처럼 견주기만 하는 값에 쓴다.
/// python 처럼 숫자가 4300 자를 넘으면 읽지 않는다.
pub fn parse_int_saturating(text: &str) -> Option<i128> {
    if let Some(n) = parse_int(text) {
        return Some(n);
    }

    // The same form as parse_int, only past i128
    let text = crate::py::text::strip(text);
    let (negative, digits) = match text.as_bytes().first() {
        Some(b'-') => (true, &text[1..]),
        Some(b'+') => (false, &text[1..]),
        _ => (false, text),
    };
    let plain = digits.replace('_', "");
    let well_formed = !digits.starts_with('_')
        && !digits.ends_with('_')
        && !digits.contains("__")
        && !plain.is_empty()
        && plain.chars().count() <= crate::py::json_load::MAX_INT_DIGITS
        && plain
            .chars()
            .all(|c| crate::py::unicode::decimal_value(c).is_some());
    well_formed.then_some(if negative { i128::MIN } else { i128::MAX })
}

#[cfg(test)]
mod tests {
    use super::*;

    /// i128 을 넘는 수는 끝 값으로, 틀린 글은 `None` 이다.
    #[test]
    fn saturating_int_parsing() {
        assert_eq!(parse_int_saturating(" 12 "), Some(12));
        assert_eq!(parse_int_saturating(&"9".repeat(60)), Some(i128::MAX));
        assert_eq!(
            parse_int_saturating(&format!("-{}", "9".repeat(60))),
            Some(i128::MIN)
        );
        assert_eq!(parse_int_saturating(&"9".repeat(4301)), None);
        assert_eq!(parse_int_saturating("1.5"), None);
    }

    /// `int()` 처럼 공백, 부호, 밑줄 구분, 다른 문자의 십진 숫자를 받고 나머지는 `None` 이다.
    #[test]
    fn int_parsing_follows_python() {
        assert_eq!(parse_int(" -1_000 "), Some(-1000));
        assert_eq!(parse_int("+7"), Some(7));
        assert_eq!(parse_int("\u{663}\n"), Some(3));
        for bad in ["", "-", "1__0", "_1", "1_", "1.0", "0x1", "- 1"] {
            assert_eq!(parse_int(bad), None, "{bad:?}");
        }
    }

    /// `float()` 처럼 밑줄 구분과 다른 문자의 숫자, `Infinity` 를 받고 나머지는 `None` 이다.
    #[test]
    fn float_parsing_follows_python() {
        assert_eq!(parse_float(" 1_000.5 "), Some(1000.5));
        assert_eq!(parse_float("\u{663}"), Some(3.0));
        assert_eq!(parse_float("1__0"), None);
        assert_eq!(parse_float("_1"), None);
        assert_eq!(parse_float("x"), None);
        assert!(parse_float("-Infinity").is_some_and(|f| f.is_infinite()));
    }

    /// `format_g` 는 python `%g` 처럼 유효숫자 6 자리와 지수 꼴로 쓴다.
    #[test]
    fn g_format_follows_python() {
        for (x, want) in [
            (10.0, "10"),
            (0.001, "0.001"),
            (1e-5, "1e-05"),
            (1234567.0, "1.23457e+06"),
            (0.5, "0.5"),
            (0.0, "0"),
            (100000.0, "100000"),
            (f64::INFINITY, "inf"),
        ] {
            assert_eq!(format_g(x), want, "{x}");
        }
    }

    /// `parse_decimal` 은 다른 문자의 십진 숫자도 읽는다.
    #[test]
    fn decimal_parsing_reads_other_scripts() {
        assert_eq!(parse_decimal("139"), Some(139));
        assert_eq!(parse_decimal("\u{661}\u{663}\u{669}"), Some(139));
    }

    /// `float_repr` 는 python `repr(float)` 처럼 가장 짧게 되돌아오는 글과 지수 꼴을 쓴다.
    #[test]
    fn repr_matches_python_examples() {
        let cases = [
            (1.5, "1.5"),
            (100.0, "100.0"),
            (0.0001, "0.0001"),
            (0.00001, "1e-05"),
            (1e16, "1e+16"),
            (1234567890123456.7, "1234567890123456.8"),
            (-2.5e-7, "-2.5e-07"),
            (1.7976931348623157e308, "1.7976931348623157e+308"),
            (-0.0, "-0.0"),
            (1e15 + 0.3, "1000000000000000.2"),
        ];
        for (x, want) in cases {
            assert_eq!(float_repr(x), want, "{x:e}");
        }
    }

    /// 정수 값 float 는 소수점이나 지수 없이 정확한 자릿수로 쓴다(`-0.0` 은 `0`).
    #[test]
    fn integral_text_is_exact() {
        assert_eq!(integral_float_text(-0.0), "0");
        assert_eq!(integral_float_text(1e20), "100000000000000000000");
        assert_eq!(integral_float_text(2f64.powi(64)), "18446744073709551616");
    }
}
