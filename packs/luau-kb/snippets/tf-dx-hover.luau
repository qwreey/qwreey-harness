--!strict
-- 주장(DX, luau-lsp 전용): 이 파일은 진단 0건이다. hover, 자동완성은 아래 명령으로 잰다.
--   python3 -I tools/lsp_probe.py snippets/tf-dx-hover.luau --lsp 1.70.1 --hover 33:16 --hover 36:7 \
--     --hover 40:8 --hover 45:8 --complete 49:19
-- 관측(1.69.0, 1.70.1 같음):
--   - 시그니처 hover 는 적용을 줄이지 않은 채 보여 준다(`StripNil<T>` 그대로).
--   - 호출 결과 hover 는 줄인 타입이다(`local got: number`).
--   - `index<Map, K>` 파라미터의 무주석 콜백은 `v: unknown` 이다. 문맥 타입이 흘러들지 않는다.
--     같은 모양의 구체 시그니처(on2)는 `number` 다.
--   - type function 이 setproperty 로 만든 테이블도 키 자동완성(`beta`)이 뜬다.
-- 근거: quad/.claude/base/typing-limits.md 8.7 3) (2026-10-16 정정), quad/.claude/audit/d-factory-studio-probe-2026-09-16/REPORT.md:37
type function StripNil(t: type): type
	if t:is("union") then
		local comps: { type } = {}
		for _, c in t:components() do
			if not c:is("nil") then
				table.insert(comps, c)
			end
		end
		if #comps == 1 then
			return comps[1]
		end
		return types.unionof(table.unpack(comps))
	end
	return t
end
type function Mk(_t: type): type
	local out = types.newtable()
	out:setproperty(types.singleton("alpha"), types.number)
	out:setproperty(types.singleton("beta"), types.string)
	return out
end
local function unwrap<T>(x: T): StripNil<T>
	return x :: any
end
local got = unwrap(1 :: number?)
type Map = { Size: number, Name: string }
local function on<K>(_name: K & keyof<Map>, _fn: (v: index<Map, K>) -> ()) end
on("Size", function(v)
	local w = v
	local _ = w
end)
local function on2(_name: "Size", _fn: (v: number) -> ()) end
on2("Size", function(v2)
	local w2 = v2
	local _ = w2
end)
local made = (nil :: any) :: Mk<number>
local _b = made.beta
local _g = got
