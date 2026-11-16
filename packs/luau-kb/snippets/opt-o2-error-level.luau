--!strict
--!optimize 2
--@run
--@run-with -O0 => ok
--@run-with --codegen => ok
-- 주장: 최적화 수준 2(여기선 --!optimize 2 지시어, CLI -O0 도 이긴다)에서 인라인된 함수의 error(msg, 2) 는 위치를 잃거나 엉뚱한 줄을 가리킨다.
--   1) 로컬 함수 -> 위치 없음(level 2 가 pcall C 프레임)  2) 호출자가 인라인 안 되면 -> 호출자의 호출자 줄(틀린 줄)
--   3) 상수 테이블 리터럴의 필드 함수도 인라인된다 -> 위치 없음  4) 생성 뒤 대입한 필드(function M.f)는 인라인 안 됨 -> 정상
--   --codegen(네이티브 실행)도 결과가 같다.
-- 근거: Compiler/src/Compiler.cpp getFunctionExpr/tryIndexConstantTable(luau 8387cfb), luau-compile --remarks -O2. 짝: opt-o1-error-level.luau
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
local function outer() local r = variadicCaller(); return r end

local function msg(f: () -> any): string
	local _, e = pcall(f)
	return tostring(e)
end
assert(msg(viaLocal) == "check: expected number", msg(viaLocal)) -- 1) 위치 없음
assert(msg(viaConstTable) == "T.check: expected number", msg(viaConstTable)) -- 3) 상수 테이블 리터럴 필드도 인라인
assert(msg(viaAssignedField):find(":26: M.check", 1, true), msg(viaAssignedField)) -- 4) 대입 필드는 정상
assert(msg(outer):find(":28: check", 1, true), msg(outer)) -- 2) 틀린 줄: 진짜 호출 줄은 27
