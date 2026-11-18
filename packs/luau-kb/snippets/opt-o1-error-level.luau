--!strict
--!optimize 1
--@run
--@run-with -O2 => ok
--@run-with --codegen => ok
--@run-with -g0 => fail; out~check: expected number; out!~:25:
-- 주장: 같은 코드를 최적화 수준 1 로 컴파일하면 error(msg, 2) 가 네 경우 모두 진짜 호출 줄을 가리킨다. opt-o2-error-level 의 대조군.
--   - 소스 지시어 --!optimize 1 은 CLI -O2 를 이긴다(run-with -O2 도 통과).
--   - --codegen(네이티브 실행)은 위치를 바꾸지 않는다. 바뀌는 것은 최적화 수준 때문이다.
--   - -g0 은 줄 정보를 모두 지워 위치 단언이 실패한다(메시지에 줄 번호가 없다).
-- 근거: Compiler/src/Compiler.cpp compileExprCall("optimizationLevel >= 2" 일 때만 인라인), luau 8387cfb. 원천: qwreey-harness .claude/scopes/packs/luau-kb/archive/research/drafts/gaps/optimize-levels.md
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
assert(msg(viaLocal):find(":25: check", 1, true), msg(viaLocal))
assert(msg(viaConstTable):find(":26: T.check", 1, true), msg(viaConstTable))
assert(msg(viaAssignedField):find(":27: M.check", 1, true), msg(viaAssignedField))
assert(msg(outer):find(":28: check", 1, true), msg(outer))
