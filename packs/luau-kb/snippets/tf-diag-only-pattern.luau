--!strict
-- 주장: type function 으로 '오용을 컴파일 타임 진단으로 띄우는' 일은 된다. 검사 실패 시 print(메시지) 후
--       types.never 를 돌려주면, print 가 그 자리의 TypeError 로 보인다(error() 대신 print + never).
--       검사 결과는 원본과 섞이지 않는 별도 필드(__check)에만 싣는다.
-- 근거: quad/.claude/base/typing-limits.md 0 "타입 함수는 진단을 띄우는 데까지만", 6, luau-test/done/23 머리 주석
type function MustBeSingleton(t: type): type
	if t.tag == "singleton" then
		return types.singleton(true)
	end
	print("MustBeSingleton: expected a literal type, got " .. t.tag)
	return types.never
end
type Checked<T> = { __check: MustBeSingleton<T> }
local ok: Checked<"a"> = { __check = true }
local bad: Checked<string> = { __check = true } -- expect-error: MustBeSingleton: expected a literal type, got string
