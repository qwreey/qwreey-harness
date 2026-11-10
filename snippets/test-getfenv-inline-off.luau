--!strict
--@run-with -O2 => ok; out~helper=ok; out~local=line
--@run-with -O1 => ok; out~helper=ok; out~local=line
-- 주장: 모듈 안에서 getfenv 라는 이름을 한 번 읽기만 해도(호출하지 않아도) 그 모듈의 -O2 인라이닝이 꺼진다.
--   test-o2-line-probe.luau 와 같은 몸통인데 -O2 에서도 헬퍼 줄과 error(msg, 2) 위치가 -O1 과 같다.
--   테스트 함의: mock 을 getfenv 로 주입하는 스펙 파일은 -O2 로 돌려도 그 파일 자신의 인라인 경로를 재현하지 못한다.
--   (인라이닝은 모듈 단위라, require 한 라이브러리 모듈은 여전히 인라인된다.)
-- 근거: luau.org performance 가이드 "inlining is completely disabled for modules that use getfenv/setfenv"(luau-lang/site
--   src/content/docs/guides/performance.md 66-68행), 원천 claude-doctor drafts/gaps/testing.md §6, 후보 Q-118·D-R19
local _ = getfenv
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

print(`helper={if helperLine == wantHelper then "ok" else tostring(helperLine)}`)
print(`local={if string.find(tostring(localErr), `:{localWhere}: `, 1, true) then "line" else "noline"}`)
