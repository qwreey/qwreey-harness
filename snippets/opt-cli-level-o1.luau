--!strict
--@run
--@run-with -O2 => fail; out~check: expected number
-- 주장: 지시어가 없으면 CLI 수준을 따른다. opt-o1-error-level 의 단언을 지시어 없이 둔 사본이다.
--   기본(-O1) 실행은 통과하고, luau -O2 로 돌리면 인라인으로 위치가 사라져 첫 단언이 실패한다(음성 대조군).
--   -O1 로만 돌리는 테스트는 이 실패를 영원히 보지 못한다.
-- 근거: 원천 claude-doctor drafts/gaps/tools/run_opt.sh B3·B4
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
assert(msg(viaLocal):find(":21: check", 1, true), msg(viaLocal))
assert(msg(viaConstTable):find(":22: T.check", 1, true), msg(viaConstTable))
assert(msg(viaAssignedField):find(":23: M.check", 1, true), msg(viaAssignedField))
assert(msg(outer):find(":24: check", 1, true), msg(outer))
