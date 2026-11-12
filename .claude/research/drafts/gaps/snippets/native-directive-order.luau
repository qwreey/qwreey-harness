--!strict
--!native
--!optimize 1
--@run
-- 주장: 지시어는 위에서부터 차례로 적용된다. --!native 뒤에 --!optimize 1 을 쓰면 최적화 수준이 1로 돌아가 인라인이 없다(위치 보존).
--       순서를 바꾸면(--!optimize 1 다음 --!native) 2가 된다. native-directive-forces-o2.luau 의 대조군.
-- 근거: Compiler/src/Compiler.cpp compileOrThrow 의 hot comment 루프(luau 8387cfb)
local function check(x: any): any
	if type(x) ~= "number" then error("check: expected number", 2) end
	return x
end
local function user() local r = check("a"); return r end
local _, e = pcall(user)
local m = tostring(e)
assert(m:find(":12: check", 1, true), m)
