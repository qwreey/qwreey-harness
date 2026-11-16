--!strict
--@run
-- 주장: 1) __index 는 rawget 이 실패할 때만 불린다. 인스턴스에 메서드와 같은 이름의 데이터 필드가 있으면 메서드가 가려진다.
--       2) 메타메서드(__tostring 등)는 __index 체인으로 상속되지 않는다. 파생 메타테이블마다 직접 단다.
--       3) table.clone 은 얕은 복사이고 메타테이블은 같은 참조를 공유한다.
-- 근거: quad .claude/base/architecture.md:507-510, .claude/base/modifier-plan.md:341-353, tbox packages/tbox/CLAUDE.md:113. 후보 Q-077, Q-078
local methods = {
	format = function(_self: any): string
		return "TNumber"
	end,
}
local Base = { __index = methods, __tostring = function(): string
	return "Base"
end }
local shadowed: any = setmetatable({ format = "u8" }, Base)
assert(not pcall(function()
	return shadowed:format()
end), "데이터 필드 format 이 메서드를 가린다")
local renamed: any = setmetatable({ encoding = "u8" }, Base)
assert(renamed:format() == "TNumber")

local Derived = setmetatable({ __index = methods }, { __index = Base })
assert(Derived.__tostring ~= nil, "필드로는 보이지만")
assert(tostring(setmetatable({}, Derived)) ~= "Base", "tostring 은 rawget 으로 찾으므로 상속되지 않는다")
assert(tostring(setmetatable({}, Base)) == "Base")

local inner = { 1 }
local original = setmetatable({ inner = inner }, Base)
local copy = table.clone(original)
assert(getmetatable(copy) == Base and copy.inner == inner)
