--!strict
-- 주장: type function 의 인자는 직렬화할 수 있어야 한다. 다음 두 꼴은 직렬화되지 않는다.
--   (1) 인자 안에 제네릭에 묶인 채 줄지 않은 타입 함수 적용(`keyof<K>`, `index<…, K>`, 사용자 type function)이 있다.
--   (2) 인자가 그 type function 적용 자신을 가리키는 순환 별칭이다(`type Obj = Pass<{ m: (self: Obj) -> … }>`).
--   그러면 "Type functions do not currently support types of the form ..." 이 나고, 결과는 키가 없는 타입이 된다.
--   큰 라이브러리 타입(진단용 type function 필드를 품은 quad `Quad` 등)을 통째로 넘기면 이 벽에 걸린다.
--   제네릭 메소드 자체(`<K>(k: K) -> K`)와, type function 밖에서 정의한 재귀 별칭은 문제없다.
-- 근거: quad/.claude/audit/decl-typefn-probe-2026-10-16/REPORT.md:657(OmitKeys over QT.Quad),
--       quad/.claude/base/store-plan.md:317-356(*error-type* 인자), quad/.claude/base/typing-limits.md 8.39
type function Pass(t: type): type
	return t
end
type Api = { n: number, get: <K>(k: K) -> keyof<K> }
local a = (nil :: any) :: Pass<Api> -- expect-error: do not currently support types of the form 'keyof<K>'
local _s: string = a.n -- expect-error: does not have key 'n'
type Plain = { n: number, get: <K>(k: K) -> K }
local b = (nil :: any) :: Pass<Plain>
local _s2: string = b.n -- expect-error: Expected this to be 'string', but got 'number'
type Rec = { n: number, map: <U>(self: Rec, f: (number) -> U) -> U }
local r = (nil :: any) :: Pass<Rec>
local _s3: string = r:map(function(v) return v end) -- expect-error: Expected this to be 'string', but got 'number'
type SelfRef = Pass<{ m: (self: SelfRef) -> number }> -- expect-error: do not currently support types of the form
