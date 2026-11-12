--!strict
-- 주장: 함수 "타입" 안의 가변 인자는 `...T` 로 쓴다. 선언 문법 `...: T` 를 함수 타입에 쓰면 구문 에러다.
-- 근거: create.roblox.com/docs/en-us/luau/type-checking.md "Variadics", rfcs docs/syntax-typed-variadics.md
type A = (...: number) -> number -- expect-error: Expected type, got ':'
type B = (...number) -> number
type C = (x: number, ...number) -> ()
local b: B = function(...: number) return 0 end
local c: C = function(x: number, ...: string) end -- expect-error
local _ = b, c
