--@run
-- 관측용(단언 없음). testing-o2-line-probe.luau 와 같은 몸통에 `getfenv` 라는 이름을 한 번 언급만 했다.
--   luau -O2 testing-getfenv-probe.luau -> helperLine=13, localLevel2 ":22:", fieldLevel2 ":27:" (-O1 과 같음)
-- 즉 모듈 안에서 getfenv 를 **부르지 않고 이름만 읽어도** 그 모듈의 -O2 인라이닝이 꺼진다(luau 0.734, 0.742).
-- 공식 문서: luau.org performance 가이드 "inlining is completely disabled for modules that use getfenv/setfenv".
-- 테스트 함의: mock 주입에 getfenv 를 쓰는 스펙 파일은 -O2 로 돌려도 그 파일 자신의 인라인 경로를 재현하지 못한다.
local _ = getfenv
local function curline(): number
	return (debug.info(2, "l") :: any) :: number
end
local helperLine = -1
local function inner()
	helperLine = curline()
end
local function outer()
	inner()
end
pcall(outer)
local function checkLocal(x: any)
	if type(x) ~= "number" then error("checkLocal: expected number", 2) end
end
local _, localErr = pcall(function() checkLocal("x") end)
local Lib = {}
function Lib.check(x: any)
	if type(x) ~= "number" then error("Lib.check: expected number", 2) end
end
local _, fieldErr = pcall(function() Lib.check("x") end)
print("helperLine", helperLine)
print("localLevel2", localErr)
print("fieldLevel2", fieldErr)
