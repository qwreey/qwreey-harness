--!strict
--!optimize 1
--@run
-- 주장: 같은 코드를 -O1(Studio 테스트 기본)로 컴파일하면 error(msg, 2) 가 네 경우 모두 진짜 호출 줄을 가리킨다.
--       optimize-o2-error-level.luau 의 대조군. 인라인이 없으면 위치가 맞는다.
-- 근거: Compiler/src/Compiler.cpp compileExprCall("optimizationLevel >= 2" 일 때만 인라인), luau 8387cfb
local function check(x: any): any
	if type(x) ~= "number" then error("check: expected number", 2) end
	return x
end
local T = { check = function(x: any): any
	if type(x) ~= "number" then error("T.check: expected number", 2) end
	return x
end }
local M = {}
function M.check(x: any): any
	if type(x) ~= "number" then error("M.check: expected number", 2) end
	return x
end
local function viaLocal() local r = check("a"); return r end
local function viaConstTable() local r = T.check("a"); return r end
local function viaAssignedField() local r = M.check("a"); return r end
local function variadicCaller(...: any) local r = check("a"); return r end
local function outer() local r = variadicCaller(); return r end

local function msg(f: () -> any): string
	local _, e = pcall(f)
	return tostring(e)
end
assert(msg(viaLocal):find(":20: check", 1, true), msg(viaLocal))
assert(msg(viaConstTable):find(":21: T.check", 1, true), msg(viaConstTable))
assert(msg(viaAssignedField):find(":22: M.check", 1, true), msg(viaAssignedField))
assert(msg(outer):find(":23: check", 1, true), msg(outer))
