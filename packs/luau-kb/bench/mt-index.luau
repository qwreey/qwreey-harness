-- 주장(S-P01, S-P02, S-P32): 메타테이블이 붙은 테이블 '자신의' 정수 키 칸 t[i] 읽기, 쓰기는 MT 가 있기만 해도 느리다.
--   빈 MT, __index MT, freeze, rawget 모두 같다. 상수 문자열 필드(o.n)와 MT 없는 안쪽 표(o.data[i])는 영향이 없다.
-- 원 수치: stl perf-measurements.md 1절(0.734 -O1, 200만 합, 최소값) 1.59x. 18절: -O1 1.60x, -O2 1.66~1.81x, codegen -O2 1.96~2.00x.
--   16절(-O2): MT 제거 시 읽기 0.63x, 쓰기 0.58x. 60절: o.n, o.data[i] 는 MT 무관.
-- 원인(소스): Luau 0.742 VM/src/lvmexecute.cpp GETTABLE/SETTABLE/GETTABLEN/SETTABLEN 빠른 경로가 !h->metatable 을 요구한다.
local Bench = require("./lib/bench")

local N = 1_000_000

local function filled(): { number }
	local t = table.create(N)
	for i = 1, N do
		t[i] = i % 7
	end
	return t
end

local plain = filled()
local emptyMt = setmetatable(filled(), {})
local indexMt = setmetatable(filled(), { __index = function() return 0 end })
local frozenMt = table.freeze(setmetatable(filled(), table.freeze({})))

local function sumOf(t: { number }): number
	local acc = 0
	for i = 1, N do
		acc += t[i]
	end
	return acc
end

-- 읽기: 같은 루프 함수에 표만 바꿔 넣는다
Bench.run("mt-index/read", {
	{ name = "plain t[i]", fn = function() return sumOf(plain) end },
	{ name = "empty MT", fn = function() return sumOf(emptyMt) end },
	{ name = "__index MT", fn = function() return sumOf(indexMt) end },
	{ name = "frozen + MT", fn = function() return sumOf(frozenMt) end },
	{
		name = "rawget on MT",
		fn = function()
			local t = emptyMt
			local acc = 0
			for i = 1, N do
				acc += rawget(t, i)
			end
			return acc
		end,
	},
})

local wPlain = filled()
local wMt = setmetatable(filled(), {})
local function bump(t: { number }): number
	for i = 1, N do
		t[i] = t[i] + 1
	end
	return t[1]
end

Bench.run("mt-index/write", {
	{ name = "plain t[i] = t[i] + 1", fn = function() return bump(wPlain) end },
	{ name = "empty MT", fn = function() return bump(wMt) end },
})

-- 상수 문자열 필드와 안쪽 표: MT 세금이 없어야 한다
type Obj = { n: number, data: { number } }
local oPlain: Obj = { n = 3, data = filled() }
local oMt: Obj = setmetatable({ n = 3, data = filled() }, { __index = {} }) :: any

local function fieldLoop(o: Obj): number
	local acc = 0
	for _ = 1, N do
		acc += o.n
	end
	return acc
end

Bench.run("mt-index/field", {
	{ name = "plain o.n", fn = function() return fieldLoop(oPlain) end },
	{ name = "MT o.n", fn = function() return fieldLoop(oMt) end },
})

local function innerLoop(o: Obj): number
	local data = o.data
	local acc = 0
	for i = 1, N do
		acc += data[i]
	end
	return acc
end

Bench.run("mt-index/inner", {
	{ name = "plain o.data[i]", fn = function() return innerLoop(oPlain) end },
	{ name = "MT outer, o.data[i]", fn = function() return innerLoop(oMt) end },
})
