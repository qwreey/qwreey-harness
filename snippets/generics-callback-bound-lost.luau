--!strict
--@run
-- 주장: 새 솔버 결함. 제네릭 T 를 추론해야 하고, 람다가 T 를 (공변/불변으로) 품은 뒤쪽 파라미터를 생략하면
--       람다 파라미터 주석이 T 에 주는 상한이 버려진다. 옛 솔버·명시 타입 인자·파라미터 선언은 잡는다.
-- 근거: stl-luau/.claude/audit/luau-solver-issues/1-annotation-bound-lost.luau, DRAFTS.md 1번
local function F<T>(x: T, fn: (T, T) -> ())
	fn(x, x)
end
local text: string = "x"
F(text, function(v: number) end) -- bug-present
F(text, function(v: number, _w) end) -- expect-error: number
F<<string>>(text, function(v: number) end) -- expect-error: number
local function G<T>(x: T, fn: (T, (T) -> ()) -> ()) end
G(text, function(v: number) end) -- expect-error: number
print("done")
