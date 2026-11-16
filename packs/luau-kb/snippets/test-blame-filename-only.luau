--!strict
--@run
--@run-opt=2
-- 주장: "에러가 사용자를 가리킨다"를 파일 이름만으로 단언하면 level 이 틀린 라이브러리도 통과한다.
--   라이브러리와 테스트가 같은 파일(또는 이름만 보는 단언)일 때, error(msg, 1) 로 라이브러리 줄을 가리키는 잘못된 구현이
--   파일 이름 단언은 통과하고 ":<사용자 줄>: " 단언에서만 걸린다. 그래서 메시지와 정확한 사용자 줄을 같이 단언한다.
-- 근거: stl-luau/.claude/conventions.md:140(메시지만 보면 level 이 틀려도 통과 - 돌연변이로 확인한 기록), 후보 S-118.
--   quad/quad-base/test/mock.luau:854-858 의 assertBlamesUser 는 파일 이름과 "/src/" 부재만 본다.
local Lib = {}
function Lib.good(x: unknown)
	if type(x) ~= "number" then
		error("Lib.good: expected number", 2)
	end
end
function Lib.bad(x: unknown) -- 돌연변이: level 1 -> 라이브러리 줄을 가리킨다
	if type(x) ~= "number" then
		error("Lib.bad: expected number", 1)
	end
end

local function blameFileOnly(err: any): boolean
	return string.find(tostring(err), "test-blame-filename-only", 1, true) ~= nil
end
local function blameLine(err: any, line: number): boolean
	return string.find(tostring(err), `:{line}: `, 1, true) ~= nil
end

local w1 = 0
local _, e1 = pcall(function()
	w1 = debug.info(1, "l") + 1
	Lib.good("x")
end)
local w2 = 0
local _, e2 = pcall(function()
	w2 = debug.info(1, "l") + 1
	Lib.bad("x")
end)
assert(blameFileOnly(e1) and blameLine(e1, w1), tostring(e1))
assert(blameFileOnly(e2), "파일 이름 단언은 잘못된 구현도 통과시킨다: " .. tostring(e2))
assert(not blameLine(e2, w2), "줄 단언만 잘못된 level 을 잡는다: " .. tostring(e2))
print("ok")
