-- 벤치용 다른 모듈. 필드 대입으로 만든 모듈 테이블이라 -O2 에서도 호출 지점에 인라인되지 않는다(실제 라이브러리와 같은 조건).
local Arr = {}
Arr.__index = Arr

function Arr.new(n: number)
	local data = table.create(n, 1)
	return setmetatable({ n = n, data = data }, Arr)
end

function Arr.Len(a): number
	return a.n
end

function Arr:LenM(): number
	return self.n
end

function Arr.Get(a, i: number)
	return a.data[i]
end

-- 루프가 있는 함수
function Arr.Sum(a): number
	local d = a.data
	local s = 0
	for i = 1, a.n do
		s += d[i]
	end
	return s
end

Arr.TYPE_KEY = "__type"

return Arr
