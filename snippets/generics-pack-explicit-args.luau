--!strict
-- 주장: 타입 팩 제네릭(T...)에 명시 타입 인자를 줄 때는 괄호로 감싼다: f<<(number)>>, f<<(number, string)>>.
--       괄호 없이 f<<number>> 는 "Too many type parameters".
-- 근거: stl-luau/.claude/base/typing-limits.md "가변 팩 자리의 명시적 타입 인자는 괄호로"
type Fut<T...> = { run: (T...) -> () }
local function Rejected<T...>(e: any): Fut<T...>
	return nil :: any
end
local a = Rejected<<number>>(1) -- expect-error: Too many type parameters
local b = Rejected<<(number)>>(1)
local c = Rejected<<(number, string)>>(1)
local wrong: Fut<string> = b -- expect-error: Expected this to be
