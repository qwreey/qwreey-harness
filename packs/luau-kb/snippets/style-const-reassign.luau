--!strict
-- 주장: `const` 는 `local` 을 대체하는 바인딩이다. `const function f()` 도 유효하고, 재대입은 컴파일 단계에서 거부된다.
-- 근거: decisions D-01 2(c1.luau), stl-luau/.claude/conventions.md:89, devplorer/.claude/conventions.md:76
const function inc(a: number): number
	return a + 1
end
const k = inc(2)
k = 4 -- expect-error: Variable 'k' is constant and may not be reassigned
