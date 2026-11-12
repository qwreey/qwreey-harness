-- 벤치용 다른 모듈(인라인되지 않게 필드 대입으로 만든다)
local M = {}
function M.pushFixed(self, v)
	self.n = v
end
function M.pushFirst(self, first, ...)
	self.n = first
end
function M.pushVar(self, ...)
	self.n = (...)
end
return M
