--!strict
--@args --flag:LuauSolverV2=false
-- 주장: 옛 솔버는 SharedTable 의 일반화 반복(`for k, v in st`)을 받아 준다. 새 솔버 짝은 parallel-sharedtable-types.luau.
-- 근거: typedefs/globalTypes.d.luau `declare extern type SharedTable ... function __iter`; SharedTable.md "Element Iteration" 예제
local st = SharedTable.new({ "a", "b", "c" })
for k, v in st do
	local key: string = k
end
for k, v in SharedTable.clone(st, false) do
end
st[true] = 1 -- expect-error
