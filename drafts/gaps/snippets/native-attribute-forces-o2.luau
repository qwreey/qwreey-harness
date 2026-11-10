--!strict
--!optimize 1
--@run
-- 주장: 파일 어디에든 @native 함수가 하나라도 있으면 모듈 전체가 -O2 로 컴파일된다. 앞의 --!optimize 1 보다 우선한다.
--       (hot comment 처리 뒤 FunctionVisitor.hasNativeFunction 로 다시 덮어씀) 인라인으로 error(msg, 2) 위치가 사라진다.
-- 근거: Compiler/src/Compiler.cpp compileOrThrow "if (functionVisitor.hasNativeFunction) setCompileOptionsForNativeCompilation" (luau 8387cfb)
local function check(x: any): any
	if type(x) ~= "number" then error("check: expected number", 2) end
	return x
end
local function user() local r = check("a"); return r end
local _, e = pcall(user)
local m = tostring(e)
assert(m == "check: expected number", m)
@native
local function unrelated(n: number): number return n * 2 end
assert(unrelated(2) == 4)
