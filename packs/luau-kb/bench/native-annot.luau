-- 주장(native-codegen 초안 5, 6, M-06): 네이티브 코드 생성의 이득은 코드 모양에 달렸다.
--   숫자 연산 위주는 크게 빨라지고, 문자열, 테이블 할당 위주는 10% 안팎이다.
--   인라인되지 않는 호출에서 vector 파라미터 주석이 없으면 네이티브가 오히려 느릴 수 있고, 주석과 다른 타입을 넘기면 느려진다.
--   (파라미터 주석은 -O2 이상 또는 --!native 에서만 쓰인다. -O1 에서는 무시된다.)
-- 원 수치: claude-doctor .claude/archive/research/drafts/gaps/native-codegen.md 5(0.742, 200만 호출, 7회 최소, ms): 주석 없는 vector noinline -O2 51.1 / -O2 codegen 56.3,
--   vector 주석 noinline -O2 49.2 / codegen 24.4; 문자열, 테이블 할당 -O2 67.2 / codegen 64.6.
--   mrow(M-06): 할당 위주 파서 -O2 --codegen 으로 1.40->1.06ms, 7.93->6.93ms(약 10%).
-- 이 파일은 그룹 안의 비율(같은 모드에서 케이스끼리)을 본다. 모드 사이 비교는 요약표의 '기준 ms' 행으로 한다.
local Bench = require("./lib/bench")

local N = 1_000_000
local function untypedVec(v) return v.X * 2 + v.Y * 3 + v.Z end
local function typedVec(v: vector): number return v.X * 2 + v.Y * 3 + v.Z end
-- 필드 대입 표를 거쳐 부르면 -O2 에서도 인라인되지 않는다
local F = {}
F.untypedVec = untypedVec
F.typedVec = typedVec
local vec = vector.create(1, 2, 3)
local tbl = { X = 1, Y = 2, Z = 3 }

Bench.run("native-annot/vector-noinline", {
	{ name = "주석 없음, vector 넘김", fn = function()
		local s = 0
		for _ = 1, N do s += F.untypedVec(vec) end
		return s
	end },
	{ name = "v: vector 주석, vector 넘김", fn = function()
		local s = 0
		for _ = 1, N do s += F.typedVec(vec) end
		return s
	end },
	{ name = "v: vector 주석, 테이블 넘김(불일치)", fn = function()
		local s = 0
		for _ = 1, N do s += F.typedVec(tbl :: any) end
		return s
	end },
	{ name = "주석 없음, 테이블 넘김", fn = function()
		local s = 0
		for _ = 1, N do s += F.untypedVec(tbl) end
		return s
	end },
})

local function num(a, b) return a * b + a - b * 0.5 end
Bench.run("native-annot/kinds", {
	{ name = "숫자 함수(인라인 가능)", fn = function()
		local s = 0
		for i = 1, N do s += num(i, 3) end
		return s
	end },
	{ name = "문자열·테이블 할당", fn = function()
		local n = 0
		for i = 1, N // 4 do
			local t = { tostring(i), "x" }
			n += #table.concat(t)
		end
		return n
	end },
})
