--!strict
--!optimize 2
--@run
-- 주장: -O2(여기선 --!optimize 2 지시어)에서 인라인된 함수의 error(msg, 2) 는 호출자 위치를 잃거나 엉뚱한 줄을 가리킨다.
--       ① 로컬 함수 → 위치 없음(level 2 가 pcall C 프레임)  ② 호출자가 인라인 안 되면 → 호출자의 호출자 줄(틀린 줄)
--       ③ 상수 테이블 리터럴의 필드 함수도 인라인된다 → 위치 없음  ④ 생성 뒤 대입한 테이블 필드(function M.f) 는 인라인 안 됨 → 정상
-- 근거: Compiler/src/Compiler.cpp getFunctionExpr/tryIndexConstantTable(luau 8387cfb), luau-compile --remarks -O2. 짝: optimize-o1-error-level.luau
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
local function variadicCaller(...: any) local r = check("a"); return r end -- 가변 인자 함수는 인라인되지 않는다
local function outer() local r = variadicCaller(); return r end -- line 25: ②가 가리키게 되는 줄

local function msg(f: () -> any): string
	local _, e = pcall(f)
	return tostring(e)
end
assert(msg(viaLocal) == "check: expected number", msg(viaLocal))
assert(msg(viaConstTable) == "T.check: expected number", msg(viaConstTable))
assert(msg(viaAssignedField):find(":23: M.check", 1, true), msg(viaAssignedField))
assert(msg(outer):find(":25: check", 1, true), msg(outer)) -- 진짜 호출 줄은 24
