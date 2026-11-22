//! 훅이 아무것도 내지 않고 끝나는 까닭. 두 훅 모두 python 판이 본문 전체를 `except Exception: pass` 로 감싸므로
//! 어느 까닭이든 출력 없이 종료 코드 0 이다. 갈래는 읽는 사람과 시험을 위해 둔다.

/// 출력 없이 끝나는 까닭.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Stop {
    /// python 이 이 입력에서 예외로 끝난다(값은 무엇이 터지는지).
    Raises(&'static str),
    /// python 이 답을 내지만 이 판은 그 계산을 옮기지 않았다(값은 무엇을). 출력 없이 끝나 python 보다 덜 막는다.
    Unported(&'static str),
}

/// 이 crate 의 결과.
pub type Result<T> = std::result::Result<T, Stop>;
