-- 주장(S-P14, S-P15, S-P47, M-08): 이 런타임에서는 C 로 내려가는 쪽(해싱, table.sort)이 차수만 좋은 Luau 루프를 이긴다.
--   O(n+m) 정렬 병합 합집합은 비교자 함수를 부르거나 정렬부터 해야 하면 해시 합집합보다 느리다(이미 정렬돼 있고 연산자로 비교하면 병합이 빠르다). O(n) 힙 짓기는 Push 반복보다 상수 배만 빠르다.
--   결과를 표({ok, value})로 돌려주는 대신 다중 반환(ok, value)이면 할당이 없어 빠르다.
-- 원 수치: stl perf 9절(0.734 -O1, 10만): 정렬 병합 Union 5.9배 느림. 10절: 힙 짓기 vs Push 1.68~1.86배(N 무관).
--   mrow REVIEW(0.734): 결과 표 -> 다중 반환 70~73% 빨라짐(파서 전체).
local Bench = require("./lib/bench")

local N = 100_000
local Cmp = {}
function Cmp.lt(a, b) return a < b end
local rnd = Bench.rng(99)
local A, B = table.create(N), table.create(N)
for i = 1, N do
	A[i] = rnd() % (N * 4)
	B[i] = rnd() % (N * 4)
end
local As, Bs = table.clone(A), table.clone(B)
table.sort(As)
table.sort(Bs)

Bench.run("algo-basics/union", {
	{ name = "해시 합집합", fn = function()
		local set = {}
		for i = 1, N do set[A[i]] = true end
		for i = 1, N do set[B[i]] = true end
		local out, n = table.create(N * 2), 0
		for k in set do n += 1; out[n] = k end
		return out
	end },
	{ name = "정렬된 두 배열 병합(정렬 비용 제외)", fn = function()
		local out, n = table.create(N * 2), 0
		local i, j = 1, 1
		local last = nil
		while i <= N or j <= N do
			local v
			if j > N or (i <= N and As[i] <= Bs[j]) then
				v = As[i]; i += 1
			else
				v = Bs[j]; j += 1
			end
			if v ~= last then n += 1; out[n] = v; last = v end
		end
		return out
	end },
	{ name = "병합, 비교자 함수 lt(a, b) 경유", fn = function()
		local lt = Cmp.lt
		local out, n = table.create(N * 2), 0
		local i, j = 1, 1
		local last = nil
		while i <= N or j <= N do
			local v
			if j > N or (i <= N and not lt(Bs[j], As[i])) then
				v = As[i]; i += 1
			else
				v = Bs[j]; j += 1
			end
			if last == nil or lt(last, v) then n += 1; out[n] = v; last = v end
		end
		return out
	end },
	{ name = "정렬부터(table.sort 둘) + 병합", fn = function()
		local a, b = table.clone(A), table.clone(B)
		table.sort(a)
		table.sort(b)
		local out, n = table.create(N * 2), 0
		local i, j = 1, 1
		local last = nil
		while i <= N or j <= N do
			local v
			if j > N or (i <= N and a[i] <= b[j]) then
				v = a[i]; i += 1
			else
				v = b[j]; j += 1
			end
			if v ~= last then n += 1; out[n] = v; last = v end
		end
		return out
	end },
}, { rounds = 9 })

local function siftDown(h, i, n)
	while true do
		local l = i * 2
		if l > n then return end
		local c = l
		if l + 1 <= n and h[l + 1] < h[l] then c = l + 1 end
		if h[i] <= h[c] then return end
		h[i], h[c] = h[c], h[i]
		i = c
	end
end
local function siftUp(h, i)
	while i > 1 do
		local p = i // 2
		if h[p] <= h[i] then return end
		h[p], h[i] = h[i], h[p]
		i = p
	end
end
Bench.run("algo-basics/heap", {
	{ name = "Push 반복 O(n log n)", fn = function()
		local h = table.create(N)
		for i = 1, N do h[i] = A[i]; siftUp(h, i) end
		return h
	end },
	{ name = "한 번에 짓기 O(n)", fn = function()
		local h = table.clone(A)
		for i = N // 2, 1, -1 do siftDown(h, i, N) end
		return h
	end },
	{ name = "table.sort 전체(참고)", fn = function()
		local h = table.clone(A)
		table.sort(h)
		return h
	end },
}, { rounds = 9 })

local Res = {}
function Res.asTable(i) if i % 7 == 0 then return { false, "bad" } end return { true, i } end
function Res.asMulti(i) if i % 7 == 0 then return false, "bad" end return true, i end
local asTable, asMulti = Res.asTable, Res.asMulti
local RN = 1_000_000
Bench.run("algo-basics/result", {
	{ name = "결과 표 {ok, value}", fn = function()
		local s = 0
		for i = 1, RN do
			local r = asTable(i)
			if r[1] then s += r[2] end
		end
		return s
	end },
	{ name = "다중 반환 ok, value", fn = function()
		local s = 0
		for i = 1, RN do
			local ok, v = asMulti(i)
			if ok then s += v end
		end
		return s
	end },
}, { rounds = 9 })
