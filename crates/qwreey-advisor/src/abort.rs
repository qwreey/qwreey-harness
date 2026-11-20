//! python 훅이 예외로 끝나는 자리. 바깥 `except Exception` 이 잡아 stdout 없이 끝나므로, 여기서도 낸 것 없이 끝낸다.

/// python 이 예외를 내는 곳. 값은 사람이 읽을 이유(stderr 에 쓴다).
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Abort(pub &'static str);

/// [`Abort`] 로 끝날 수 있는 결과.
pub type Result<T> = std::result::Result<T, Abort>;
