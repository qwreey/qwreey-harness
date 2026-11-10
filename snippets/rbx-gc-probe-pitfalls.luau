--!strict
--@run
-- 주장: GC 프로브가 스스로 결론을 바꾸는 함정 둘.
--   (1) 클로저가 키를 업밸류로 잡는 누수를 보이려다 "다른 참조를 지운다"며 그 지역 변수를 nil 로 만들면, 클로저가 잡은 바로 그
--       업밸류가 비워져 항목이 수거된다. 누수가 없어 보이지만 실험이 틀렸다. 키는 따로 복사한 업밸류로 잡게 해야 한다.
--   (2) 업밸류가 반복마다 바뀌지 않는 클로저는 Luau 가 캐시해 반복마다 같은 객체다. 그래서 "만든 N 개 중 1 개가 남았다"처럼 보인다.
--       반복 변수를 캡처하면 매번 새 클로저다.
-- 근거: quad .claude/audit/tween-completed-2026-09-21/REPORT.md:25-31,43-44 (Q-123); quad .claude/audit/round13-e42-gc-sweep/README.md:92-93 (Q-005)
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

-- (1) 잘못된 프로브: 포획 변수를 nil 로 지운다
local wrong = setmetatable({}, { __mode = "k" })
do
	local k: {}? = {}
	wrong[k :: {}] = function()
		return k
	end
	k = nil -- 클로저가 잡은 업밸류 자체를 비웠다
end
fullgc()
assert(count(wrong) == 0, "probe bug: the 'leak' disappears because the upvalue itself was cleared")

-- (1) 맞는 프로브: 키를 별도 업밸류로 복사해 잡게 하고, 바깥 변수만 지운다
local right = setmetatable({}, { __mode = "k" })
do
	local k: {}? = {}
	local held = k
	right[k :: {}] = function()
		return held
	end
	k = nil
end
fullgc()
assert(count(right) == 1, "real probe: the back-reference keeps the entry")

-- (2) 클로저 캐시
local distinct = setmetatable({}, { __mode = "k" })
local cached = {}
for i = 1, 5 do
	local f = function() end -- 업밸류 없음 → 같은 객체
	distinct[f] = true
	cached[i] = f
end
assert(count(distinct) == 1 and rawequal(cached[1], cached[5]), "closure without changing upvalues is reused")
local fresh = setmetatable({}, { __mode = "k" })
local keepFresh = {}
for i = 1, 5 do
	local f = function()
		return i
	end
	fresh[f] = true
	keepFresh[i] = f
end
assert(count(fresh) == 5, "capturing the loop variable creates a new closure each time")
print("ok")
