--!strict
--@run-with -O1 => ok; out~helper=ok; out~local=line; out~field=line
--@run-with -O2 => ok; out~helper=lost; out~local=noline; out~field=line
-- 주장: 같은 테스트 코드가 -O1 과 -O2 에서 다른 것을 관측한다(하네스가 두 수준으로 돌려 출력으로 판정).
--   (a) 호출자 줄을 재는 헬퍼 curline() = debug.info(2, "l") 는 -O2 에서 인라인되어 level 2 가 pcall C 프레임이 된다 → -1.
--   (b) 로컬 함수 안의 error(msg, 2) 는 -O2 에서 위치를 잃는다(":줄:" 접두 없음).
--   (c) 생성 뒤 대입한 테이블 필드(function Lib.check)의 error(msg, 2) 는 두 수준 모두 사용자 줄을 가리킨다.
--   그래서 -O1 로만 도는 테스트 스위트는 (a)·(b) 의 실패를 영원히 보지 못한다.
-- 근거: 원천 claude-doctor .claude/archive/research/drafts/gaps/testing.md §5·§12(quad spec.errorutil 이 -O2 에서 실패한 원인), 후보 S-116·S-118. 짝: opt-cli-level-o1.luau
local function curline(): number
	return (debug.info(2, "l") :: any) :: number
end
local helperLine, wantHelper = -1, -1
local function inner()
	wantHelper = debug.info(1, "l") + 1
	helperLine = curline()
end
local function outer()
	inner()
end
pcall(outer)

local function checkLocal(x: any)
	if type(x) ~= "number" then
		error("checkLocal: expected number", 2)
	end
end
local localWhere = 0
local _, localErr = pcall(function()
	localWhere = debug.info(1, "l") + 1
	checkLocal("x")
end)

local Lib = {}
function Lib.check(x: any)
	if type(x) ~= "number" then
		error("Lib.check: expected number", 2)
	end
end
local fieldWhere = 0
local _, fieldErr = pcall(function()
	fieldWhere = debug.info(1, "l") + 1
	Lib.check("x")
end)

local function hasLine(err: any, line: number): string
	return if string.find(tostring(err), `:{line}: `, 1, true) then "line" else "noline"
end
print(`helper={if helperLine == wantHelper then "ok" elseif helperLine == -1 then "lost" else tostring(helperLine)}`)
print(`local={hasLine(localErr, localWhere)}`)
print(`field={hasLine(fieldErr, fieldWhere)}`)
