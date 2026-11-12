--!strict
--@run
--@run-opt=2
-- 주장: luau CLI 에서 weak 표 정리는 collectgarbage("collect") 로 검증할 수 있다. 판정은 KB 가 아니라 weak-key 추적자에 남은
--   **객체 수**로 하고, 수렴할 때까지 여러 번 돌린다(fullgc). 프로브 함정: 테스트 쪽 기록 표가 대상을 강하게 쥐면 "누수"로 보인다.
--   타입 검사기(luau-analyze)는 collectgarbage 를 모른다(Roblox 정의 기준이라 'Unknown global'). 런타임에는 있다 → `(_G :: any)` 로 꺼낸다.
--   Roblox 의 GC 와 같다는 보장은 없다(순수 Luau 수준의 사실로만 쓴다. Roblox 일부 컨텍스트는 "collect" 를 거부한다).
-- 근거: 원천 quad/.claude/audit/round13-e42-gc-sweep/README.md:10-13(fullgc·잔여 수 판정), quad/.claude/audit/tween-completed-2026-09-21/REPORT.md:43-44,
--   rbvm/.claude/review/2026-10-05-sibling-repos.md:120-122, quad/quad-base/test/spec.errorutil.luau:18-19, 후보 Q-122·Q-123·R-48·Q-011
local _bad = collectgarbage("count") -- expect-error: Unknown global 'collectgarbage'
local gc = (_G :: any).collectgarbage :: (string) -> number

local function fullgc()
	local prev = gc("count")
	for i = 1, 12 do
		gc("collect")
		local cur = gc("count")
		if i >= 3 and math.abs(cur - prev) < 0.5 then
			break
		end
		prev = cur
	end
end

local function alive(tracker: { [any]: true }): number
	local n = 0
	for _ in tracker do
		n += 1
	end
	return n
end

-- 정상: 참조를 놓은 객체는 수거된다
local tracker = setmetatable({} :: { [any]: true }, { __mode = "k" })
do
	local obj = {}
	tracker[obj] = true
end
fullgc()
assert(alive(tracker) == 0, `잔여 {alive(tracker)}`)

-- 함정: 하네스의 로그 표가 대상을 강하게 쥐면 남는다(대상의 누수가 아니라 프로브의 누수)
local log = {}
do
	local obj = {}
	tracker[obj] = true
	table.insert(log, obj)
end
fullgc()
assert(alive(tracker) == 1, "로그 표가 쥔 객체는 남는다")
table.clear(log)
fullgc()
assert(alive(tracker) == 0, "로그를 비우면 수거된다")
print("ok")
