--!strict
--@run
-- 주장: coroutine.resume 은 코루틴 안의 에러를 던지지 않고 (false, err) 로 돌려준다. 반환값을 보지 않으면 에러가 조용히 사라진다.
--       전파하려면 `if not ok then error(err, 0) end`. 죽은 코루틴을 다시 resume 하면 (false, "cannot resume dead coroutine").
-- 근거: quad .claude/archive/v2-initial-implementation/m2-implementation-round11.md:122-128, .claude/base/ref-plan.md:314-325(H-170 실버그).
--       후보 Q-066. 의미론 정본은 luau-runtime coroutines.md 1, Roblox task.spawn 쪽 동작은 roblox-engine 담당.
local co = coroutine.create(function()
	error("in co")
end)
coroutine.resume(co) -- 나쁜 예: 반환값을 버리면 아무 일도 없었던 것처럼 지나간다
local ok, err = coroutine.resume(co)
assert(not ok and err == "cannot resume dead coroutine", tostring(err))
local co2 = coroutine.create(function()
	error("boom")
end)
local ok2, err2 = coroutine.resume(co2)
local rethrown = select(2, pcall(function()
	if not ok2 then
		error(err2, 0)
	end
end))
assert(rethrown == err2 and string.find(tostring(err2), ":%d+: boom$") ~= nil)
