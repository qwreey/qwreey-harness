--!strict
-- 주장: `...: T` 와 `(...T) -> ...U` 는 가변 인자 원소를 검사한다. select 는 첫 인자가 리터럴일 때만 정확한 타입을 준다.
--       select("#", ...) 는 number, select(<정수 리터럴>, ...) 는 뒤쪽 팩, select(<변수>, ...) 는 ...any(검사 꺼짐).
--       주석 없는 `...` 는 ...any 다.
-- 근거: luau.org/types/basic-types "Variadic types", luau 소스 Analysis/src/BuiltinDefinitions.cpp MagicSelect::infer,
--       EmbeddedBuiltinDefinitions.cpp `declare function select<A...>(i: string | number, ...: A...): ...any`
local function f(...: number) end
f(1, 2, 3)
f(1, "s") -- expect-error: Expected this to be 'number', but got 'string'
type F = (...number) -> ...string
local g: F = function(...) return "a", 1 end -- expect-error
local function sel(i: number, ...: string)
	return select("#", ...), select(2, ...), select(i, ...)
end
local n1, a1, b1 = sel(1, "x")
local q1: string = n1 -- expect-error: got 'number'
local q2: number = a1 -- expect-error: got 'string'
local q3: number = b1 -- bug-present
local lit = select(2, 1, "two", true)
local q4: number = lit -- expect-error: got 'string'
local function unann(...) return ... end
local q5: boolean = unann(1, "x") -- bug-present
local _ = g, q1, q2, q3, q4, q5
