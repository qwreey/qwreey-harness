--!strict
-- 주장: 가변 인자 자리의 꼬리 호출 결과(f(mkStr()), f(1, mkStr()))는 0.734 새 솔버에서 검사되지 않았다.
--       괄호로 값 하나로 만들면((mkStr())) 잡혔다. 0.742 에서는 셋 다 잡힌다.
-- 근거: stl-luau/.claude/base/typing-limits.md 머리 "가변 인자 자리의 꼬리 호출 결과는 검사되지 않습니다", stl mise.toml 머리 주석(0.742 에서 53 이 더 잡힘)
local function f(...: number) end
local function mkStr(): string return "x" end
f(mkStr()) -- bug-present [<0.742] || expect-error: but got 'string' [>=0.742]
f((mkStr())) -- expect-error: but got 'string'
f(1, mkStr()) -- bug-present [<0.742] || expect-error: but got 'string' [>=0.742]
local function g(a: number, b: number) end
g(1, mkStr()) -- expect-error: but got 'string'
