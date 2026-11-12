-- 주장(S-P48): 결과 크기를 알면 table.create(n) 으로 미리 잡는다(작은 n 에서 효과가 크고 큰 n 에서는 작다).
--   크기 필드를 원소마다 올리기보다 지역 변수로 세고 끝에 한 번 쓰는 쪽이 빠르다.
-- 원 수치: stl perf 28절(-O2): N=10 에서 0.45→0.33us(0.73x), 크면 차이 없음. 33절: size 필드 매번 갱신 1.16~1.18x.
local Bench = require("./lib/bench")

local function fill(make: (number) -> { number }, n: number, reps: number)
	return function()
		local last
		for _ = 1, reps do
			local t = make(n)
			for i = 1, n do t[i] = i end
			last = t
		end
		return last
	end
end
local function empty(_n: number): { number } return {} end
local function created(n: number): { number } return table.create(n) end

Bench.run("tbl-prealloc/n10", {
	{ name = "{} 에 10개", fn = fill(empty, 10, 100_000) },
	{ name = "table.create(10)", fn = fill(created, 10, 100_000) },
})
Bench.run("tbl-prealloc/n10000", {
	{ name = "{} 에 1만개", fn = fill(empty, 10_000, 100) },
	{ name = "table.create(10000)", fn = fill(created, 10_000, 100) },
})

local KEYS = 1000
local names = {}
for k = 1, KEYS do names[k] = "k" .. (k % 500) end
Bench.run("tbl-prealloc/size-field", {
	{ name = "지역으로 세고 끝에 한 번", fn = function()
		local last
		for _ = 1, 300 do
			local m = { data = {}, size = 0 }
			local data, size = m.data, 0
			for k = 1, KEYS do
				local key = names[k]
				if data[key] == nil then size += 1 end
				data[key] = k
			end
			m.size = size
			last = m
		end
		return last
	end },
	{ name = "새 키마다 m.size += 1", fn = function()
		local last
		for _ = 1, 300 do
			local m = { data = {}, size = 0 }
			local data = m.data
			for k = 1, KEYS do
				local key = names[k]
				if data[key] == nil then m.size += 1 end
				data[key] = k
			end
			last = m
		end
		return last
	end },
}, { rounds = 9 })
