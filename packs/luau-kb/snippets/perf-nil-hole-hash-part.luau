--!strict
--@run
-- 주장: 배열을 앞에서부터 채우며 구멍 자리를 nil 로 두면(t[i] = nil 이거나 대입을 건너뜀) 배열부가 자라지 못해
--       원소가 해시부에 들어간다. 자리표시자로 채운 뒤 마지막에 nil 로 바꾸면 배열부에 남는다(대조군).
--       판별: 일반화 for 는 배열부를 번호 순으로 먼저 돌고 해시부는 해시 순서로 돈다. 순서가 섞이면 해시부에 있다는 뜻이다.
-- 근거: 후보 S-P17, stl-luau-doctor/.claude/base/perf-measurements.md 19절. 시간 비교는 bench/tbl-nil-holes.luau
local N = 1000
local HOLE = {}

local function ascending(t: { [number]: any }): boolean
	local last = 0
	for k in t do
		if k < last then
			return false
		end
		last = k
	end
	return true
end

local direct: { [number]: any } = {}
for i = 1, N do
	if i % 2 == 1 then
		direct[i] = i
	end
end

local placeholder: { [number]: any } = {}
for i = 1, N do
	placeholder[i] = if i % 2 == 1 then i else HOLE
end
for i = 2, N, 2 do
	placeholder[i] = nil
end

assert(not ascending(direct), "구멍에 nil 을 바로 두면 원소가 해시부로 간다")
assert(ascending(placeholder), "자리표시자로 채우면 배열부에 남는다")
print("ok")
