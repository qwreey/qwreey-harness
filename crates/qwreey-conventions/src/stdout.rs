//! 훅 출력 글을 python 이 stdout 에 쓰는 바이트로(`python3 -X utf8` 의 stdout 은 surrogateescape 다).
//!
//! python 훅은 `json.dump(out, sys.stdout, ensure_ascii=False)` 로 값마다 조각을 쓴다. 그래서
//! - U+DC80..U+DCFF 서로게이트(UTF-8 이 아닌 파일 이름의 바이트)는 그 바이트 하나로 나가고,
//! - 다른 서로게이트(JSON 의 `"\ud800"` 같은 escape)는 그 글 조각을 인코딩하다 UnicodeEncodeError 로 끝나
//!   그 글의 여는 따옴표 앞까지만 나간다(종료 코드 1).
//!
//! 이 판의 글은 서로게이트를 [`harness_hook::py::surrogate`] 의 자리표로 들고 있으므로 여기서 되돌린다.

use harness_hook::py::surrogate::unit_of;

/// python 이 쓰는 바이트와, 끝까지 썼는가(거짓이면 python 은 그 자리에서 예외로 끝난다).
pub fn python_bytes(out: &str) -> (Vec<u8>, bool) {
    let mut bytes = Vec::with_capacity(out.len());
    let mut in_string = false;
    let mut escaped = false;
    let mut string_start = 0;

    for c in out.chars() {
        // Track the JSON string the character sits in
        if in_string {
            if escaped {
                escaped = false;
            } else if c == '\\' {
                escaped = true;
            } else if c == '"' {
                in_string = false;
            }
        } else if c == '"' {
            in_string = true;
            string_start = bytes.len();
        }

        // Placeholders go back to python's bytes
        match unit_of(c) {
            Some(unit @ 0xDC80..=0xDCFF) => bytes.push((unit - 0xDC00) as u8),
            Some(_) => {
                bytes.truncate(string_start);
                return (bytes, false);
            }
            None => bytes.extend_from_slice(c.encode_utf8(&mut [0; 4]).as_bytes()),
        }
    }
    (bytes, true)
}

#[cfg(test)]
mod tests {
    use super::*;
    use harness_hook::py::surrogate::placeholder;

    /// 파일 이름의 바이트 서로게이트는 그 바이트로, 다른 서로게이트는 그 글 앞에서 멈춘다.
    #[test]
    fn writes_like_python_surrogateescape() {
        let low = placeholder(0xDC80).unwrap();
        let high = placeholder(0xD800).unwrap();

        // A byte surrogate becomes the raw byte, the rest stays UTF-8
        let (bytes, ok) = python_bytes(&format!(r#"{{"a": "x{low}—"}}"#));
        assert!(ok);
        assert_eq!(bytes, b"{\"a\": \"x\x80\xe2\x80\x94\"}");

        // A high surrogate cuts the output before its string
        // (json.dump 의 그 조각이 인코딩에서 실패한다)
        let out = format!(
            r#"{{"hookSpecificOutput": {{"hookEventName": "PostToolUse", "additionalContext": "a \"q\" {high}"}}}}"#
        );
        let (bytes, ok) = python_bytes(&out);
        assert!(!ok);
        assert_eq!(
            bytes,
            br#"{"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "#
        );

        // Plain text unchanged
        assert_eq!(
            python_bytes("{\"k\": \"한\"}"),
            ("{\"k\": \"한\"}".as_bytes().to_vec(), true)
        );
    }
}
