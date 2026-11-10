--!strict
--@run
-- 주장: 제네릭 함수가 타입 변수 V 로 받은 값을 공변(read) 자리의 컨테이너와 함께 받으면,
--       V 가 넓어져(number | string) 틀린 값도 통과한다. 불변 팬텀 (V) -> V 로 받으면 잡힌다.
-- 근거: stl-luau/.claude/base/typing-limits.md 머리 "2026-10-12 키·위치·값을 넘기는 제네릭은 불변 마커"
local function put<V>(m: { read v: V }, x: V) end
local box: { read v: number } = { v = 1 }
put(box, "bad") -- bug-present
local function putInv<V>(m: { read v: (V) -> V }, x: V) end
local boxInv = { v = function(n: number): number return n end }
putInv(boxInv, "bad") -- expect-error: Expected this to be 'number', but got 'string'
print("ok")
