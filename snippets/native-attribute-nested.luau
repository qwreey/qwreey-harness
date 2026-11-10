--!strict
--@codegen => names = f
--@codegen +native => names = [anonymous],[top-level],f,g
-- 주장: @native 는 붙인 함수 하나에만 적용된다. 그 안에서 만든 클로저와 같은 파일의 다른 함수, 최상위 코드는 네이티브로 컴파일되지 않는다.
--       --!native 는 파일의 모든 함수와 최상위(루프가 있을 때)를 대상으로 한다. 하네스 머리(--@compile/--@codegen/--@inline-remarks) 가 luau-compile --codegen 의 함수 목록으로 검사한다.
-- 근거: rfcs docs/syntax-attribute-functions-native.md "It does not apply recursively", CodeGen/src/CodeGenLower.h gatherFunctionsHelper (luau 8387cfb)
@native
local function f(x: number): number
	local inner = function(y: number): number return y * 2 end
	return inner(x) + 1
end
local function g(x: number): number return x * 3 end
for i = 1, 3 do print(f(i), g(i)) end
