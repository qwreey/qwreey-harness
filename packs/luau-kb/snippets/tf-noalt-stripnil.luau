--!strict
-- 주장: '제네릭 타입의 메소드/필드 반환에서 nil 을 벗기기'는 type function 없이는 안 된다.
--   대안 셋을 쟀다.
--   (a) 메소드 제네릭 `Unwrap: <U>(self: R<U?>) -> U` 는 `unknown` 이 된다(두 솔버, quad 8.14).
--   (b) 부정 타입 `T & ~nil` 은 타입 주석 문법에 없다(SyntaxError).
--   (c) 자유 제네릭 함수 `unwrap<U>(r: Ref<U?>): U` 는 `number` 를 준다. 메소드가 아니어도 되는 API 라면 대안이 있다.
--   StripNil type function 은 메소드 자리에서도 동작한다.
--   - `number?` 는 `number`, `(number | string)?` 는 `number | string` 이 되고, nil 없는 타입은 그대로다.
--   - 새 솔버는 type function 본문도 검사하므로 지역 테이블에 `{ type }` 주석이 필요하다.
-- 근거: quad/.claude/base/typing-limits.md 8.14, quad/quad-types/src/init.luau:122 (StripNil, Ref:Unwrap),
--       qwreey-harness .claude/base/decisions/D-04-type-functions.md "사용자 결정"(strip-nil 예)
type function StripNil(t: type): type
	if t:is("union") then
		local comps: { type } = {}
		for _, c in t:components() do
			if not c:is("nil") then
				table.insert(comps, c)
			end
		end
		if #comps == 1 then
			return comps[1]
		end
		return types.unionof(table.unpack(comps))
	end
	return t
end
local _a: StripNil<number?> = 1
local _b: StripNil<number?> = nil -- expect-error: Expected this to be 'number', but got 'nil'
local _c: StripNil<(number | string)?> = "x"
local _d: StripNil<(number | string)?> = nil -- expect-error: Expected this to be 'number | string', but got 'nil'
local _e: StripNil<boolean> = true
type RefTf<T> = { v: T, Unwrap: (self: RefTf<T>) -> StripNil<T> }
local rt: RefTf<number?> = nil :: any
local _t1: number = rt:Unwrap()
local _t2: string = rt:Unwrap() -- expect-error: Expected this to be 'string', but got 'number'
type RefGen<T> = { v: T, Unwrap: <U>(self: RefGen<U?>) -> U }
local rg: RefGen<number?> = nil :: any
local _g1: number = rg:Unwrap() -- expect-error: got 'unknown'
type Ref<T> = { get: (self: Ref<T>) -> T, set: (self: Ref<T>, v: T) -> () }
local function unwrap<U>(_r: Ref<U?>): U
	return nil :: any
end
local r: Ref<number?> = nil :: any
local _f1: number = unwrap(r)
local _f2: string = unwrap(r) -- expect-error: Expected this to be 'string', but got 'number'
type Neg<T> = T & ~nil -- expect-error: Expected type, got '~'
