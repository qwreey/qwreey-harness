--!strict
--!native
--@run
--@run-with -O1 => ok
--@run-with --codegen => ok
-- 주장: --!native 는 네이티브 실행과 별개로 컴파일 최적화 수준을 2로 올린다(typeInfoLevel 도 1). 그래서 --codegen 없이(인터프리터로) 돌려도
--       인라인이 일어나 error(msg, 2) 의 위치가 사라진다. Roblox 문서의 "동작은 전과 같고 성능만 다르다"와 어긋나는 관찰 지점.
-- 근거: Compiler/src/Compiler.cpp setCompileOptionsForNativeCompilation, compileOrThrow 의 hot comment 루프(luau 8387cfb)
local function check(x: any): any
	if type(x) ~= "number" then error("check: expected number", 2) end
	return x
end
local function user() local r = check("a"); return r end
local _, e = pcall(user)
local m = tostring(e)
assert(m == "check: expected number", m)
