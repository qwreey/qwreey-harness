--!strict
-- 주장: 인덱서 없는 갈래가 든 유니온을 for ... in 으로 돌면 진단이 0건이고 루프 변수 타입도 검사되지 않는다.
--       같은 갈래 하나만이면 "Cannot iterate over a table without indexer" 로 잡힌다.
-- 근거: 실측. 원천 stl-luau-doctor/.claude/audit/luau-solver-issues/DRAFTS.md:236-247 (후보 S-141, 상류 미보고)
type U = { read [number]: number } | { read n: number }
local x = (nil :: any) :: U
for _, v in x do local _s: string = v end -- bug-present
local y = (nil :: any) :: { read n: number }
for _, v in y do print(v) end -- expect-error: Cannot iterate over a table without indexer
