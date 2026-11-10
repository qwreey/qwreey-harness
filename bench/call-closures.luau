-- 주장(S-P10, S-P27, S-P29): 원소마다 클로저 콜백을 부르면 직접 루프보다 몇 배 느리다. 업밸류를 든 클로저는 지역 함수보다 비싸다.
--   함수를 한 겹 감싸면 호출당 값이 붙는다. 표에서 함수를 루프 밖에서 미리 꺼내 두면 직접 호출과 같다.
-- 원 수치: stl perf 22절(-O2): Contains 직접 루프 vs Some(클로저) 0.34x. 55절(-O2): 업밸류 클로저 16.4 vs 지역 8.1ns.
--   48절(-O2): 감싸는 한 겹 13~17ns, 미리 꺼낸 함수 = 직접(59.7 vs 59.8ns).
local Bench = require("./lib/bench")
local F = require("./lib/vfuncs")

local arr = table.create(1000, 1)
arr[1000] = 7
local REPS = 2000

local function contains(t, x)
	for i = 1, #t do
		if t[i] == x then return true end
	end
	return false
end
local function some(t, pred)
	for i = 1, #t do
		if pred(t[i]) then return true end
	end
	return false
end
Bench.run("call-closures/contains", {
	{ name = "직접 루프 contains(t, x)", fn = function()
		local c = 0
		for _ = 1, REPS do if contains(arr, 7) then c += 1 end end
		return c
	end },
	{ name = "some(t, function(v) return v == x end)", fn = function()
		local c = 0
		for _ = 1, REPS do
			local x = 7
			if some(arr, function(v) return v == x end) then c += 1 end
		end
		return c
	end },
})

local N = 2_000_000
local K = 3
local function addLocal(v) return v + 3 end
local function makeAdder(k) return function(v) return v + k end end
local addUp = makeAdder(K)
local Wrap = {}
Wrap.inner = F.pushFixed
function Wrap.outer(o, v) return Wrap.inner(o, v) end
Bench.run("call-closures/upvalue", {
	{ name = "지역 함수(상수)", fn = function()
		local s = 0
		for i = 1, N do s += addLocal(i) end
		return s
	end },
	{ name = "업밸류 클로저", fn = function()
		local s = 0
		for i = 1, N do s += addUp(i) end
		return s
	end },
})
local T = { f = F.pushFixed }
Bench.run("call-closures/wrap", {
	{ name = "직접 F.pushFixed 미리 꺼냄", fn = function()
		local o, f = { n = 0 }, F.pushFixed
		for i = 1, N do f(o, i) end
		return o.n
	end },
	{ name = "루프 안에서 T.f(o, i)", fn = function()
		local o = { n = 0 }
		for i = 1, N do T.f(o, i) end
		return o.n
	end },
	{ name = "감싼 한 겹 Wrap.outer", fn = function()
		local o, f = { n = 0 }, Wrap.outer
		for i = 1, N do f(o, i) end
		return o.n
	end },
})
