--!strict
--@run
-- 주장: Luau 의 weak-key 표(`__mode = "k"`)는 ephemeron 이 아니다. 값이 자기 키를 강하게 잡으면(직접 필드, 클로저 업밸류)
--       그 항목은 키에 대한 다른 참조가 다 사라져도 수거되지 않는다. 두 weak-key 표의 값이 서로의 키를 잡는 순환도 영구 누수다.
--       대조군(값이 키를 잡지 않음)은 수거된다. 값이 키를 잡지 않게 하려면 사설 데이터를 키 객체 자신에 둔다.
-- 근거: luau.org/compatibility "Ephemeron tables" 미지원; quad .claude/audit/tween-completed-2026-09-21/REPORT.md:25-28,
--       rbvm .claude/review/2026-10-05-repro/L7_no_ephemeron_signal_leak.luau:1-3,14-17 (audit/08 Q-001, audit/09 R-22)
-- luau-analyze 의 내장 정의에는 collectgarbage 가 없다. 런타임 전역에서 꺼낸다.
local collectgarbage: (string) -> any = (_G :: any).collectgarbage
local function fullgc()
	for _ = 1, 4 do
		collectgarbage("collect")
	end
end

local function count(t: { [any]: any }): number
	local n = 0
	for _ in t do
		n += 1
	end
	return n
end

local N = 50

-- 1) 값이 키를 직접 잡는다
local direct = setmetatable({}, { __mode = "k" })
-- 2) 값이 키를 클로저 업밸류로 잡는다
local viaClosure = setmetatable({}, { __mode = "k" })
-- 3) 대조군: 값이 키를 잡지 않는다
local control = setmetatable({}, { __mode = "k" })
-- 4) 두 weak-key 표의 상호 참조 순환
local mapA = setmetatable({}, { __mode = "k" })
local mapB = setmetatable({}, { __mode = "k" })

local function fill()
	for i = 1, N do
		local k1 = {}
		direct[k1] = { back = k1 }
		local k2 = {}
		viaClosure[k2] = function()
			return k2
		end
		control[{}] = { i = i }
		local a, b = {}, {}
		mapA[a] = { other = b }
		mapB[b] = { other = a }
	end
end
fill() -- 지역 변수가 키를 잡지 않도록 채우기는 별도 함수에서 한다
fullgc()

assert(count(control) == 0, "control should be collected")
assert(count(direct) == N, "direct back-reference: entries survive (no ephemeron)")
assert(count(viaClosure) == N, "closure upvalue back-reference: entries survive")
assert(count(mapA) == N and count(mapB) == N, "cross-map cycle: entries survive")

-- 처방: 값을 지우면(명시적으로 끊으면) 수거된다
for k in direct do
	direct[k] = nil
end
fullgc()
assert(count(direct) == 0)
print("ok", N)
