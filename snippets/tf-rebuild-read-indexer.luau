--!strict
-- 주장: type function 이 테이블을 '다시 조립'하면 읽기 전용 인덱서를 잃는다.
--   - `setreadindexer` 는 런타임 에러다("luau does not yet support separate read/write types for indexers").
--   - `indexer()` → `setindexer` 로 옮기면 `read` 가 빠져 쓰기가 통과한다.
--   - 패스스루(`return t`)는 원래 타입을 그대로 돌려주므로 `read` 가 남는다.
--   - 읽기 전용 '프로퍼티'는 setreadproperty 로 옮길 수 있다.
-- 근거: stl-luau/src/Trait/init.luau:~373-377, stl-luau/.claude/base/trait-system.md:105,
--       stl-luau/.claude/papers/08-trait-retrospective.md:95
type function Pass(t: type): type
	return t
end
type function RebuildRead(t: type): type
	local out = types.newtable()
	local ix = t:indexer()
	if ix then
		out:setreadindexer(ix.index, ix.readresult)
	end
	return out
end
type function Rebuild(t: type): type
	local out = types.newtable()
	local ix = t:indexer()
	if ix then
		out:setindexer(ix.index, ix.readresult)
	end
	for k, p in t:properties() do
		if p.read and not p.write then
			out:setreadproperty(k, p.read)
		end
	end
	return out
end
local _a: RebuildRead<{ read [string]: number }> = nil :: any -- expect-error: separate read/write types for indexers
local b: Rebuild<{ read [string]: number }> = {}
b.x = 1 -- bug-present
local c: Pass<{ read [string]: number }> = {}
c.x = 1 -- expect-error: read-only
local d: Rebuild<{ read v: number }> = { v = 1 }
d.v = 2 -- expect-error: read-only
