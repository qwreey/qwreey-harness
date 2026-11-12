--!strict
--@run
-- 주장: `c and a or b` 는 a 가 false/nil 이면 b 로 샌다. `if c then a else b` 식은 그렇지 않다. 단순 기본값 `x or y` 는 의도대로다.
-- 근거: quad/.claude/base/architecture.md:764-781, stl-luau/.claude/conventions.md:90. 후보 Q-083
local function viaAndOr(on: boolean): string?
	return on and nil or "off"
end
local function viaIf(on: boolean): string?
	return if on then nil else "off"
end
assert(viaAndOr(true) == "off", "and/or: 참인데도 off 로 샌다")
assert(viaIf(true) == nil and viaIf(false) == "off")
local opts: { name: string? } = {}
assert((opts.name or "default") == "default")
