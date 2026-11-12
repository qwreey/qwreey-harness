--!strict
-- 주장: "이름 + 그 이름의 타입을 받는 콜백" 은 K & keyof<Map> 와 (index<Map, K>) -> () 로 타이핑된다.
--       이름 오타와 콜백 파라미터 타입 불일치가 호출 자리에서 잡힌다. 무주석 콜백은 '검사만' 된다
--       (파라미터로 문맥 타입이 흘러들지는 않고, 본문 사용과의 불일치가 그 람다 자리 에러로 뜬다).
-- 근거: quad/.claude/base/typing-limits.md 8.7 3번(2026-10-16 정정 포함)
type PM = { Position: number, Size: string }
local function On<K>(name: K & keyof<PM>, fn: (index<PM, K>) -> ()) end
On("Position", function(v: number) end)
On("Positon", function(v: number) end) -- expect-error: does not exist on type 'PM'
On("Size", function(v: number) end) -- expect-error: Expected this to be
On("Size", function(v) local b: boolean = v end) -- expect-error: Expected this to be
