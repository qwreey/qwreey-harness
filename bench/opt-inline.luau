-- 주장(S-P26, S-P31, S-P22, S-P24): 최적화 수준이 '무엇이 공짜인가'를 바꾼다.
--   -O2 는 같은 파일의 루프 없는 지역 함수를 호출 지점에 인라인해 호출 비용을 없앤다. 다른 모듈의 함수, 필드 대입으로 만든
--   함수, 루프가 있는 함수는 인라인되지 않는다. 타입 캐스트 :: 는 런타임 비용이 없다.
--   한 명령 자리가 칸 배치가 다른 표들을 번갈아 보면 상수 키 필드(t.Name)의 인라인 캐시가 빗나간다(번호 t[i] 는 그대로).
--   다른 모듈에서 받은 문자열 상수로 t[K] = v 하면 상수 키 명령을 못 써서 리터럴보다 느리다.
-- 원 수치: stl perf 55절(-O2): 지역 함수 인라인 0ns. 31절 "::" 22.2~24.2 → 22.3~23.5ns. 44절(-O2): 표 넷을 번갈아 t.Name 6.5 vs t[i] 4.6ns.
--   21절(-O2): const TYPE_KEY = Trait.TYPE_KEY 로 raw[TYPE_KEY] = TOKEN 하면 생성 7~11% 느림.
local Bench = require("./lib/bench")
local Arr = require("./lib/arr")
local C = require("./lib/consts")

local N = 2_000_000
local function lenLocal(a) return a.n end
local a = Arr.new(4)
Bench.run("opt-inline/call", {
	{ name = "a.n 직접", fn = function()
		local s = 0
		for _ = 1, N do s += a.n end
		return s
	end },
	{ name = "같은 파일 지역 함수 lenLocal(a)", fn = function()
		local s = 0
		for _ = 1, N do s += lenLocal(a) end
		return s
	end },
	{ name = "다른 모듈 함수(local 로 받음)", fn = function()
		local Len = Arr.Len
		local s = 0
		for _ = 1, N do s += Len(a) end
		return s
	end },
	{ name = "lenLocal(a :: any) 캐스트", fn = function()
		local s = 0
		for _ = 1, N do s += lenLocal(a :: any) end
		return s
	end },
})

-- 인라인 캐시: 한 자리에서 표 넷을 번갈아 본다
local function mk(extra: number, i: number)
	local t: any = {}
	for k = 1, extra do t["pad" .. k] = k end
	t.Name = i
	t[1] = i
	return t
end
local one = { mk(0, 1), mk(0, 1), mk(0, 1), mk(0, 1) }
local mixed = { mk(0, 1), mk(7, 1), mk(40, 1), mk(150, 1) }
local function readName(ts)
	local s = 0
	for i = 1, N do s += ts[i % 4 + 1].Name end
	return s
end
local function readSlot(ts)
	local s = 0
	for i = 1, N do s += ts[i % 4 + 1][1] end
	return s
end
Bench.run("opt-inline/ic-name", {
	{ name = "같은 모양 표 넷 t.Name", fn = function() return readName(one) end },
	{ name = "모양 다른 표 넷 t.Name", fn = function() return readName(mixed) end },
})
Bench.run("opt-inline/ic-slot", {
	{ name = "같은 모양 표 넷 t[1]", fn = function() return readSlot(one) end },
	{ name = "모양 다른 표 넷 t[1]", fn = function() return readSlot(mixed) end },
})

local KEY = C.KEY
local CN = 1_000_000
Bench.run("opt-inline/const-key", {
	{ name = 't["__type"] 리터럴', fn = function()
		local last
		for i = 1, CN do
			local t = { n = i }
			t["__type"] = true
			last = t
		end
		return last
	end },
	{ name = "t[KEY] (다른 모듈 상수)", fn = function()
		local last
		for i = 1, CN do
			local t = { n = i }
			t[KEY] = true
			last = t
		end
		return last
	end },
}, { rounds = 9 })
