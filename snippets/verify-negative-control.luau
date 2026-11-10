--!strict
--@run
-- 주장(방법론): 검사기가 실제로 이 파일을 strict 새 솔버로 보고 있다는 증거는 '일부러 틀린 줄'이 잡히는 것뿐이다.
--       모든 스니펫은 이런 음성 대조군 줄을 최소 하나 둔다(하네스가 bug-present 파일에 강제).
-- 근거: stl-luau/.claude/base/typing-limits.md 원칙 "진단 0건을 신뢰하지 마세요", quad doc-snippets.py 통제군
local function id<T>(x: T): T
	return x
end
local ok: number = id<<number>>(1)
local bad: number = id<<string>>("a") -- expect-error: Expected this to be 'number', but got 'string'
print(ok, bad)
