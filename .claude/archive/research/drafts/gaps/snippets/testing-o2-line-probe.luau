--@run
-- 관측용(단언 없음): 같은 파일을 -O1 과 -O2 로 돌려 출력이 갈리는 것을 본다. 하네스는 -O1 로만 실행한다.
--   luau -O1 testing-o2-line-probe.luau   -> helperLine=11, localLevel2 에 ":20:" 위치, fieldLevel2 에 ":25:" 위치
--   luau -O2 testing-o2-line-probe.luau   -> helperLine=-1(C 프레임 pcall), localLevel2 위치 없음, fieldLevel2 는 그대로 ":25:"
-- 근거: testing.md §5 (luau 0.734, 0.742 에서 같은 결과).
local function curline(): number
	return (debug.info(2, "l") :: any) :: number -- 호출자 줄을 헬퍼로 잰다(-O2 에서 깨지는 모양)
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
