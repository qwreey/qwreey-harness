-- 주장(S-P06, S-P07, S-P16, S-P28): 순회 모양별 비용.
--   배열: 숫자 for, ipairs, 일반화 for(for _, v in t) 의 차이. MT 가 붙은 컨테이너에서는 정수 칸 세금이 순회에 섞인다.
--   해시: 일반화 for > next 삼중항을 돌려주는 함수 > Luau 로 쓴 래퍼 이터레이터.
--   nil 검사 한 줄의 값, 필드를 거친 인덱싱(a.data[i])을 루프 밖 지역으로 빼는 값.
-- 원 수치: stl perf 3절(0.734 -O1, MT 컨테이너 200만): ipairs 0.39x, for i=1,n 1.00, 메서드 이터레이터 2.89, __iter 2.86, 콜백 Fold 2.54.
--   27절(-O2, 1000개 해시): 래퍼 29.0 → next 삼중항 15.9 → 일반화 3.2us. 6절(-O1): if v ~= nil 1.13x. 57절(0.742 -O2): a.data[i] 1.43x.
local Bench = require("./lib/bench")

local N = 1_000_000
local arr = table.create(N, 1)
local mtArr = setmetatable(table.create(N, 1), {})

Bench.run("iter-forms/array", {
	{ name = "for i = 1, n do t[i]", fn = function()
		local s, t = 0, arr
		for i = 1, N do s += t[i] end
		return s
	end },
	{ name = "ipairs", fn = function()
		local s = 0
		for _, v in ipairs(arr) do s += v end
		return s
	end },
	{ name = "일반화 for _, v in t", fn = function()
		local s = 0
		for _, v in arr do s += v end
		return s
	end },
	{ name = "pairs", fn = function()
		local s = 0
		for _, v in pairs(arr) do s += v end
		return s
	end },
	{ name = "숫자 for + if v ~= nil", fn = function()
		local s, t = 0, arr
		for i = 1, N do
			local v = t[i]
			if v ~= nil then s += v end
		end
		return s
	end },
})

Bench.run("iter-forms/mt-array", {
	{ name = "MT 표 for i = 1, n do t[i]", fn = function()
		local s, t = 0, mtArr
		for i = 1, N do s += t[i] end
		return s
	end },
	{ name = "MT 표 ipairs", fn = function()
		local s = 0
		for _, v in ipairs(mtArr) do s += v end
		return s
	end },
	{ name = "MT 표 일반화 for", fn = function()
		local s = 0
		for _, v in mtArr do s += v end
		return s
	end },
	{ name = "MT 표 콜백(Fold 꼴)", fn = function()
		local function fold(t, init, f)
			local acc = init
			for i = 1, N do acc = f(acc, t[i]) end
			return acc
		end
		return fold(mtArr, 0, function(a, v) return a + v end)
	end },
})

local HN = 1000
local hash = {}
for i = 1, HN do hash["k" .. i] = i end
local REPS = 300
local function wrapIter(t)
	local k = nil
	return function()
		local v
		k, v = next(t, k)
		return k, v
	end
end
local function nextTriple(t)
	return next, t, nil
end
Bench.run("iter-forms/hash", {
	{ name = "일반화 for k, v in t", fn = function()
		local s = 0
		for _ = 1, REPS do
			for _, v in hash do s += v end
		end
		return s
	end },
	{ name = "pairs(t)", fn = function()
		local s = 0
		for _ = 1, REPS do
			for _, v in pairs(hash) do s += v end
		end
		return s
	end },
	{ name = "in next, t (리터럴)", fn = function()
		local s = 0
		for _ = 1, REPS do
			for _, v in next, hash do s += v end
		end
		return s
	end },
	{ name = "함수가 돌려준 next, t", fn = function()
		local s = 0
		for _ = 1, REPS do
			for _, v in nextTriple(hash) do s += v end
		end
		return s
	end },
	{ name = "Luau 래퍼 클로저", fn = function()
		local s = 0
		for _ = 1, REPS do
			for _, v in wrapIter(hash) do s += v end
		end
		return s
	end },
})

local holder = { data = table.create(1024, 1) }
Bench.run("iter-forms/hoist", {
	{ name = "local d = a.data; d[i]", fn = function()
		local s = 0
		for _ = 1, 1000 do
			local d = holder.data
			for i = 1, 1024 do s += d[i] end
		end
		return s
	end },
	{ name = "a.data[i] 그대로", fn = function()
		local s = 0
		for _ = 1, 1000 do
			for i = 1, 1024 do s += holder.data[i] end
		end
		return s
	end },
})
