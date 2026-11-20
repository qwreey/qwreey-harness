//! SHA-1(FIPS 180-4). python `hashlib.sha1(data).hexdigest()` 자리: 훅이 diff 와 보고 글의 짧은 지문을 만든다.
//!
//! why not sha1 crate: 새 의존성은 사용자가 정한다. 지문은 보안 용도가 아니고 python 상태 파일과 같은 값이면 된다.
//! 같은 RustCrypto 의 `sha1` crate(sha2 와 digest 를 같이 씀)로 바꾸는 것은 제안으로 남긴다.

const H0: [u32; 5] = [
    0x6745_2301,
    0xefcd_ab89,
    0x98ba_dcfe,
    0x1032_5476,
    0xc3d2_e1f0,
];

/// `data` 의 SHA-1 을 소문자 hex 40자로.
pub fn hex(data: &[u8]) -> String {
    let mut state = H0;

    // Pad: 0x80, zeros, then the bit length as a big-endian u64
    let bit_len = (data.len() as u64).wrapping_mul(8);
    let mut message = data.to_vec();
    message.push(0x80);
    while message.len() % 64 != 56 {
        message.push(0);
    }
    message.extend_from_slice(&bit_len.to_be_bytes());

    for block in message.as_chunks::<64>().0 {
        compress(&mut state, block);
    }
    state.iter().map(|word| format!("{word:08x}")).collect()
}

/// [`hex`] 의 앞 `n` 자(python `hexdigest()[:n]`).
pub fn hex_prefix(data: &[u8], n: usize) -> String {
    let mut digest = hex(data);
    digest.truncate(n);
    digest
}

fn compress(state: &mut [u32; 5], block: &[u8; 64]) {
    // Message schedule
    let mut w = [0u32; 80];
    for (i, word) in block.as_chunks::<4>().0.iter().enumerate() {
        w[i] = u32::from_be_bytes(*word);
    }
    for i in 16..80 {
        w[i] = (w[i - 3] ^ w[i - 8] ^ w[i - 14] ^ w[i - 16]).rotate_left(1);
    }

    // Eighty rounds in four stages
    let [mut a, mut b, mut c, mut d, mut e] = *state;
    for (i, &wi) in w.iter().enumerate() {
        let (f, k) = match i {
            0..=19 => ((b & c) | (!b & d), 0x5a82_7999),
            20..=39 => (b ^ c ^ d, 0x6ed9_eba1),
            40..=59 => ((b & c) | (b & d) | (c & d), 0x8f1b_bcdc),
            _ => (b ^ c ^ d, 0xca62_c1d6),
        };
        let temp = a
            .rotate_left(5)
            .wrapping_add(f)
            .wrapping_add(e)
            .wrapping_add(k)
            .wrapping_add(wi);
        e = d;
        d = c;
        c = b.rotate_left(30);
        b = a;
        a = temp;
    }

    // Add this block into the running state
    for (slot, value) in state.iter_mut().zip([a, b, c, d, e]) {
        *slot = slot.wrapping_add(value);
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// FIPS 180 의 시험 값과 블록 경계(55, 56, 64 바이트)에서 python hashlib 과 같다.
    #[test]
    fn known_vectors() {
        // Standard vectors
        assert_eq!(hex(b""), "da39a3ee5e6b4b0d3255bfef95601890afd80709");
        assert_eq!(hex(b"abc"), "a9993e364706816aba3e25717850c26c9cd0d89d");
        assert_eq!(
            hex(b"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq"),
            "84983e441c3bd26ebaae4aa1f95129e5e54670f1"
        );

        // Padding boundaries: 55 bytes fit one block, 56 need two
        assert_eq!(hex(&[b'a'; 55]), "c1c8bbdc22796e28c0e15163d20899b65621d65a");
        assert_eq!(hex(&[b'a'; 56]), "c2db330f6083854c99d4b5bfb6e8f29f201be699");
        assert_eq!(hex(&[b'a'; 64]), "0098ba824b5c16427bd7a1122a5a442a25ec644d");
        assert_eq!(hex_prefix(b"abc", 16), "a9993e364706816a");
    }
}
