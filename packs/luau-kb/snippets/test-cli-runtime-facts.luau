--!strict
--@run
-- 주장: 순수 luau CLI 를 테스트 러너로 쓸 때의 환경 사실.
--   - Roblox 전역(task, game, Instance, Vector3, Enum)과 io·fs·warn 이 없다. getfenv, debug.info, buffer, vector 는 있다.
--   - 그래서 엔진 전역을 모듈 **최상위**(로드 시점)에서 건드리는 모듈은 CLI 에서 require 하는 순간 죽는다.
--     공용 모듈은 로드 시점에 엔진 값을 참조하지 않고 호출 시점으로 미룬다.
--   - assert(cond, 테이블) 은 테이블을 던지지 않는다. error(테이블) 은 그 테이블을 그대로 던진다.
-- 근거: luau 0.734·0.742 실행, 원천 claude-doctor .claude/archive/research/drafts/gaps/testing.md §4, devplorer/.claude/conventions.md:53,67, tbox/CLAUDE.md:149-154,
--   stl-luau/.claude/base/architecture.md:9-13, 후보 D-C03·S-127·Q-070·Q-118
local G = _G :: any
for _, name in { "task", "game", "Instance", "Vector3", "Enum", "io", "fs", "warn" } do
	assert(G[name] == nil, `{name} 이 있으면 안 된다`)
end
for _, name in { "getfenv", "debug", "buffer", "vector", "collectgarbage" } do
	assert(G[name] ~= nil, `{name} 이 있어야 한다`)
end

-- 로드 시점에 엔진 전역을 쓰는 모듈 흉내(모듈 몸통 = 함수 호출)
local function loadTimeEngine()
	local zero = G.Vector3.new(0, 0, 0) -- CLI 에서 nil 인덱싱
	return { zero = zero }
end
local function callTimeEngine()
	return {
		zero = function()
			return G.Vector3.new(0, 0, 0)
		end,
	}
end
assert(not pcall(loadTimeEngine), "로드 시점 참조는 CLI 에서 죽는다")
assert(pcall(callTimeEngine), "호출 시점으로 미루면 로드는 된다")
print("ok")
