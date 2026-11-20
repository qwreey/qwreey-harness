//! python `hashlib.sha1(data).hexdigest()[:n]`: 훅이 diff 와 보고 글의 짧은 지문을 만든다(python 상태 파일과 같은 값).

use sha1::{Digest, Sha1};

/// `data` 의 SHA-1 소문자 hex 앞 `n` 자(python `hashlib.sha1(data).hexdigest()[:n]`).
pub fn sha1_hex_prefix(data: &[u8], n: usize) -> String {
    let mut digest: String = Sha1::digest(data)
        .iter()
        .map(|b| format!("{b:02x}"))
        .collect();
    digest.truncate(n);
    digest
}

#[cfg(test)]
mod tests {
    use super::*;

    /// python hashlib 의 값과 같다(FIPS 180 시험 값, 블록 경계 55, 56 바이트).
    #[test]
    fn known_vectors() {
        assert_eq!(
            sha1_hex_prefix(b"", 40),
            "da39a3ee5e6b4b0d3255bfef95601890afd80709"
        );
        assert_eq!(sha1_hex_prefix(b"abc", 16), "a9993e364706816a");
        assert_eq!(sha1_hex_prefix(&[b'a'; 55], 12), "c1c8bbdc2279");
        assert_eq!(sha1_hex_prefix(&[b'a'; 56], 12), "c2db330f6083");
    }
}
