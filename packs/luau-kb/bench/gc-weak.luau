-- 주장(S-P36, S-P35, Q-089): 약한 키 표의 비용.
--   (1) 정체성을 약한 키 레지스트리(reg[obj] = true)로 매기면 작은 객체를 만드는 경로가 문자열 태그 필드보다 느리다. 조회만 보면 싸다.
--   (2) 살아 있는 객체가 많을 때 약한 표가 있으면 전체 GC 가 더 든다.
--   (3) 뜨거운 경로에서 약한 표 조회 앞에 type(v) == "table" 을 두면 원시값은 조회를 건너뛴다.
-- 원 수치: stl perf 18절(0.734 -O1): Arr.Of ×100만 태그 100.6~107.8 vs 레지스트리 199.6~208.6ms(~1.9x), Clone 1.66x, 20만 생존 시 풀 GC 2~3.7배.
--   quad brand-plan: "포인터 해싱 한 번, 무시할 만"(조회 관점). quad round14 expensive-checks(-O2, 9회 최소): Set 0.107 → 0.069us.
local Bench = require("./lib/bench")

local N = 200_000
local registry = setmetatable({}, { __mode = "k" })

Bench.run("gc-weak/create", {
	{ name = "문자열 태그 {__type = true}", fn = function()
		local last
		for i = 1, N do last = { i, i, __type = true } end
		return last
	end },
	{ name = "약한 키 레지스트리 등록", fn = function()
		local last
		local reg = registry
		for i = 1, N do
			local o = { i, i }
			reg[o] = true
			last = o
		end
		return last
	end },
}, { rounds = 9 })

-- 판정 경로(조회만)
local tagged = { 1, 2, __type = true }
local registered = { 1, 2 }
registry[registered] = true
local LN = 2_000_000
Bench.run("gc-weak/check", {
	{ name = "o.__type == true", fn = function()
		local c, o = 0, tagged
		for _ = 1, LN do if o.__type == true then c += 1 end end
		return c
	end },
	{ name = "reg[o] 조회", fn = function()
		local c, o, reg = 0, registered, registry
		for _ = 1, LN do if reg[o] then c += 1 end end
		return c
	end },
})

-- 원시값이 섞인 입력: type 선검사
local mixed = {}
for i = 1, 1000 do mixed[i] = if i % 10 == 0 then registered else i end
Bench.run("gc-weak/precheck", {
	{ name = "reg[v] 바로", fn = function()
		local c, reg = 0, registry
		for _ = 1, 1000 do
			for i = 1, 1000 do if reg[mixed[i]] then c += 1 end end
		end
		return c
	end },
	{ name = 'type(v) == "table" and reg[v]', fn = function()
		local c, reg = 0, registry
		for _ = 1, 1000 do
			for i = 1, 1000 do
				local v = mixed[i]
				if type(v) == "table" and reg[v] then c += 1 end
			end
		end
		return c
	end },
})

-- 풀 GC 시간: 20만 개가 살아 있을 때, 약한 표에 등록했는가
local aliveTagged, aliveReg
Bench.run("gc-weak/full-gc", {
	{ name = "20만 생존, 태그 필드", setup = function()
		aliveReg = nil
		aliveTagged = table.create(N)
		for i = 1, N do aliveTagged[i] = { i, __type = true } end
		return nil
	end, fn = function()
		collectgarbage("collect")
		return nil
	end },
	{ name = "20만 생존, 약한 키 표에 등록", setup = function()
		aliveTagged = nil
		local reg = setmetatable({}, { __mode = "k" })
		aliveReg = { reg = reg, list = table.create(N) }
		for i = 1, N do
			local o = { i }
			reg[o] = true
			aliveReg.list[i] = o
		end
		return nil
	end, fn = function()
		collectgarbage("collect")
		return nil
	end },
}, { rounds = 9, gc = false })

-- __mode = "k" 와 "ks": 많이 넣었다 버린 뒤 남는 메모리(표 칸 수)
local function churn(mode: string)
	return function(_i)
		local t = setmetatable({}, { __mode = mode })
		local keep = {}
		for j = 1, 20_000 do
			local k = {}
			t[k] = true
			if j % 100 == 0 then keep[#keep + 1] = k end
		end
		keep = nil
		collectgarbage("collect")
		collectgarbage("collect")
		-- 넣은 키 대부분이 수거된 뒤 표 하나가 차지하는 메모리
		return t
	end
end
Bench.mem("gc-weak/mem", '__mode = "k" (2만 넣고 버린 표 하나)', 1, churn("k"))
Bench.mem("gc-weak/mem", '__mode = "ks" (같은 일)', 1, churn("ks"))
