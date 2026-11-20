//! python 표준 라이브러리 동작을 바이트까지 맞춘 조각. 훅 출력과 설정 값이 python 판과 같아야 해서 둔다.
//!
//! why not 일반 crate(dirs, dotenvy, ryu 등): 결과가 python 과 바이트로 같아야 한다. 일반 구현은 공백 판정,
//! float 표기, `~` 풀기, 경로 정규화가 python 과 조금씩 달라 그 차이가 그대로 훅 출력과 설정 값에 나온다.

pub mod json;
pub mod num;
pub mod path;
pub mod re;
pub mod tempfile;
pub mod text;
pub mod unicode;
mod unicode_tables;
pub mod value;
