--!strict
-- 주장(0.734/0.742 새 솔버): 제네릭 T 에 문자열 리터럴을 넘기면 싱글턴이 보존된다(f("bbb") 의 T = "bbb").
--       T & ("A" | "B") 로 범위를 걸면 범위 밖 리터럴이 정확히 거부된다.
--       단, 결과를 '레코드 유니온' 기대 타입에 맞추면 레코드 필드의 K 가 string 으로 넓어져 거부된다.
--       (quad 8월 표의 "f<T>(x: T): T 는 string 으로 뭉개짐"은 이 버전들에서 재현되지 않는다 — 옛 솔버만 string)
-- 근거: quad/.claude/base/typing-limits.md §7 싱글톤 보존 표, 8.7 1번
local function f1<T>(input: T): T return input end
local function f4<T>(input: T & ("A" | "B")): T return input :: any end
local function OnChange<K>(name: K): { Name: K } return { Name = name } end
local a = f1("bbb")
local keepA: "bbb" = a
local c = f4("B")
local keepC: "B" = c
local wrongC: "A" = c -- expect-error: Expected this to be '"A"', but got '"B"'
local outOfRange = f4("C") -- expect-error: is not a subtype of
local r = OnChange("Position")
local keepR: "Position" = r.Name
local inUnion: { Name: "Position" } | { Name: "Size" } = OnChange("Position") -- expect-error: { Name: string }
