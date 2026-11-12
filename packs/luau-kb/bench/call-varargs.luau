-- 주장(S-P08, S-P09): 가변 인자는 호출마다 값이 든다. 원소마다 select("#", ...) 헬퍼를 부르면 루프가 크게 느려진다(한 번만 센다).
--   인자를 표로 모을 때 {...} 와 table.pack 의 차이, select(i, ...) 루프가 인자 수에 대해 O(n^2) 인 점.
-- 원 수치: stl perf 7절(0.734 -O1, 500만×3): (self, first, ...) +8.2%, (self, ...) +12.6%; "select 루프 vs table.pack 1.6~2.3배 빠름"(방향 모호).
--   19절(-O2): 원소마다 countReturns 2.1x. 57절(0.742 -O2): {...} 는 32 인자까지 table.pack 보다 0.80~0.99x, 1024 인자 1.12x.
local Bench = require("./lib/bench")
local Mod = require("./lib/vfuncs")

local N = 2_000_000
local obj = { n = 0 }
Bench.run("call-varargs/push", {
	{ name = "push(self, v) 고정", fn = function()
		local f = Mod.pushFixed
		for i = 1, N do f(obj, i) end
		return obj.n
	end },
	{ name = "push(self, first, ...)", fn = function()
		local f = Mod.pushFirst
		for i = 1, N do f(obj, i) end
		return obj.n
	end },
	{ name = "push(self, ...)", fn = function()
		local f = Mod.pushVar
		for i = 1, N do f(obj, i) end
		return obj.n
	end },
})

local function countReturns(...) return select("#", ...) end
local src = table.create(200_000, 1)
Bench.run("call-varargs/count", {
	{ name = "같은 루프, 헬퍼 없이", fn = function()
		local c = 0
		local it, st, ctl = ipairs(src)
		while true do
			local k, v = it(st, ctl)
			if k == nil then break end
			ctl = k
			c += v
		end
		return c
	end },
	{ name = "원소마다 select('#') 헬퍼", fn = function()
		local c = 0
		local it, st, ctl = ipairs(src)
		while true do
			local k, v = it(st, ctl)
			if countReturns(k, v) == 0 or k == nil then break end
			ctl = k
			c += v
		end
		return c
	end },
	{ name = "ipairs 그대로", fn = function()
		local c = 0
		for _, v in ipairs(src) do c += v end
		return c
	end },
})

for _, nargs in { 4, 32, 256 } do
	local args = table.create(nargs, 1)
	local reps = 400_000 // nargs
	local function viaBrace(...) local t = { ... } return #t end
	local function viaPack(...) local t = table.pack(...) return t.n end
	local function viaSelect(...)
		local s = 0
		for i = 1, select("#", ...) do s += (select(i, ...)) end
		return s
	end
	Bench.run("call-varargs/collect-" .. nargs, {
		{ name = "{...}", fn = function()
			local s = 0
			for _ = 1, reps do s += viaBrace(table.unpack(args)) end
			return s
		end },
		{ name = "table.pack(...)", fn = function()
			local s = 0
			for _ = 1, reps do s += viaPack(table.unpack(args)) end
			return s
		end },
		{ name = "select(i, ...) 루프", fn = function()
			local s = 0
			for _ = 1, reps do s += viaSelect(table.unpack(args)) end
			return s
		end },
	}, { rounds = 9 })
end
