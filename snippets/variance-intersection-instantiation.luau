--!strict
-- 주장: 교집합 안에서 T 가 불변·반공변 자리에 서면 같은 별칭의 값에서도 T 를 뽑지 못한다("No valid instantiation").
--       같은 멤버를 한 테이블에 두거나, 교집합이어도 T 가 공변 자리뿐이면 된다.
-- 근거: quad/.claude/audit/consumer-type-surface-2026-10-06/probes/pure/repro_a1_pure.luau, quad 8.36 A1
type W1<T> = { read v: T } & { read f: (T) -> () }
type W2<T> = { read v: T, read f: (T) -> () }
type W3<T> = { v: T } & {}
type W5<T> = { read v: T } & { read x: number }
local w1: W1<number> = (nil :: any)
local w2: W2<number> = (nil :: any)
local w3: W3<number> = (nil :: any)
local w5: W5<number> = (nil :: any)
local function id1<T>(x: W1<T>): W1<T> return x end
local function id2<T>(x: W2<T>): W2<T> return x end
local function id3<T>(x: W3<T>): W3<T> return x end
local function id5<T>(x: W5<T>): W5<T> return x end
local r1 = id1(w1) -- expect-error: No valid instantiation
local r2 = id2(w2)
local r3 = id3(w3) -- expect-error: No valid instantiation
local r5 = id5(w5)
