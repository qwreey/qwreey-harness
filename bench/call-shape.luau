-- 주장(S-P04, S-P29): 같은 함수라도 호출 모양이 비용을 바꾼다. obj:M() (MT __index 경유) > Mod.M(obj) > local M = Mod.M; M(obj).
--   필드를 바로 읽는 것이 가장 싸다. 테이블에서 함수를 루프 밖에서 꺼내 두면 직접 호출과 같다.
-- 원 수치: stl perf 14절(0.734 -O1, 500만): a:Len() 1.00, Arr.Len(a) 0.82, local 0.64, a.n 0.24.
--   60절(-O1/-O2, 버전 미기재): 메서드 27.4, 모듈 함수 24.1, 지역 20.6ns.
local Bench = require("./lib/bench")
local Arr = require("./lib/arr")

local N = 2_000_000
local a = Arr.new(4)

Bench.run("call-shape/len", {
	{ name = "a:LenM() (MT __index)", fn = function()
		local s = 0
		for _ = 1, N do s += a:LenM() end
		return s
	end },
	{ name = "Arr.Len(a)", fn = function()
		local s = 0
		for _ = 1, N do s += Arr.Len(a) end
		return s
	end },
	{ name = "local Len = Arr.Len", fn = function()
		local Len = Arr.Len
		local s = 0
		for _ = 1, N do s += Len(a) end
		return s
	end },
	{ name = "a.n 직접", fn = function()
		local s = 0
		for _ = 1, N do s += a.n end
		return s
	end },
})
