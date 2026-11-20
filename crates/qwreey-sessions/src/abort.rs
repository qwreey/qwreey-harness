//! python 판에서 예외가 나는 자리.

/// python 훅이 예외로 끝나는 입력이나 상태.
///
/// 훅은 그때까지 쓴 출력만 남기고 종료 코드 0 으로 끝난다(session-log 는 오류 기록 한 줄을 더 쓴다).
/// Rust 가 python 의 결과를 그대로 만들 수 없는 드문 입력(목록인 session_id 등)도 이것으로 끝낸다: 알림을 내지 않는 쪽이다.
/// 글은 오류 기록(`hook-errors.log`)에 남기는 까닭이다.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Abort(pub &'static str);

/// 훅 단계의 결과.
pub type Result<T> = std::result::Result<T, Abort>;
