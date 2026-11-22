//! 훅이 아무것도 내지 않고 끝나는 까닭. python 판은 훅 본문을 `except Exception` 으로 감싸 어떤 예외든 출력 없이 끝난다
//! (subagent-slots 는 원장을 쓰기 전의 예외도 삼켜 상태 파일을 고치지 않는다). 갈래는 읽는 사람과 시험을 위해 둔다.

/// 출력 없이 끝나는 까닭.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Stop {
    /// python 이 이 입력에서 예외로 끝난다(값은 무엇이 터지는지). 상태 파일도 쓰지 않는다.
    Raises(&'static str),
    /// python 은 답을 낼 수 있지만 이 판은 그 계산을 옮기지 않았다(값은 무엇을). 출력 없이 끝나 python 보다 덜 알린다.
    Unported(&'static str),
}

/// 이 crate 의 결과.
pub type Result<T> = std::result::Result<T, Stop>;
