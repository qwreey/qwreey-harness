-- 주장(S-P03): table.move 는 C 에서 raw 로 복사해 메타메서드를 보지 않는다. 원소 루프 복사는 몇 배 느리고, MT 가 있으면 더 느리다.
-- 원 수치: stl perf 2절(0.734 -O1, 100만): 손 루프 7.6x(MT 없음) / 14.3x(MT 있음).
-- 근거(소스): VM/src/ltablib.cpp tmove/moveelements 는 array 를 직접 복사하거나 lua_rawgeti/lua_rawseti 를 쓴다.
local Bench = require("./lib/bench")

local N = 1_000_000
local src = table.create(N, 1)
local srcMt = setmetatable(table.create(N, 1), {})

Bench.run("tbl-move/copy", {
	{ name = "table.move", fn = function()
		return table.move(src, 1, N, 1, table.create(N))
	end },
	{ name = "table.move, MT 원본", fn = function()
		return table.move(srcMt, 1, N, 1, table.create(N))
	end },
	{ name = "손 루프", fn = function()
		local s, d = src, table.create(N)
		for i = 1, N do d[i] = s[i] end
		return d
	end },
	{ name = "손 루프, MT 원본·대상", fn = function()
		local s, d = srcMt, setmetatable(table.create(N), {})
		for i = 1, N do d[i] = s[i] end
		return d
	end },
	{ name = "table.clone", fn = function()
		return table.clone(src)
	end },
}, { rounds = 9 })
