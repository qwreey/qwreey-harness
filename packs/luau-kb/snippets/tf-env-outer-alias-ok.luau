--!strict
-- 주장: 바깥 '타입 별칭'은 type function 안에서 참조할 수 있다(0.734·0.742, luau-lsp 1.69.0·1.70.1).
--       - 제네릭 없는 별칭은 type 값으로 보인다(`return Point`).
--       - 제네릭 별칭은 함수처럼 부른다(`Box(t)`).
--       - 같은 스코프의 다른 type function 도 부를 수 있다(`Helper(t)`).
--       - `types.optional` 도 있다.
--       quad 의 "type function 은 바깥 타입 별칭을 참조하지 못한다"와 "types.optional 은 없다"는 이 버전들에서 성립하지 않는다.
--       (다른 모듈 별칭은 지역 별칭으로 다시 이름 붙이면 된다: tf-cross-module.sh)
-- 근거: quad/.claude/base/typing-limits.md §5 "바깥 타입 별칭을 참조하지 못해", 8.22 "types.optional 은 없다",
--       quad/.claude/audit/type-store-index-keyof/REPORT.md:24-28, Luau Analysis/src/UserDefinedTypeFunction.cpp environmentAlias
type Point = { x: number }
type Box<T> = { v: T }
type function UseAlias(t: type): type
	return Point
end
type function UseGeneric(t: type): type
	return Box(t)
end
type function Helper(t: type): type
	return types.unionof(t, types.string)
end
type function UseHelper(t: type): type
	return Helper(t)
end
type function Opt(t: type): type
	return types.optional(t)
end
local _a: UseAlias<number> = { x = 1 }
local _a2: UseAlias<number> = { x = "no" } -- expect-error: Expected this to be 'number'
local _b: UseGeneric<number> = { v = 1 }
local _b2: UseGeneric<number> = { v = "no" } -- expect-error: Expected this to be 'number'
local _c: UseHelper<number> = "s"
local _c2: UseHelper<number> = true -- expect-error: number | string
local _d: Opt<number> = nil
local _d2: Opt<number> = "s" -- expect-error: number?
