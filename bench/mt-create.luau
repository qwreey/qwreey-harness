-- 주장(S-P05): setmetatable 하나는 작은 객체 생성에 조금 더할 뿐이다. 메서드를 인스턴스마다 복사하면 생성과 메모리가 크게 는다.
-- 원 수치: stl perf 1-부(0.734 -O1): 메서드 54개 복사 시 20만 개 생성 20.4배, 인스턴스당 96 B vs 2112 B(22배).
--   60절: {n=0,data={}} 50ns 에 setmetatable +14~21ns.
local Bench = require("./lib/bench")

local N = 50_000
local methods = {}
for i = 1, 54 do
	methods["m" .. i] = function(self) return i end
end
local Mt = { __index = methods }

Bench.run("mt-create/time", {
	{ name = "{n,data} 맨 표", fn = function()
		local last
		for i = 1, N do last = { n = 0, data = {} } end
		return last
	end },
	{ name = "+ setmetatable", fn = function()
		local last
		for i = 1, N do last = setmetatable({ n = 0, data = {} }, Mt) end
		return last
	end },
	{ name = "메서드 54개 복사", fn = function()
		local last
		for i = 1, N do
			local o = { n = 0, data = {} }
			for k, f in methods do o[k] = f end
			last = o
		end
		return last
	end },
}, { rounds = 9 })

Bench.mem("mt-create/mem", "작은 배열 + 빈 MT", 20_000, function(i) return setmetatable({ i, i }, Mt) end)
Bench.mem("mt-create/mem", "작은 배열, MT 없음", 20_000, function(i) return { i, i } end)
Bench.mem("mt-create/mem", "작은 배열 + 메서드 54개 복사", 20_000, function(i)
	local o = { i, i }
	for k, f in methods do o[k] = f end
	return o
end)
