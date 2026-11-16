--!strict
-- 주장: 내장 `keyof<>`/`index<>` 도 type function 이다.
--   - `keyof<T>` 에 테이블이 아닌 타입을 넣으면 "does not have keys" 로 죽는다. 조건부 타입이 없어 가릴 수 없다.
--   - `keyof<{}>` 는 빈 유니온(never)이다. 에러가 아니다.
--   - `K & keyof<Map>` 로 이름 오타를, `index<Map, K>` 로 콜백 타입 불일치를 잡는다(호출 자리).
-- 근거: quad/.claude/base/typing-limits.md 8.15, 8.7 3), quad/.claude/base/store-plan.md:358-362
type Map = { Size: number, Name: string }
type K1 = keyof<string> -- expect-error: does not have keys
type Empty = keyof<{}>
local _e: Empty = "x" -- expect-error
local function on<K>(_name: K & keyof<Map>, _fn: (v: index<Map, K>) -> ()) end
on("Size", function(_v: number) end)
on("Sise", function(_v: number) end) -- expect-error: does not exist
on("Name", function(_v: number) end) -- expect-error: 1st parameter
local _k: K1? = nil -- expect-error: does not have keys
