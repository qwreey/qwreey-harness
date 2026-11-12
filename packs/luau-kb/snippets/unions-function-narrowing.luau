--!strict
-- 주장: 새 솔버에서 type(x) == "function" 으로 좁힌 값은 최상위 function 타입이 되어 호출할 수 없다.
--       검사용 값과 호출용 값(구체 함수 타입으로 캐스트)을 나눌 것.
-- 근거: quad/.claude/base/typing-limits.md 8.9 "인접 실측" 의 type(x) == "function" 항목
local function g(x: unknown)
	if type(x) == "function" then
		x() -- expect-error: not precise enough
		local f = (x :: any) :: () -> ()
		f()
	end
end
