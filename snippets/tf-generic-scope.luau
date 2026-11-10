--!strict
-- 주장: 제네릭과 type function 의 경계.
--   (1) 바깥 제네릭 T 에 걸린 적용(`Pass<(T) -> T>`)은 그 제네릭 함수 몸통 안에서 줄지 않는다.
--       호출조차 거부된다("Cannot call a value of type Pass<(T) -> T>").
--   (2) 호출부에서 T 가 정해지면 줄어든다. `unwrap<T>(x: T): StripNil<T>` 에 `number?` 를 주면 결과는 `number` 다.
--   (3) 제네릭 함수 타입 자체를 인자로 넘기면 제네릭이 보존된다(`Pass<<T>(T) -> T>`).
--   (4) 바깥 제네릭을 가진 별칭도 인스턴스화된 뒤에는 줄어든다(`Wrapped<number>`).
--   stl `Trait.View` 가 "외부 제네릭을 가진 별칭에 걸지 말고 함수 타입 전체에 건다"고 적은 것이 (1) 이다.
-- 근거: stl-luau/src/Trait/init.luau:101-105, stl-luau/.claude/base/trait-system.md:35,
--       Luau tests/TypeFunction.user.test.cpp outer_generics_irreducible
type function Pass(t: type): type
	return t
end
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
local function g<T>(x: Pass<(T) -> T>, v: T): T
	return x(v) -- expect-error: Cannot call a value of type Pass<(T) -> T>
end
local function unwrap<T>(x: T): StripNil<T>
	return x :: any
end
local maybe: number? = 1
local _u: number = unwrap(maybe)
local _u2: string = unwrap(maybe) -- expect-error: Expected this to be 'string', but got 'number'
type Id = Pass<<T>(T) -> T>
local id: Id = function(x) return x end
local _i: string = id(1) -- expect-error: Expected this to be 'string', but got 'number'
type Fn<T> = (T) -> T
type Wrapped<T> = Pass<Fn<T>>
local w: Wrapped<number> = function(x) return x end
local _w: string = w(1) -- expect-error: Expected this to be 'string', but got 'number'
local _g = g
