--!strict
--@run
-- 주장: 1) {...} + ipairs 는 첫 nil 에서 멈춘다. 개수는 select("#", ...) 나 table.pack(...).n 으로 센다.
--       2) 다중 반환은 인자, 생성자 목록의 마지막일 때만 펼쳐진다. 가운데면 첫 값만 남는다.
--       3) 테이블 생성자에서 같은 키가 두 번 나오면 마지막 값만 남는다.
-- 근거: quad .claude/base/effect-plan.md:228-232, .claude/base/tag-plan.md:76-83, .claude/archive/onchange-hash-key-reversed.md:34-37,
--       rbvm-cr:677. 후보 Q-076, Q-074, R-25
local function count(...: any): (number, number, number)
	local viaIpairs = 0
	for _, _ in ipairs({ ... }) do
		viaIpairs += 1
	end
	return viaIpairs, select("#", ...), table.pack(...).n
end
local a, b, c = count(1, nil, 3)
assert(a == 1 and b == 3 and c == 3)

local function pair(): (number, number)
	return 1, 2
end
local mid = { pair(), 10 }
local last = { 10, pair() }
assert(#mid == 2 and mid[2] == 10 and #last == 3)

local k = "key"
local dup = { [k] = "first", [k] = "second" }
assert(dup.key == "second")
