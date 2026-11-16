--!strict
--@run-with -O2 => ok
--@run-with -O1 => fail; out~check: expected number
-- 주장: 지시어가 없으면 CLI 수준을 따른다. opt-o2-error-level 의 단언을 지시어 없이 둔 사본이다.
--   luau -O2 에서는 단언이 통과하고(위치 소실), 기본 -O1 에서는 위치가 남아 첫 단언이 실패한다(음성 대조군).
-- 근거: luau CLI 기본 -O1(luau --help). 원천: claude-doctor .claude/archive/research/drafts/gaps/tools/run_opt.sh B1, B2
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
assert(msg(viaAssignedField):find(":22: M.check", 1, true), msg(viaAssignedField)) -- 4) 대입 필드는 정상
assert(msg(outer):find(":24: check", 1, true), msg(outer)) -- 2) 틀린 줄: 진짜 호출 줄은 23
