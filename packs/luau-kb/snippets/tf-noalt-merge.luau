--!strict
-- 주장: 옵션 테이블 '합치기'는 대부분 교집합 `A & B` 로 된다. type function 이 꼭 필요한 것은 '뒤 키가 앞 키를 덮어쓰는' 병합이다.
--   - `(A & B)?` 는 옵셔널과 섞여도 동작한다(0.734·0.742 최소 꼴). tbox 의 "& 가 ? 와 섞이면 깨진다"는 이 꼴로 재현되지 않는다.
--   - 같은 키의 타입이 다르면 교집합은 `number & string` 이 되어 아무 값도 못 넣는다. Merge type function 은 덮어쓴다.
--   - 리터럴의 모르는 키(c)는 Merge 결과든, 교집합이든, 손으로 쓴 테이블 타입이든 똑같이 통과한다(bug-present ×3).
--     tbox 가 "Merge 가 만드는 테이블이 닫혀 있지 않아서"라고 적은 원인은 Merge 고유가 아니다.
--     새 솔버가 테이블 리터럴의 남는 키를 검사하지 않는 것이다.
-- 근거: tbox/packages/tbox/CLAUDE.md:120-121,150, tbox/packages/tbox/src/types.luau:105-141 (MergeInner)
type function Merge(a: type, b: type): type
	local out = types.newtable()
	for k, v in a:properties() do
		out:setproperty(k, v.read)
	end
	for k, v in b:properties() do
		out:setproperty(k, v.read)
	end
	return out
end
type A = { a: number? }
type B = { b: string? }
type Opts = (A & B)?
local _o1: Opts = { a = 1, b = "x" }
local _o2: Opts = nil
local _o3: Opts = { a = "no" } -- expect-error: Expected this to be 'number?', but got 'string'
type Over = { a: number } & { a: string }
local _ov: Over = { a = 1 } -- expect-error: Expected property `a` to be exactly `string`
type Merged = Merge<{ a: number }, { a: string }>
local _m1: Merged = { a = "x" }
local _m2: Merged = { a = 1 } -- expect-error: Expected this to be 'string', but got 'number'
type M = Merge<{ a: number }, { b: string }>
local _x1: M = { a = 1, b = "x", c = true } -- bug-present
local _x2: { a: number } & { b: string } = { a = 1, b = "x", c = true } -- bug-present
local _x3: { a: number, b: string } = { a = 1, b = "x", c = true } -- bug-present
