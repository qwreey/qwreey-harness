--!strict
--@run
-- 주장: "에러가 사용자 줄을 가리킨다"를 단언하는 견고한 모양은 둘을 같이 지킨다.
--   (1) 기대 줄은 그 자리에서 `where = debug.info(1, "l") + 1` 로 잰다(헬퍼로 재지 않는다).
--   (2) 라이브러리 함수는 테이블 필드로 부른다. 로컬 함수의 error(msg, 2) 는 -O2 인라인에서 위치를 잃는다.
-- 이 파일의 assert 는 -O0/-O1/-O2 모두에서 통과한다(testing.md §5 의 수동 실행 기록).
-- 근거: stl-luau/.claude/conventions.md:138, stl-luau/tests/spec.common.luau:99-130, decisions D-10.

local Lib = {}
function Lib.check(x: unknown)
	if type(x) ~= "number" then
		error("Lib.check: expected number", 2)
	end
end

local function expectErrorAt(label: string, run: () -> (), wantLine: () -> number, needle: string)
	local ok, err = pcall(run)
	assert(not ok, `{label}: 에러가 안 남`)
	local msg = tostring(err)
	assert(string.find(msg, needle, 1, true) ~= nil, `{label}: 메시지: {msg}`)
	local line = wantLine()
	assert(string.find(msg, `:{line}: `, 1, true) ~= nil, `{label}: {line} 줄이 아님: {msg}`)
end

local where = 0
expectErrorAt("필드 경유 level 2", function()
	where = debug.info(1, "l") + 1
	Lib.check("x")
end, function()
	return where
end, "expected number")

print("ok")
