--@luaurc {"languageMode": "nonstrict"}
--@args --mode=strict
--@no-control 같은 파일에 --!strict 를 넣으면 주장이 사라진다. 대조군은 modes-strict-directive-wins.luau
-- 주장: .luaurc 가 nonstrict 이고 파일에 --!strict 가 없으면, 명백한 타입 에러도 새 솔버가 0건으로 보고한다.
--       luau-analyze 의 --mode=strict 는 .luaurc 를 덮어쓰지 못한다(.luaurc 도 지시자도 없을 때의 기본값일 뿐).
-- 근거: stl-luau/.claude/base/typing-limits.md "`.luaurc` 하나에 의존하면 검사가 통째로 꺼집니다"(310건 → 0건 표)
local function f(x: number): number
	return x
end
local s: string = f(1) -- bug-present
local bad = f("x") -- bug-present
