--!strict
-- 주장: 타입 별칭 안에 '선언된' 테이블 타입의 제네릭 함수 필드(Apply: <U>(self, factory: (any) -> U) -> U)는
--       U 가 결과를 제약하지 않는다 — 결과를 엉뚱한 타입에 담아도 진단 0건. 자유 함수나 '추론된' 테이블의
--       같은 함수는 정상으로 잡힌다.
-- 근거: quad/.claude/base/typing-limits.md 8.29 (audit/round13-e14-types5.luau)
type Mod = { Apply: <U>(self: any, factory: (any) -> U) -> U }
local m = (nil :: any) :: Mod
local function Boldify(x: string): string return x end
local declared: number = m:Apply(Boldify) -- bug-present
local function ApplyFree<U>(self: any, factory: (any) -> U): U return factory(self) end
local free: number = ApplyFree(m, Boldify) -- expect-error: Expected this to be 'number', but got 'string'
local inferred = { Apply = ApplyFree }
local viaInferred: number = inferred.Apply(m, Boldify) -- expect-error: Expected this to be 'number', but got 'string'
