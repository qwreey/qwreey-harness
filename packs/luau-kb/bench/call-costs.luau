-- 주장(S-P30, Q-087): 호출 한 번의 바닥값 — 평범한 호출 < pcall < coroutine 생성+resume.
--   인자를 매 호출 새 표로 넘기면 위치 인자보다 비싸고, 재사용 표에 매번 table.clear 하는 것은 새 표보다도 느리다.
-- 원 수치: stl perf 13절(0.734 -O1): 호출 0.012us, pcall 0.037us, coroutine 0.174us.
--   quad updatefn-ctx-table-bench(0.734, 200만, 중앙값 5회) ns: 위치 25.1/16.8/8.7(-O1/-O2/-O2 codegen), 새 표 76.0/68.3/55.4,
--   재사용 표 47.5/37.8/28.6, 재사용+clear 92.0/81.0/83.4.
local Bench = require("./lib/bench")
local F = require("./lib/vfuncs")

local N = 1_000_000
local function body(x) return x end
Bench.run("call-costs/base", {
	{ name = "f(x)", fn = function()
		local f = F.pushFixed
		local o = { n = 0 }
		for i = 1, N // 5 do f(o, i) end
		return o.n
	end },
	{ name = "pcall(f, x)", fn = function()
		local f = F.pushFixed
		local o = { n = 0 }
		for i = 1, N // 5 do pcall(f, o, i) end
		return o.n
	end },
	{ name = "coroutine.create + resume", fn = function()
		local s = 0
		for i = 1, N // 5 do
			local co = coroutine.create(body)
			local _, v = coroutine.resume(co, i)
			s += v
		end
		return s
	end },
}, { rounds = 9 })

local Ctx = {}
function Ctx.positional(a, b, c) return a + b + c end
function Ctx.tableArg(t) return t.a + t.b + t.c end
local positional, tableArg = Ctx.positional, Ctx.tableArg
Bench.run("call-costs/arg-shape", {
	{ name = "위치 인자 f(a, b, c)", fn = function()
		local s = 0
		for i = 1, N do s += positional(i, 2, 3) end
		return s
	end },
	{ name = "매 호출 새 표 f({a=,b=,c=})", fn = function()
		local s = 0
		for i = 1, N do s += tableArg({ a = i, b = 2, c = 3 }) end
		return s
	end },
	{ name = "재사용 표(필드만 덮어씀)", fn = function()
		local s = 0
		local t = { a = 0, b = 0, c = 0 }
		for i = 1, N do
			t.a, t.b, t.c = i, 2, 3
			s += tableArg(t)
		end
		return s
	end },
	{ name = "재사용 표 + 매번 table.clear", fn = function()
		local s = 0
		local t = { a = 0, b = 0, c = 0 }
		for i = 1, N do
			table.clear(t)
			t.a, t.b, t.c = i, 2, 3
			s += tableArg(t)
		end
		return s
	end },
}, { rounds = 9 })
