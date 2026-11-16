--!strict
-- 주장: 제네릭 M 에 의존하는 index<..., M> 반환을 다른 제네릭에 함수 값으로 넘기면, 결과가 줄어들지 않은 채
--       아무 타입에나 대입된다(never 처럼 행동). 같은 값을 number 에 넣는 대조는 잡힌다.
-- 근거: stl-luau/.claude/audit/luau-solver-issues/7-unreduced-type-function-never.luau
local function mk<M>(mode: M): index<{ full: () -> boolean, impl: (() -> boolean)? }, M>
	return nil :: any
end
local function take<F>(def: (mode: "full") -> F): F
	return nil :: any
end
local f = take(mk)
local asNumber: number = f -- expect-error: Expected this to be 'number', but got '() -> boolean'
local s: string = f() -- bug-present
local t: { x: string } = f() -- bug-present
