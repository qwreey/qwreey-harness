//! 훅을 중간에 끝내는 두 갈래: python 판이 예외로 끝나는 자리와, 이 판이 python 의 판정을 옮기지 않은 자리.

/// 훅을 여기서 끝내는 까닭.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Halt {
    /// python 판이 잡지 않는 예외로 끝나는 입력이나 상태(종료 코드 1, stdout 없음). 글은 stderr 에 쓴다.
    PyError(&'static str),
    /// python 의 결과를 이 판이 그대로 만들 수 없는 드문 입력(목록인 session_id, 옮기지 않은 정규식 문법 등).
    /// 알림 없이 0 으로 끝난다: python 이 조용한 곳에서 알리는 일은 없게 한다.
    Unported(&'static str),
}

/// 훅 단계의 결과.
pub type Result<T> = std::result::Result<T, Halt>;
