--!strict
--@run
-- 주장: 1) pcall(f(x)) 는 f(x) 를 pcall 밖에서 먼저 부른다. f 가 성공해도 반환값을 호출하려다 실패하고, f 의 에러는 잡지 못한다.
--          메서드 인덱싱 pcall(obj.Method, obj) 도 인덱싱 자체는 pcall 밖이다. -> pcall(f, x) 또는 클로저 안에서 부른다.
--       2) local ok = pcall(...) 은 성공 여부만 담는다. 결과는 둘째 값이다.
-- 근거: moonwave-luau/.claude/known-issues.md:117-127, devplorer dvr:2026-10-21-modified-bold.md:17-28,39-44, dvr:2026-10-19-shared-specs.md:107-108.
--       후보 D-R38, D-R39
local calls = 0
local function work(x: number): string
	calls += 1
	return tostring(x)
end
local ok1, e1 = pcall(work(1) :: any)
assert(calls == 1 and not ok1 and string.find(tostring(e1), "attempt to call a string value", 1, true))

local function fails(_: number): string
	error("inner failure", 0)
end
local escaped = not pcall(function()
	pcall(fails(1) :: any) -- fails 는 pcall 밖에서 돌아 에러가 바깥으로 나간다
end)
assert(escaped)

local ok2, v2 = pcall(work, 2)
assert(ok2 and v2 == "2")
local onlyOk = pcall(work, 3)
assert(onlyOk == true)

local obj: any = nil
assert(not pcall(function()
	pcall(obj.Method, obj) -- obj.Method 인덱싱이 pcall 밖에서 터진다
end))
