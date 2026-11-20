//! python str 의 짝 없는 서로게이트(U+D800..U+DFFF)를 Rust `String` 에 담는 자리표.
//!
//! python 글은 짝 없는 서로게이트를 가질 수 있고 Rust `str` 은 못 가진다. 그런 글은 두 곳에서 온다:
//! JSON 의 `"\ud800"` 같은 escape(`json.load` 는 받고 serde_json 은 거절한다), 그리고 UTF-8 이 아닌 파일 이름
//! (python 은 바이트 하나를 U+DC80..U+DCFF 하나로 읽는다, surrogateescape).
//! 여기서는 서로게이트 하나를 U+10F800..U+10FFFF(보조 사용자 영역 B 의 끝 2048 자) 의 글자 하나로 바꿔 담는다.
//!
//! 자리표는 python 의 서로게이트와 같이 py::re 에서 `\w`, `\d`, `\s` 가 아니고 대소문자가 없다. 그래서 판정은 python 과 같다.
//! [`crate::py::json`] 은 자리표를 python `json.dumps` 처럼 `\udcff` 로 쓰고, [`to_os`] 는 파일 이름의 바이트로 되돌린다.
//!
//! python 과 달라지는 곳(모두 출력 글만):
//! - 글에 U+10F800..U+10FFFF 글자가 그대로 있으면(거의 쓰이지 않는 사용자 영역) 그것도 서로게이트로 읽고 쓴다.
//! - `ensure_ascii=False` 출력: python 은 서로게이트를 stdout 에 쓰다 UnicodeEncodeError 로 멈추고, 여기서는 자리표를 UTF-8 로 쓴다.
//! - 패턴이 그 범위를 직접 쓴 문자 집합(`[\U0010f800-\U0010ffff]`, `[\ud800-\udfff]`)은 python 과 다르게 맞는다.

use serde::de::DeserializeOwned;

const FIRST: u32 = 0xD800;
const LAST: u32 = 0xDFFF;
const BASE: u32 = 0x10_F800;

/// 서로게이트 코드 `unit`(U+D800..U+DFFF)의 자리표 글자.
pub fn placeholder(unit: u32) -> Option<char> {
    if !(FIRST..=LAST).contains(&unit) {
        return None;
    }
    char::from_u32(BASE + (unit - FIRST))
}

/// 자리표 글자면 그것이 가리키는 서로게이트 코드.
pub fn unit_of(c: char) -> Option<u32> {
    let code = u32::from(c);
    (code >= BASE).then(|| code - BASE + FIRST)
}

/// 파일 이름 바이트를 python `os.fsdecode` 처럼 글로(UTF-8, surrogateescape).
///
/// UTF-8 이 아닌 바이트 하나는 U+DC80..U+DCFF 의 자리표 하나다.
pub fn decode_os(bytes: &[u8]) -> String {
    let mut out = String::with_capacity(bytes.len());
    for chunk in bytes.utf8_chunks() {
        out.push_str(chunk.valid());
        for &b in chunk.invalid() {
            out.push(placeholder(0xDC00 + u32::from(b)).expect("in the surrogate range"));
        }
    }
    out
}

/// 글을 파일 이름 바이트로(python `os.fsencode`, [`decode_os`] 의 반대).
///
/// U+DC80..U+DCFF 의 자리표는 그 바이트로 간다. 다른 서로게이트 자리표는 python 도 인코딩하지 못해 `None` 이다.
pub fn encode_os(text: &str) -> Option<Vec<u8>> {
    let mut out = Vec::with_capacity(text.len());
    for c in text.chars() {
        match unit_of(c) {
            Some(unit @ 0xDC80..=0xDCFF) => out.push((unit - 0xDC00) as u8),
            Some(_) => return None,
            None => out.extend_from_slice(c.encode_utf8(&mut [0; 4]).as_bytes()),
        }
    }
    Some(out)
}

/// 글 경로를 OS 경로로(python 이 str 경로를 넘길 때와 같은 바이트). python 이 인코딩하지 못하면 `None`.
#[cfg(unix)]
pub fn to_os(text: &str) -> Option<std::path::PathBuf> {
    use std::os::unix::ffi::OsStringExt;
    encode_os(text).map(|b| std::ffi::OsString::from_vec(b).into())
}

/// 글 경로를 OS 경로로. Windows 는 자리표가 없는 글만 그대로 쓴다.
#[cfg(not(unix))]
pub fn to_os(text: &str) -> Option<std::path::PathBuf> {
    text.chars()
        .all(|c| unit_of(c).is_none())
        .then(|| std::path::PathBuf::from(text))
}

/// OS 경로를 python str 처럼(surrogateescape).
#[cfg(unix)]
pub fn from_os(path: &std::ffi::OsStr) -> String {
    use std::os::unix::ffi::OsStrExt;
    decode_os(path.as_bytes())
}

/// OS 경로를 글로. Windows 의 잘못된 UTF-16 은 U+FFFD 다(python 은 서로게이트를 그대로 둔다).
#[cfg(not(unix))]
pub fn from_os(path: &std::ffi::OsStr) -> String {
    path.to_string_lossy().into_owned()
}

/// python `json.loads` 처럼 읽는다: 짝 없는 서로게이트 escape(`"\ud800"`)도 받는다.
///
/// 먼저 그대로 읽고, 실패하면 짝 없는 `\uD800`..`\uDFFF` escape 를 자리표 글자의 escape 쌍으로 바꿔 한 번 더 읽는다.
/// escape 된 역슬래시(`\\ud800` 은 글자 그대로의 `\ud800`)는 바꾸지 않는다.
pub fn json_from_slice<T: DeserializeOwned>(bytes: &[u8]) -> serde_json::Result<T> {
    match serde_json::from_slice(bytes) {
        Ok(v) => Ok(v),
        Err(first) => match rewrite_lone_escapes(bytes) {
            Some(fixed) => serde_json::from_slice(&fixed),
            None => Err(first),
        },
    }
}

// 짝 없는 서로게이트 escape 를 자리표의 escape 쌍으로. 바꾼 것이 없으면 None
fn rewrite_lone_escapes(bytes: &[u8]) -> Option<Vec<u8>> {
    let mut out = Vec::with_capacity(bytes.len() + 16);
    let mut changed = false;
    let mut i = 0;
    while i < bytes.len() {
        if bytes[i] != b'\\' {
            out.push(bytes[i]);
            i += 1;
            continue;
        }

        // `\uXXXX` 가 아닌 escape 는 두 바이트 그대로
        let Some(unit) = escape_unit(bytes, i) else {
            out.extend_from_slice(&bytes[i..(i + 2).min(bytes.len())]);
            i += 2;
            continue;
        };

        // 짝이 맞는 쌍과 서로게이트가 아닌 글자는 그대로
        let paired = (0xD800..=0xDBFF).contains(&unit)
            && escape_unit(bytes, i + 6).is_some_and(|low| (0xDC00..=0xDFFF).contains(&low));
        if paired {
            out.extend_from_slice(&bytes[i..i + 12]);
            i += 12;
            continue;
        }
        match placeholder(unit) {
            Some(c) => {
                for u in c.encode_utf16(&mut [0; 2]) {
                    out.extend_from_slice(format!("\\u{u:04x}").as_bytes());
                }
                changed = true;
            }
            None => out.extend_from_slice(&bytes[i..i + 6]),
        }
        i += 6;
    }
    changed.then_some(out)
}

// bytes[i..] 가 `\uXXXX` 면 그 값
fn escape_unit(bytes: &[u8], i: usize) -> Option<u32> {
    let esc = bytes.get(i..i + 6)?;
    if esc[0] != b'\\' || esc[1] != b'u' {
        return None;
    }
    u32::from_str_radix(std::str::from_utf8(&esc[2..]).ok()?, 16).ok()
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::Value;

    #[test]
    fn lone_escapes_become_placeholders() {
        let v: Value = json_from_slice(
            br#"{"a": "x\ud800y", "b": "\udcff", "c": "\ud83d\ude00", "d": "\\ud800"}"#,
        )
        .unwrap();
        assert_eq!(v["a"], format!("x{}y", placeholder(0xD800).unwrap()));
        assert_eq!(
            v["b"]
                .as_str()
                .unwrap()
                .chars()
                .map(unit_of)
                .collect::<Vec<_>>(),
            [Some(0xDCFF)]
        );
        assert_eq!(v["c"], "\u{1f600}");
        assert_eq!(v["d"], "\\ud800");

        // 낮은 것 다음 높은 것은 둘 다 짝이 없다
        let v: Value = json_from_slice(br#""\udc00\ud800""#).unwrap();
        let units: Vec<_> = v.as_str().unwrap().chars().map(unit_of).collect();
        assert_eq!(units, [Some(0xDC00), Some(0xD800)]);

        // 다른 오류는 그대로
        assert!(json_from_slice::<Value>(b"{\"a\": \"\\ud800\"").is_err());
        assert!(json_from_slice::<Value>(b"[1,]").is_err());
    }

    #[test]
    fn os_bytes_round_trip_like_surrogateescape() {
        let raw = b"caf\xe9/\xff/core.5\xe2\x82";
        let text = decode_os(raw);
        assert!(
            text.starts_with("caf")
                && text.ends_with(&format!(
                    "core.5{}{}",
                    placeholder(0xDCE2).unwrap(),
                    placeholder(0xDC82).unwrap()
                ))
        );
        assert_eq!(encode_os(&text).unwrap(), raw);
        assert_eq!(encode_os(&placeholder(0xD800).unwrap().to_string()), None);
        assert_eq!(decode_os("한글".as_bytes()), "한글");
    }
}
