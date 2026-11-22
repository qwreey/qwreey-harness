//! python str 의 짝 없는 서로게이트(U+D800..U+DFFF)를 Rust `String` 에 담는 자리표.
//!
//! python 글은 짝 없는 서로게이트를 가질 수 있고 Rust `str` 은 못 가진다. 그런 글은 두 곳에서 온다:
//! JSON 의 `"\ud800"` 같은 escape([`super::json_load`] 가 읽는다), 그리고 UTF-8 이 아닌 파일 이름
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

#[cfg(test)]
mod tests {
    use super::*;

    /// UTF-8 이 아닌 바이트는 surrogateescape 자리표로 풀리고, 다시 인코딩하면 같은 바이트다.
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
    }

    /// surrogateescape 범위 밖의 서로게이트(`U+D800`)는 인코딩하지 못한다.
    #[test]
    fn encode_os_rejects_other_surrogates() {
        assert_eq!(encode_os(&placeholder(0xD800).unwrap().to_string()), None);
    }

    /// 올바른 UTF-8 글은 그대로 풀린다.
    #[test]
    fn decode_os_keeps_valid_utf8() {
        assert_eq!(decode_os("한글".as_bytes()), "한글");
    }
}
