--!strict
--@luaurc {"languageMode": "nonstrict"}
-- 주장: 같은 nonstrict .luaurc 아래에서도 파일 첫 줄의 --!strict 는 strict 검사를 켠다 — 믿을 수 있는 유일한 층.
--       (modes-luaurc-nonstrict-silences.luau 의 대조군)
-- 근거: stl-luau/.claude/base/typing-limits.md ".luaurc 하나에 의존하면" 표의 '있음' 행
local function f(x: number): number
	return x
end
local s: string = f(1) -- expect-error: Expected this to be 'string', but got 'number'
local bad = f("x") -- expect-error: Expected this to be 'number', but got 'string'
