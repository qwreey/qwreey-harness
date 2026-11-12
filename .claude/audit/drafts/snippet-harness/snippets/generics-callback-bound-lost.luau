--!strict
--@run
-- 새 솔버 결함: 뒤쪽 인자를 생략한 람다는 주석의 상한이 버려진다 (stl-luau typing-limits.md "뿌리" 절, 0.742 재현)
local function F<T>(x: T, fn: (T, T) -> ())
	fn(x, x)
end
local text: string = "x"
F(text, function(v: number) end) -- bug-present
F(text, function(v: number, _w) end) -- expect-error: number
print("done")
