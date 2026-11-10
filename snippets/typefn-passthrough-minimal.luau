--!strict
-- 주장(반증 기록): "값의 타입이 type function 을 한 번 거치면(return t 패스스루라도) 이후 제네릭 self 메소드
--       체이닝이 조용히 깨진다"(quad §6)는 이 최소 꼴에서는 재현되지 않는다 — 패스스루 뒤에도 체이닝 결과가 검사된다.
--       원래 관측은 quad 실물 타입(CheckedQuad, luau-test/done/23)에 얽혀 있었다. 그래서 references 에서는 described.
-- 근거: quad/.claude/base/typing-limits.md §6, luau-test/done/23-type-quadtypes-checkversion-addplugin.luau
type function Pass(t: type): type
	return t
end
type Core = { n: number, AddPlugin: <Self, P>(self: Self, plugin: P) -> Self & P }
local plugin = { extra = 1 }
local core = (nil :: any) :: Core
local direct: string = core:AddPlugin(plugin).extra -- expect-error: Expected this to be 'string', but got 'number'
local passed = (nil :: any) :: Pass<Core>
local afterPass: string = passed:AddPlugin(plugin).extra -- expect-error: Expected this to be 'string', but got 'number'
