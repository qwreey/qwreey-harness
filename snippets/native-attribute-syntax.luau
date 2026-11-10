--!strict
-- 주장: 함수 속성은 @native, @checked, @deprecated 셋뿐이다. @inline 은 없다(RFC 의 예시일 뿐). 같은 속성 중복은 에러.
--       @native 는 local function, 익명 함수 식, 메서드 선언, 테이블 필드 함수 어디에나 붙는다. @checked 는 사용자 코드에서도 조용히 받는다.
-- 근거: Ast/src/Parser.cpp kAttributeEntries(luau 8387cfb), rfcs docs/syntax-attributes-functions.md, syntax-attribute-functions-native.md
@native
local function a(x: number): number return x + 1 end
local t = { k = @native function(x: number): number return x * 2 end }
local C = {}
@native
function C:m(x: number): number return x end
@native
function C.f(x: number): number return x end
@checked
local function chk(x: number): number return x end
@inline -- expect-error: Invalid attribute '@inline'
local function b() end
@native @native -- expect-error: Cannot duplicate attribute '@native'
local function c() end
print(a(1), t.k(1), C:m(1), C.f(1), chk(1), b, c)
