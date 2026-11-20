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

#[cfg(test)]
mod tests {
    use super::*;

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

    #[test]
    fn integral_text_is_exact() {
        assert_eq!(integral_float_text(-0.0), "0");
        assert_eq!(integral_float_text(1e20), "100000000000000000000");
        assert_eq!(integral_float_text(2f64.powi(64)), "18446744073709551616");
    }
}
