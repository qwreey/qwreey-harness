-- 주장(S-P21, S-P23, S-P33): 단건 접근에서 상수 문자열 필드 n.value 와 번호 칸 n[1] 은 비슷하다(인라인 캐시).
--   표 조회 키: 원천은 '숫자 키가 테이블 키보다 싸다'고 적었다(그 숫자는 배열부 칸이었다). # 의 비용을 필드 n 읽기와 비교한다(# 는 경계 캐시가 맞으면 O(1), 아니면 이진 탐색 O(log n)).
-- 원 수치: stl perf 38-2절(-O2): n.value 5.1ns ≈ n[1] 4.7ns. 39절: 테이블 키 14.8 vs 숫자 키 9.1ns. 17절: # 한 번 약 90ns(20만).
local Bench = require("./lib/bench")

local N = 2_000_000
local node = { 1, 2, value = 3 }
Bench.run("tbl-access/field-vs-slot", {
	{ name = "n.value", fn = function()
		local s, n = 0, node
		for _ = 1, N do s += n.value end
		return s
	end },
	{ name = "n[1]", fn = function()
		local s, n = 0, node
		for _ = 1, N do s += n[1] end
		return s
	end },
})

local KEYS = 1024
local tkeys, akeys, nkeys, ikeys, skeys = {}, {}, {}, {}, {}
local byT, byA, byN, byI, byS = {}, {}, {}, {}, {}
local rnd = Bench.rng(7)
for i = 1, KEYS do
	tkeys[i] = {}
	nkeys[i] = (rnd() % 1_000_000) + 0.5 -- 정수가 아닌 숫자 키: 항상 해시부
	ikeys[i] = 1_000_000 + (rnd() % 1_000_000) -- 큰 정수 키: 해시부
	skeys[i] = "key" .. i
	byI[ikeys[i]] = i
	akeys[i] = i -- 1..KEYS: 배열부
	byA[i] = i
	byT[tkeys[i]] = i
	byN[nkeys[i]] = i
	byS[skeys[i]] = i
end
local function lookups(map: { [any]: number }, keys: { any })
	return function()
		local s = 0
		for _ = 1, N // KEYS do
			for i = 1, KEYS do s += map[keys[i]] end
		end
		return s
	end
end
Bench.run("tbl-access/hash-key-kind", {
	{ name = "테이블 키", fn = lookups(byT, tkeys) },
	{ name = "작은 정수 키(배열부)", fn = lookups(byA, akeys) },
	{ name = "정수 키(해시부)", fn = lookups(byI, ikeys) },
	{ name = "숫자 키(비정수)", fn = lookups(byN, nkeys) },
	{ name = "문자열 키(변수)", fn = lookups(byS, skeys) },
})

local big = table.create(200_000, 1)
local partial = table.create(262_144) -- 배열부가 다 차지 않은 표
for i = 1, 200_000 do partial[i] = 1 end
local holder = { n = 200_000, data = big }
Bench.run("tbl-access/len", {
	{ name = "holder.n", fn = function()
		local s = 0
		for _ = 1, 200_000 do s += holder.n end
		return s
	end },
	{ name = "#big (20만)", fn = function()
		local s, b = 0, big
		for _ = 1, 200_000 do s += #b end
		return s
	end },
	{ name = "#partial (20만/262144)", fn = function()
		local s, b = 0, partial
		for _ = 1, 200_000 do s += #b end
		return s
	end },
	{ name = "끝에 넣고 # 하고 빼기", fn = function()
		local s, b = 0, partial
		for _ = 1, 200_000 do
			b[200_001] = 1
			s += #b
			b[200_001] = nil
		end
		return s
	end },
})
