--!strict
--@run
--@run-opt=0,2
-- 주장: pcall 로 잡은 에러 값의 모양(위치 접두가 붙는지)은 던진 방식마다 다르다. 테스트가 메시지를 단언할 때 이 표를 따른다.
--   assert(false, msg)   -> "<파일>:<줄>: msg"  (Lua 5.1 과 달리 Luau 의 assert 는 위치를 붙인다)
--   assert(false)        -> "<파일>:<줄>: assertion failed!"
--   error(msg, 0)        -> "msg" (위치 없음)
--   error(msg, 2) 를 pcall 이 직접 부른 함수에서 -> 위치 없음(level 2 가 C 함수 pcall)
--   error(tbl)           -> 그 테이블 그대로(동일성 유지)
--   assert(cond, tbl)    -> 테이블을 던지지 않고 "invalid argument #2 to 'assert'" 로 바뀐다
-- 근거: 이 파일 실행(luau 0.734, 0.742, -O0/-O1/-O2 모두 같은 값). -O2 에서 달라지는 모양은 test-o2-line-probe.luau. 원천: claude-doctor drafts/gaps/testing.md §5

local function catch(fn: () -> ()): any
	local ok, err = pcall(fn)
	assert(not ok, "에러가 나야 한다")
	return err
end

local function hasPrefix(msg: string, line: number): boolean
	return string.find(msg, `:{line}: `, 1, true) ~= nil
end

local where = 0
local e1 = catch(function()
	where = debug.info(1, "l") + 1
	assert(false, "boom")
end)
assert(hasPrefix(e1, where) and string.sub(e1, -4) == "boom", e1)

local e2 = catch(function()
	where = debug.info(1, "l") + 1
	assert(false)
end)
assert(hasPrefix(e2, where) and string.find(e2, "assertion failed!", 1, true) ~= nil, e2)

local e3 = catch(function()
	error("bare", 0)
end)
assert(e3 == "bare", e3)

local e4 = catch(function()
	error("lvl2", 2)
end)
assert(e4 == "lvl2", `pcall 이 직접 부른 함수의 level 2 는 위치가 없다: {e4}`)

local payload = { code = 7 }
local e5 = catch(function()
	error(payload)
end)
assert(e5 == payload, "테이블 에러 값은 그대로 온다")

local e6 = catch(function()
	assert(nil, (payload :: any))
end)
assert(type(e6) == "string" and string.find(e6, "invalid argument #2 to 'assert'", 1, true) ~= nil, tostring(e6))

print("ok")
