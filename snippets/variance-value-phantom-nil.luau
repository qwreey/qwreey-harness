--!strict
-- 주장: 값 팬텀 read __phantom: T 는 T 가 nil 을 품으면 그 필드가 아예 없는 테이블도 통과시킨다
--       (없는 read 필드를 nil 로 읽음). 함수 팬텀 (T) -> T 는 거부한다.
-- 근거: stl-luau/.claude/base/typing-limits.md "값 팬텀은 피하세요", quad 8.42 1번
type VP<T> = { read __phantom: T }
type FP<T> = { read __phantom: (T) -> T }
local empty = {}
local holeAccepted: VP<number?> = empty -- bug-present
local strict: VP<number> = empty -- expect-error: Expected this to be 'VP<number>'
local funcPhantom: FP<number?> = empty -- expect-error: Expected this to be 'FP<number?>'
