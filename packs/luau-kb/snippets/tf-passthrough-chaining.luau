--!strict
-- 주장(반증 기록): quad 6 은 "값의 타입이 type function 을 한 번 거치면(`return t` 패스스루라도) 이후 제네릭 self
--       메소드 체이닝이 조용히 깨진다"고 한다. 이 파일의 다섯 꼴에서는 재현되지 않는다.
--       다섯 꼴: 직접 비교, 두 인자 Check<Core, "1.0.0">, 두 번 체이닝, 제네릭 Gen<number>, 자유 함수 addPlugin.
--       luau-lsp 1.69.0·1.70.1 에서도 같다. 체이닝 결과가 계속 검사된다.
--       quad 실물 `Quad` 를 Pass 에 넣으면 0.742 가 "do not currently support types of the form 'CheckReservedKeys<keyof<T>>'" 를 낸다.
--       그 뒤 `AddPlugin` 키가 사라진다. 0.734 는 메시지 없이 키만 사라진다. 원인은 이력이 아니라 직렬화 실패다
--       (tf-serialize-unsupported-arg). 원래 관측("Expected exactly 'P & Self', got 'P & Self'")은 2026-08 툴체인이었다. [추정]
-- 근거: quad/.claude/base/typing-limits.md 6, quad/.claude/luau-test/done/23 머리 주석 3번, stl-luau/.claude/conventions.md:84 2)
type function Pass(t: type): type
	return t
end
type function Check(t: type, _p: type): type
	return t
end
type Core = { n: number, AddPlugin: <Self, P>(self: Self, plugin: P) -> Self & P }
local plugin = { extra = 1 }
local core = (nil :: any) :: Core
local _direct: string = core:AddPlugin(plugin).extra -- expect-error: Expected this to be 'string', but got 'number'
local passed = (nil :: any) :: Pass<Core>
local _afterPass: string = passed:AddPlugin(plugin).extra -- expect-error: Expected this to be 'string', but got 'number'
local c = (nil :: any) :: Check<Core, "1.0.0">
local x2 = c:AddPlugin({ extra = 1 }):AddPlugin({ more = "s" })
local _r2: string = x2.extra -- expect-error: Expected this to be 'string', but got 'number'
local _r3: number = x2.more -- expect-error: Expected this to be 'number', but got 'string'
type Gen<T> = { v: T, With: <Self, P>(self: Self, p: P) -> Self & P }
local g = (nil :: any) :: Pass<Gen<number>>
local _r5: string = g:With({ q = 1 }):With({ w = 2 }).v -- expect-error: Expected this to be 'string', but got 'number'
local function addPlugin<Self, P>(_self: Self, _p: P): Self & P
	return nil :: any
end
local _r6: string = addPlugin(c, { k = 1 }).k -- expect-error: Expected this to be 'string', but got 'number'
