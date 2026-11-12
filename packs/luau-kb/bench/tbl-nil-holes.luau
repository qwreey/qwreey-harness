-- 주장(S-P17): 배열을 앞에서부터 채우며 구멍 자리에 nil 을 바로 대입하면 배열부가 자라지 못해 뒤 원소가 해시부로 간다.
--   만들기도 느리고, 만든 뒤의 인덱싱도 느리다. 자리표시자로 채우고 마지막에 그 자리만 nil 로 바꾸면 배열부가 유지된다.
-- 원 수치: stl perf 19절(-O2, 15회 최소): 구멍 1/2 에서 만들기 9.5배, 결과 인덱싱 4.5배(45.7 vs 10.1ms).
local Bench = require("./lib/bench")

local N = 200_000
local HOLE = {}

local function buildDirect(): { any }
	local t = {}
	for i = 1, N do
		if i % 2 == 0 then t[i] = nil else t[i] = i end
	end
	return t
end
local function buildPlaceholder(): { any }
	local t = {}
	local holes = {}
	for i = 1, N do
		if i % 2 == 0 then
			t[i] = HOLE
			holes[#holes + 1] = i
		else
			t[i] = i
		end
	end
	for _, i in holes do t[i] = nil end
	return t
end
local function buildDense(): { any }
	local t = {}
	for i = 1, N do t[i] = i end
	return t
end

Bench.run("tbl-nil-holes/build", {
	{ name = "조밀(구멍 없음)", fn = buildDense },
	{ name = "자리표시자 후 nil", fn = buildPlaceholder },
	{ name = "구멍에 nil 바로", fn = buildDirect },
}, { rounds = 9 })

local direct, placeholder, dense = buildDirect(), buildPlaceholder(), buildDense()
local function scan(t: { any }): number
	local c = 0
	for i = 1, N do
		if t[i] ~= nil then c += 1 end
	end
	return c
end
Bench.run("tbl-nil-holes/index", {
	{ name = "조밀", fn = function() return scan(dense) end },
	{ name = "자리표시자 후 nil", fn = function() return scan(placeholder) end },
	{ name = "구멍에 nil 바로", fn = function() return scan(direct) end },
}, { rounds = 9 })
