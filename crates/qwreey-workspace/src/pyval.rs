//! 훅 입력 값을 python 처럼 글로: `str(v)`, `str(v or "")`.
//!
//! Claude Code 는 문자열만 주지만 python 판은 어떤 JSON 값이든 `str()` 로 바꿔 쓴다(경로, session_id). 목록과 dict 의
//! `str()` 은 repr 이라 글의 따옴표와 escape 가 python 과 같아야 한다([`harness_hook::py::repr::str_value`]).

use harness_hook::py::repr::str_value;
use harness_hook::py::value::Value;

/// python `str(v)`.
pub fn py_str(v: &Value) -> String {
    str_value(v)
}

/// python `str(v or "")`: 거짓 값은 빈 글.
pub fn truthy_text(v: Option<&Value>) -> String {
    match v {
        Some(v) if v.truthy() => py_str(v),
        _ => String::new(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use harness_hook::py::json_load::loads;

    /// 목록과 dict 는 python repr, 글은 그대로, 거짓 값은 빈 글이다.
    #[test]
    fn str_like_python() {
        let v = loads(r#"[1, 2.5, "a'b", {"k": null}, true, []]"#).unwrap();
        assert_eq!(py_str(&v), r#"[1, 2.5, "a'b", {'k': None}, True, []]"#);
        assert_eq!(py_str(&Value::Str("x/y".into())), "x/y");
        assert_eq!(truthy_text(Some(&Value::Int(0))), "");
        assert_eq!(truthy_text(Some(&Value::Float(1e20))), "1e+20");

        // Non-ASCII chars inside a list keep their python repr
        let odd = loads(r#"["\u00e9\u00a0"]"#).unwrap();
        assert_eq!(py_str(&odd), "['\u{e9}\\xa0']");
    }
}
