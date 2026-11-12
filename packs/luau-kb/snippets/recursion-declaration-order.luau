--!strict
-- 주장(새 솔버 전용): 비균일 재귀 제네릭 SC 보다 '파일에서 먼저' 선언된 별칭이 SC<number> 를 쓰면 그 참조가
--       통째로 에러 타입이 되어 진단 없이 무엇이든 통과한다. SC 뒤에 선언된 별칭은 정상 검사된다.
-- 근거: quad/.claude/base/typing-limits.md 8.21 (원인: ConstraintSolver 의 무한 확장 가드 오판)
type OptsBefore = { Time: SC<number> }
type SC<T> = { Get: (self: SC<T>) -> T, Compute: <U>(self: SC<T>, fn: (T) -> U) -> SC<U> }
type OptsAfter = { Time: SC<number> }
local before: OptsBefore = { Time = "x" } -- bug-present
local after: OptsAfter = { Time = "x" } -- expect-error: Expected this to be 'SC<number>', but got 'string'
local asBool: boolean = before.Time -- bug-present
