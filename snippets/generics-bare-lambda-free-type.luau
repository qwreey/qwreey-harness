--!strict
--@run
-- 주장: 파라미터를 제약하지 않는 맨 람다(return v)의 결과가 0.734 새 솔버에선 자유 타입으로 새어 아무 데나 대입됐다.
--       0.742 에서 고쳐졌다(에러가 난다). 버전을 올릴 때 이런 칸이 바뀐다.
-- 근거: stl-luau/.claude/audit/luau-solver-issues/2-bare-lambda-free-type.luau, DRAFTS.md 머리("0.742 에서 고쳐져 뺄 것")
local function Map2<T, G>(xs: { T }, f: (T) -> G): { G }
	local out: { G } = {}
	for i, x in xs do
		out[i] = f(x)
	end
	return out
end
local leaked: { string } = Map2({ 1, 2 }, function(v) return v end) -- bug-present [<0.742] || expect-error [>=0.742]
local control: { string } = Map2({ 1, 2 }, function(v: number) return v end) -- expect-error: {number}
print(type(leaked[1]))
