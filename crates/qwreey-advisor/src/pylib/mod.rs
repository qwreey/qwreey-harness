//! 이 플러그인의 python 훅이 쓰는 표준 라이브러리 동작 가운데 `harness_hook::py` 에 없는 것.
//!
//! 다른 플러그인도 쓰게 되면 `harness_hook::py` 로 옮길 후보다(shlex 는 qwreey-proc-guard 에도 한 갈래가 있다).

pub mod fs;
pub mod hashlib;
pub mod pathx;
pub mod shlex;
pub mod text;
