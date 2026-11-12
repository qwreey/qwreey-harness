--!strict
-- 주장: 콜백 타입이 `(number) -> (string?, number?)` 이면 값 하나만 돌려주는 콜백은 strict 에러다(옵셔널이어도 개수는 맞춰야 한다).
--       선택적으로 덜 돌려줘도 되는 API 는 함수 타입의 유니온으로 받는다. 또 Luau 에는 사용자 정의 타입 가드(`x is T`)가 없어서
--       불리언을 돌려주는 술어로는 좁혀지지 않는다 → 술어 뒤에 캐스트하거나 `type(x) == …` 를 그 자리에 쓴다.
-- 근거: 실측. 원천 quad/.claude/base/slot-plan.md:1232-1240, brand-plan.md:291-298 (후보 Q-127)
local function each(fn: (number) -> (string?, number?)) end
each(function(x: number) return "a" end) -- expect-error: Expected this to be 'string?, number?', but got 'string?'
each(function(x: number) return "a", 1 end)
type F2 = (number) -> (string?, number?)
type F1 = (number) -> string?
local function each2(fn: F2 | F1) end
each2(function(x: number) return "a" end)
local function isStr(v: unknown): boolean return type(v) == "string" end
local u = (nil :: any) :: unknown
if isStr(u) then local s: string = u end -- expect-error: but got 'unknown'
if isStr(u) then local s = u :: string end
if type(u) == "string" then local s: string = u end
