--!strict
-- 주장: 함수 ∩ 테이블 교집합은 거주하는 값이 없는 타입(never 취급)이라 그 값을 아무 데나 대입해도 진단이 없다.
--       콜러블 테이블은 setmetatable<{...}, { __call: ... }> 로 적는다. 그 __call 의 인자 검사는
--       0.734 에선 빠져 있었고 0.742 에선 된다.
-- 근거: quad/.claude/base/typing-limits.md 8.6 (2026-11-06 재실측 문단)
type Callable = ((string) -> number) & { Merged: number }
local function mk(): Callable return nil :: any end
local asString: string = mk() -- bug-present
local badArg = mk()(5) -- expect-error: Expected this to be 'string', but got 'number'
type CT = setmetatable<{ Merged: number }, { __call: (any, string) -> number }>
local ct = (nil :: any) :: CT
local result: string = ct("x") -- expect-error: Expected this to be 'string', but got 'number'
local argHole = ct(5) -- bug-present [<0.742] || expect-error [>=0.742]
