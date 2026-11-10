--!strict
-- 주장: 서브타입 테이블에 '자기 타입을 참조하는 함수 필드'가 있고, 슈퍼타입 유니온의 어느 멤버가 같은 이름의
--       함수 필드를 가지면, 다른 필드가 어긋나도 유니온 대조가 통과한다. 둘 중 하나만 있으면 정상 거부.
-- 근거: quad/.claude/base/typing-limits.md 8.9 (luau-test/done/31)
type MarkA = { read tag: "A" }
type Xn = { Zed: (self: Xn) -> number, Other: (self: Xn) -> string }
type R3 = { read tag: "B", Zed: (self: R3) -> number }
local r3 = (nil :: any) :: R3
local hole: Xn | MarkA = r3 -- bug-present
local single: MarkA = r3 -- expect-error: Expected this to be 'MarkA', but got 'R3'
type Xn4 = { Zed: () -> number, Other: () -> string }
type R4 = { read tag: "B", Zed: () -> number }
local noSelf: Xn4 | MarkA = (nil :: any) :: R4 -- expect-error: Expected this to be 'MarkA | Xn4', but got 'R4'
