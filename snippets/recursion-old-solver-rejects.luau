--!strict
--@solver=old
-- 주장: 옛 솔버(--solver=old)는 비균일 재귀 별칭을 선언 시점에 "Recursive type being used with different parameters"
--       로 거부한다(새 솔버는 받아 주되 위 recursion-nonuniform-return 처럼 반환이 샌다).
-- 근거: quad/.claude/base/typing-limits.md §1 "언제 풀리는가", §1③ 마지막 항목
type Tween<T> = { Value: T, Mapped: <U>(self: Tween<T>, fn: (T) -> U) -> Tween<U> } -- expect-error: Recursive type being used with different parameters
type Same<T> = { Value: T, Again: (self: Same<T>) -> Same<T> }
local s = (nil :: any) :: Same<string>
local uniform: number = s:Again().Value -- expect-error: Expected this to be 'number', but got 'string'
