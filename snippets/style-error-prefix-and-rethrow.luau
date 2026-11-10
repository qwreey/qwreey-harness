--!strict
--@run
-- 주장: ① error(msg) 는 level 1 이라 "파일:줄: " 접두가 붙고 error(msg, 0) 은 붙지 않는다.
--       ② error 는 아무 값이나 던진다. 테이블은 pcall 을 지나도 같은 값이다(err 를 string 으로 가정하지 않는다).
--       ③ pcall(f) 처럼 C 가 바로 부른 함수의 error(msg, 2) 는 위치를 잃는다(level 2 가 C 프레임).
--       ④ 받은 에러를 error(e) 로 되던지면 접두가 두 번 붙는다. 되던질 때는 error(e, 0).
-- 근거: quad .claude/audit/fallback-xpcall-verification.md:28-38, docs/quadnomicon/11-static-grepability-and-error-architecture.md:117-129,
--       stl-luau/.claude/archive/conventions-2026-11-04.md:525-539, rbvm-cr:198-203. 후보 Q-095, Q-098, S-117, R-11
local function catch(f: () -> ()): any
	local ok, e = pcall(f)
	assert(not ok)
	return e
end
local e1 = catch(function()
	error("boom")
end)
assert(type(e1) == "string" and string.find(e1, "^.+:%d+: boom$") ~= nil, e1)
assert(catch(function()
	error("boom", 0)
end) == "boom")
local payload = { code = 7 }
assert(catch(function()
	error(payload)
end) == payload)
local function thrower()
	error("direct", 2)
end
local ok, e3 = pcall(thrower)
assert(not ok and e3 == "direct", tostring(e3))
local inner = catch(function()
	error("boom")
end)
local twice = catch(function()
	error(inner)
end)
local once = catch(function()
	error(inner, 0)
end)
assert(select(2, string.gsub(twice, ":%d+: ", "")) == 2, twice)
assert(once == inner)
