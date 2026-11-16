--!strict
--@run
-- 주장: (1) `__mode = "v"` 표는 키를 강하게 잡는다. 값만 약하다. (2) `__mode` 오타(`__mod`)는 아무 경고 없이 강한 표가 된다.
--       (3) 값이 약한 배열은 원소가 수거되면 구멍이 생겨 ipairs 가 일찍 멈춘다. 약한 집합은 `{ [obj] = true }` + `__mode = "k"` 로 둔다.
--       (4) `:Wait()` 처럼 멈춘 코루틴은 스택의 지역을 강하게 잡는다. weak-key 표의 값이 그 코루틴을 잡으면 키가 고정된다.
-- 근거: quad docs/quadnomicon/03-luau-memory-topology.md:113-117, .claude/base/lifecycle-pattern.md:130-131 (Q-002);
--       quad .claude/base/blocker-plan.md:123-127 (Q-008); rbvm .claude/review/2026-10-05-code-review.md:573-574 (R-23)
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

local tracker = setmetatable({}, { __mode = "k" }) -- 살아 있는 객체를 세는 약한 추적자

-- (1) weak-value 표의 키는 강하다
local wv = setmetatable({}, { __mode = "v" })
local keepValue = {}
local function fillWv()
	local key = {}
	tracker[key] = true
	wv[key] = keepValue -- 값은 다른 곳에서 살아 있다
end
fillWv()
fullgc()
assert(count(tracker) == 1, "__mode=v keeps the key alive")
assert(count(wv) == 1)

-- (2) 오타 __mod 는 강한 표
local typo = setmetatable({}, { __mod = "k" } :: any)
local function fillTypo()
	typo[{}] = true
end
fillTypo()
fullgc()
assert(count(typo) == 1, "__mod typo silently makes a strong table")

-- (3) 값이 약한 배열의 구멍
local arr = setmetatable({}, { __mode = "v" })
local keep1, keep3 = {}, {}
local function fillArr()
	arr[1] = keep1
	arr[2] = {} -- 다른 참조가 없다
	arr[3] = keep3
end
fillArr()
fullgc()
local seen = 0
for _i, _v in ipairs(arr :: any) do -- 루프 변수를 하나만 두면 새 솔버가 엉뚱한 "Argument count mismatch" 를 낸다(0.734~0.746)
	seen += 1
end
assert(arr[2] == nil and arr[3] == keep3, "middle element collected, hole left")
assert(seen == 1, "ipairs stops at the hole")

-- (4) 멈춘 코루틴의 스택이 키를 잡는다
local waiting = setmetatable({}, { __mode = "k" })
local function park()
	local sig = {}
	local th = coroutine.create(function(s)
		coroutine.yield() -- `sig:Wait()` 처럼 멈춘다. 스택에 s 가 있다
		return s
	end)
	coroutine.resume(th, sig)
	waiting[sig] = { th } -- 값이 코루틴을 잡는다 -> 코루틴 스택이 키를 잡는다
end
park()
fullgc()
assert(count(waiting) == 1, "parked coroutine pins the weak key")
print("ok")
