--!strict
-- 주장: 값 팬텀 read __phantom: T 는 T 가 nil 을 품으면 그 필드가 아예 없는 테이블도 통과시킨다
--       (없는 read 필드를 nil 로 읽음). 함수 팬텀 (T) -> T 는 거부한다.
-- 0.746 에서 고쳐짐: 이미 만든 테이블(empty)은 거부한다. 리터럴 `{}` 를 바로 넣는 것은 0.746 에서도 통과(watchlist 2).
-- 근거: stl-luau/.claude/base/typing-limits.md "값 팬텀은 피하세요", quad 8.42 1번
type VP<T> = { read __phantom: T }
type FP<T> = { read __phantom: (T) -> T }
local empty = {}
local holeAccepted: VP<number?> = empty -- bug-present [<0.746] || expect-error: Expected this to be 'VP<number?>' [>=0.746]
local strict: VP<number> = empty -- expect-error: Expected this to be 'VP<number>'
local funcPhantom: FP<number?> = empty -- expect-error: Expected this to be 'FP<number?>'
