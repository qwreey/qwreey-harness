--!strict
--@run
-- 주장: 테이블 메모리는 배열부와 해시부를 따로 잡는다. 이름 필드가 하나라도 있으면 해시부가 생긴다.
--       같은 3칸이라도 전부 번호 칸 < 번호 2 + 이름 1 < 전부 이름 순으로 크다. 트리 노드 6칸도 전부 번호 칸이 가장 작다.
--       번호 칸을 생성자 밖에서 나중에 대입해도 메모리는 같지만 만들기가 몇 배 느리다(bench/tbl-ctor-slots.luau).
-- 근거: 후보 S-P19, S-P20, S-P37, stl-luau-doctor/.claude/base/perf-measurements.md 34·38절(0.734: 96/112/176B, 144/224B)
local collect = (_G :: any).collectgarbage
local N = 10_000

local function bytesPer(make: (number) -> any): number
	local keep = table.create(N)
	collect("collect")
	local before = collect("count")
	for i = 1, N do
		keep[i] = make(i)
	end
	collect("collect")
	local after = collect("count")
	assert(#keep == N)
	return (after - before) * 1024 / N
end

local allSlots = bytesPer(function(i) return { false, false, i } end)
local mixed = bytesPer(function(i) return { false, false, value = i } end)
local allNamed = bytesPer(function(i) return { prev = false, next = false, value = i } end)
local tree6 = bytesPer(function(i) return { false, false, false, i, i, true } end)
local tree33 = bytesPer(function(i) return { false, false, false, key = i, value = i, red = true } end)
assert(allSlots < mixed and mixed < allNamed, `3칸: {allSlots} < {mixed} < {allNamed}`)
assert(tree6 < tree33, `6칸: {tree6} < {tree33}`)
print("ok", allSlots, mixed, allNamed, tree6, tree33)
