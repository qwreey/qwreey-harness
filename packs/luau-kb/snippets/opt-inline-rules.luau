--!strict
--@inline-remarks=2
-- 주장: -O2 인라인 조건(luau-compile --remarks -O2 로 확인, 하네스 머리(--@compile/--@codegen/--@inline-remarks) 가 검사). 각 호출 줄 끝 주석의 [태그]가 기대 결과다.
--       인라인 됨: 로컬 함수, 상수 테이블 리터럴의 필드(그 테이블을 넘기거나 필드에 쓰지 않을 때), 재귀 함수의 바깥 호출 1회, 가변 upvalue 를 쓰는 함수, 단일 반환 함수를 다중 반환 자리에서
--       안 됨: 가변 인자 함수, 다시 대입된 로컬, 넘겨지거나(escape) 필드를 쓴 테이블의 필드, 메서드 호출(:), 비용 초과, 다중 반환 함수를 다중 반환 자리에서
-- 근거: Compiler/src/Compiler.cpp compileFunction(canInline), tryCompileInlinedCall, getFunctionExpr (luau 8387cfb)
local function small(x: number): number return x + 1 end
local function va(...: number): number return (...) end
local reassigned = function(x: number): number return x end
reassigned = function(x: number): number return x * 2 end
local function rec(n: number): number if n <= 0 then return 0 end return rec(n - 1) end
local obj = {}
function obj:m(x: number): number return x end
local K = { f = function(x: number): number return x - 1 end }
local Esc = { f = function(x: number): number return x - 1 end } -- 다른 곳으로 넘겨짐(escape)
local Wr = { f = function(x: number): number return x - 1 end } -- 생성 뒤 필드에 씀
Wr.g = 1
print(Esc)
local up = 0
local function usesUp(x: number): number up += x return up end
local function multi(x: number): (number, number) return x, x end
local function huge(x: number): number
	x = x * 1 + math.sin(x) x = x * 2 + math.sin(x) x = x * 3 + math.sin(x) x = x * 4 + math.sin(x)
	x = x * 5 + math.sin(x) x = x * 6 + math.sin(x) x = x * 7 + math.sin(x) x = x * 8 + math.sin(x)
	x = x * 9 + math.sin(x) x = x * 10 + math.sin(x) x = x * 11 + math.sin(x) x = x * 12 + math.sin(x)
	return x
end
local function test(v: number)
	local a = small(v) -- [inline:ok]
	local b = va(v) -- [inline:variadic]
	local c = reassigned(v) -- [inline:none]
	local d = rec(v) -- [inline:ok]
	local e = obj:m(v) -- [inline:none]
	local f = K.f(v) -- [inline:ok]
	local f2 = Esc.f(v) -- [inline:none]
	local f3 = Wr.f(v) -- [inline:none]
	local g = usesUp(v) -- [inline:ok]
	print(small(v)) -- [inline:ok]
	print(multi(v)) -- [inline:multret]
	local h = huge(v) -- [inline:expensive]
	return a, b, c, d, e, f, f2, f3, g, h
end
return test
