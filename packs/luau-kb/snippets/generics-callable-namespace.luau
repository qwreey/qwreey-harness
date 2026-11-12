--!strict
-- 주장: `__call` 을 단 모듈 테이블(콜러블 네임스페이스)로 제네릭 생성자를 부르면 결과의 타입 인자가 검사되지 않는다.
--       `M(5).v` 를 string 에 담아도 0건이고, 같은 생성자를 필드로 부르면(`M.New(5)`) 잡힌다. `__call` 을 제네릭으로 주석해도 같다.
--       원천의 "모듈 필드 오타도 못 잡는다"는 이 꼴에서는 재현되지 않았다(아래 typo 줄은 잡힌다).
-- 근거: 실측(0.734, 0.742). 원천 stl-luau-doctor/.claude/conventions.md:40, base/architecture.md:300 (후보 S-136)
type Box<T> = { v: T }
local M = {}
function M.New<T>(v: T): Box<T> return { v = v } end
setmetatable(M, { __call = function<T>(_: any, v: T): Box<T> return M.New(v) end })
local viaCall = M(5)
local s1: string = viaCall.v -- bug-present
local viaField = M.New(5)
local s2: string = viaField.v -- expect-error: but got 'number'
local typo = M.Neww -- expect-error: does not have key 'Neww'
local _ = s1, s2, typo
