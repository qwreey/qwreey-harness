--!strict
-- 주장: any 를 인덱스해 얻은 무주석 지역을 ~= nil 로 좁히면 *error-type* | ~nil 이 되어 호출이 거부된다.
--       지역에 함수 타입을 적으면 된다.
-- 근거: quad/.claude/base/typing-limits.md 8.24
local function fire(v: any, name: string)
	local cb = v[name]
	if cb ~= nil then
		cb() -- expect-error: Cannot call a value of type *error-type* in union
	end
	local typed: (() -> ())? = v[name]
	if typed ~= nil then
		typed()
	end
end
