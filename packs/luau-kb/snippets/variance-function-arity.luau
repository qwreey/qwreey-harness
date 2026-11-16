--!strict
-- 주장: 파라미터가 적은 함수 '리터럴', 함수 문장은 파라미터가 많은 함수 타입 자리에 들어간다(초과 인자는 버려짐).
--       그러나 선언된 함수 타입을 가진 '값'은 파라미터가 적으면 거부된다. 파라미터가 더 많거나 타입이 다르면 거부.
-- 근거: quad/.claude/base/typing-limits.md 8.23, 8.36 5번(keyFn), audit/consumer-type-surface-2026-10-06/probes/pure/repro_arity_pure.luau
local function one(x: number) end
local typed: (number) -> () = one
local lit: (number, number) -> () = function(x) end
local stmt: (number, number) -> () = one
local val: (number, number) -> () = typed -- expect-error: Expected the parameter types to be a supertype
local key = (nil :: any) :: (string) -> string
local optSlot: ((string, number) -> any)? = key -- expect-error: Expected this to be
local more: (number, number) -> () = function(x, y, z) end -- expect-error: Expected this to be
local other: (number, number) -> () = function(x: string) end -- expect-error: Expected this to be
