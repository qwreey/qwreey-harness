-- 주장(S-P10, S-P11): table.sort 는 비교자가 없을 때 가장 빠르다. 3방향 비교자를 불리언으로 감싸 넘기면 한 겹 더 든다.
-- 원 수치: stl perf 5절(0.734 -O1, 20만): 비교자 없음 0.22x, 불리언 lt 1.00, 3방향 래퍼 1.82x. 15절(-O2, 10만) 비교자 없음 0.22~0.27x.
local Bench = require("./lib/bench")

local N = 100_000
local rnd = Bench.rng(12345)
local base = table.create(N)
for i = 1, N do base[i] = rnd() % 1_000_000 end
local function lt(a, b) return a < b end
local function cmp3(a, b) return if a < b then -1 elseif a > b then 1 else 0 end
local function wrapped(a, b) return cmp3(a, b) < 0 end

Bench.run("sort-compare/100k", {
	{ name = "table.sort(t, lt)", setup = function() return table.clone(base) end, fn = function(t) table.sort(t, lt) return t end },
	{ name = "table.sort(t) 비교자 없음", setup = function() return table.clone(base) end, fn = function(t) table.sort(t) return t end },
	{ name = "3방향 비교자 래퍼", setup = function() return table.clone(base) end, fn = function(t) table.sort(t, wrapped) return t end },
}, { rounds = 7 })
