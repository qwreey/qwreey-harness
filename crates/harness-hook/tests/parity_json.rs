//! JSON 읽기와 쓰기(py::json_load, py::json::dumps)를 python `json.loads`, `json.dumps` 와 바이트로 대조한다.
//!
//! 훅 stdin(surrogateescape)과 python 이 쓴 상태 파일(strict UTF-8) 두 갈래로 같은 입력을 읽고, 읽은 값을 python 의 세 꼴
//! (`json.dumps(v)`, `ensure_ascii=False`, `ensure_ascii=False, indent=1`)로 써서 견준다. 읽지 못하면 양쪽 모두 오류여야 한다.
//! 깊은 중첩은 indent 꼴을 빼고 견준다(5000 단계면 들여쓰기만 수십 MB 이고, 쓰는 길은 얕은 입력과 같다).

mod common;

use common::{case, python};
use harness_hook::py::json::{EnsureAscii, dumps};
use harness_hook::py::json_load::{Decode, from_bytes};
use harness_hook::py::surrogate::unit_of;
use serde_json::{Value, json};

// 서로게이트 자리표는 python 의 surrogatepass 처럼 그 코드의 3 바이트로
fn surrogatepass(text: &str) -> String {
    let mut out = Vec::new();
    for c in text.chars() {
        match unit_of(c) {
            Some(u) => out.extend([
                0xE0 | (u >> 12) as u8,
                0x80 | ((u >> 6) & 0x3F) as u8,
                0x80 | (u & 0x3F) as u8,
            ]),
            None => out.extend_from_slice(c.encode_utf8(&mut [0; 4]).as_bytes()),
        }
    }
    hex(&out)
}

fn hex(bytes: &[u8]) -> String {
    bytes.iter().map(|b| format!("{b:02x}")).collect()
}

// (입력, indent 꼴도 견주나)
fn inputs() -> Vec<(Vec<u8>, bool)> {
    // 깊은 중첩
    let deep = [
        format!("{}{}", "[".repeat(5000), "]".repeat(5000)),
        format!("{}1{}", "{\"a\": ".repeat(5000), "}".repeat(5000)),
        format!(
            "{}{{\"k\": [1, {{}}]}}{}",
            "[{\"x\": ".repeat(2500),
            "}]".repeat(2500)
        ),
    ];
    let mut out: Vec<(Vec<u8>, bool)> = deep.into_iter().map(|t| (t.into_bytes(), false)).collect();

    // 글로 쓸 수 있는 입력
    let texts: Vec<String> = vec![
        // NaN, 무한대, 넘치는 float, float 표기
        "[NaN, Infinity, -Infinity]".into(),
        "1e400".into(),
        "-1e400".into(),
        "1e-400".into(),
        "[1E400, -0.0, -0, 0.1, 1e16, 123456789012345678901234567890.5, 1e99999999999999999999]"
            .into(),
        "[1.5, 100.0, 1e-5, 0.0001, 1e22, 5e-324, 2.5e-7, 1.7976931348623157e308]".into(),
        // 큰 정수
        "1".repeat(39),
        "170141183460469231731687303715884105727".into(),
        "170141183460469231731687303715884105728".into(),
        "-170141183460469231731687303715884105728".into(),
        "-170141183460469231731687303715884105729".into(),
        format!("-{}", "9".repeat(100)),
        format!("[{}]", "1".repeat(4300)),
        format!("[{}]", "1".repeat(4301)),
        format!("{{\"n\": -{}}}", "2".repeat(4300)),
        // 서로게이트 escape
        r#""\ud800""#.into(),
        r#""\udc00\ud800""#.into(),
        r#""😀""#.into(),
        r#"["\ud83d", "\ud83dA", "\\ud800"]"#.into(),
        // 겹친 키, 큰 객체
        r#"{"a": 1, "b": 2, "a": 3}"#.into(),
        format!(
            "{{{}}}",
            (0..40)
                .map(|i| format!("\"k{}\": {i}", i % 25))
                .collect::<Vec<_>>()
                .join(", ")
        ),
        // 공백, 글
        "\r\n {\"a\" : [ 1 ,2 ] }\r\n".into(),
        r#"{"a": "é\u007f\u001f\t\/\"\\", "b": "한글 ok"}"#.into(),
        "\"\u{2028}\u{7f}\u{1f600}\"".into(),
        // 오류
        String::new(),
        "  ".into(),
        "[1,]".into(),
        "{\"a\": 1,}".into(),
        "[01]".into(),
        "1.".into(),
        r#""\u+123""#.into(),
        "\"a\tb\"".into(),
        "\"a\rb\"".into(),
        "nan".into(),
        "-NaN".into(),
        "{1: 2}".into(),
        "[1] x".into(),
        "\u{feff}{}".into(),
    ];
    out.extend(texts.into_iter().map(|t| (t.into_bytes(), true)));

    // UTF-8 이 아닌 바이트: 글 안, 글 밖, 인코딩된 서로게이트, 잘린 글자
    let bytes: [&[u8]; 6] = [
        b"{\"a\": \"x\xffy\"}",
        b"{\"a\": \"\xed\xa0\x80\"}",
        b"[\"\xf0\x9f\x98\"]",
        b"[\"\xc3\", \"caf\xe9\"]",
        b"[1, \xff]",
        b"{\"\xfe\": 1}",
    ];
    out.extend(bytes.iter().map(|b| (b.to_vec(), true)));
    out
}

#[test]
fn json_matches_python() {
    let inputs = inputs();
    let sent: Vec<Value> = inputs
        .iter()
        .map(|(b, indent)| json!([hex(b), indent]))
        .collect();
    let modes = [("stdin", Decode::SurrogateEscape), ("file", Decode::Strict)];
    let cases: Vec<Value> = modes
        .iter()
        .map(|(mode, _)| case("json", &[], json!({"inputs": sent, "mode": mode})))
        .collect();
    let Some(got) = python(&cases) else {
        return;
    };

    // 같은 입력을 Rust 로 읽고 써서 견준다
    for ((mode, decode), results) in modes.iter().zip(&got) {
        for (i, ((raw, indent), want)) in inputs
            .iter()
            .zip(results.as_array().expect("list"))
            .enumerate()
        {
            let rust = match from_bytes(raw, *decode) {
                Ok(v) => {
                    let mut forms = vec![
                        dumps(&v, EnsureAscii::Yes, None),
                        dumps(&v, EnsureAscii::No, None),
                    ];
                    if *indent {
                        forms.push(dumps(&v, EnsureAscii::No, Some(1)));
                    }
                    json!({"dumps": forms.iter().map(|f| surrogatepass(f)).collect::<Vec<_>>()})
                }
                Err(_) => json!("error"),
            };

            // python 의 오류 종류(JSONDecodeError, UnicodeDecodeError, ValueError)는 가리지 않는다
            let python = match want.get("error") {
                Some(_) => json!("error"),
                None => want.clone(),
            };
            let shown: String = String::from_utf8_lossy(raw).chars().take(80).collect();
            assert_eq!(rust, python, "{mode} input {i}: {shown:?}");
        }
    }
}
