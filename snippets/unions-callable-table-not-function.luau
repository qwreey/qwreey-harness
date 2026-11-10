--!strict
--@run
-- 주장: `__call` 메타메서드를 가진 테이블은 함수 타입 `(number) -> number` 자리에 들어가지 않는다. 직접 호출은 타입이 맞고 런타임도 멀쩡하다.
--       그래서 `--!nocheck` 스파이크로는 드러나지 않는다. 함수를 받는 API 에 콜러블 테이블을 넘기려면 람다로 감싸거나 지정된 필드 함수를 쓴다.
-- 근거: 실측. 원천 quad/.claude/base/source-state-plan.md:1204-1211, gate-plan.md:154-162 (후보 Q-125)
local callable = setmetatable({}, { __call = function(_: any, x: number): number return x * 2 end })
local function apply(f: (number) -> number): number return f(1) end
local bad = function() return apply(callable) end -- expect-error: Expected this to be '(number) -> number'
local n: number = callable(1)
local wrapped = apply(function(x: number) return callable(x) end)
assert(n == 2 and wrapped == 2)
assert(apply((callable :: any) :: (number) -> number) == 2) -- 런타임은 콜러블 테이블을 함수처럼 부른다
local _ = bad
