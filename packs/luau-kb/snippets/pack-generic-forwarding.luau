--!strict
-- 주장: 제네릭 팩 `A...`, `R...` 는 함수 감싸기와 인자 전달에서 타입을 그대로 운반한다.
--       타입 별칭은 팩 파라미터를 받고, `<number, ...string>`, `<number, ()>`, `<>`, `(a, b)` 팩 인자를 받는다.
-- 근거: luau.org/types/basic-types "Type packs", rfcs docs/syntax-type-alias-type-packs.md
local function wrap<A..., R...>(fn: (A...) -> R...): (A...) -> R...
	return fn
end
local w = wrap(function(a: number, b: string): boolean return true end)
local w1: number = w(1, "x") -- expect-error: got 'boolean'
w("x", "x") -- expect-error: got 'string'
local function call<A..., R...>(fn: (A...) -> R..., ...: A...): R...
	return fn(...)
end
local c1: string = call(function(a: number) return a end, 1) -- expect-error: got 'number'
call(function(a: number) return a end, "s") -- expect-error: got 'string'
type Signal<T, U...> = { f: (T, U...) -> (), data: T }
local function fire<T, U...>(s: Signal<T, U...>, ...: U...) end
local sig: Signal<string, (number, boolean)> = { f = function(_: string, _: number, _: boolean) end, data = "d" }
fire(sig, 1, true)
fire(sig, 1, 2) -- expect-error
type A<T, U...> = (T) -> U...
type B = A<number, ...string>
type D = A<number, ()>
type Returns<T...> = () -> T...
type E = Returns<>
local b: B = function(_: number) return "x", "y" end
local d: D = function(_: number) return 1 end -- expect-error
local e: E = function() end
local _ = w1, c1, b, d, e
