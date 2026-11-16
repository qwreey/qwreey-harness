--!strict
-- DX 프로브 샘플 라이브러리: 공개 API 의 hover, 자동완성, 추론 타입이 소비자에게 어떻게 보이는지 본다.

export type Stack<T> = {
	items: { T },
	--- 맨 위 값을 넣는다.
	push: (self: Stack<T>, value: T) -> (),
	--- 맨 위 값을 꺼낸다. 비었으면 nil.
	pop: (self: Stack<T>) -> T?,
	size: (self: Stack<T>) -> number,
}

local Stack = {}

--- 빈 스택을 만든다.
function Stack.new<T>(): Stack<T>
	local self = { items = {} } :: any
	function self.push(s: Stack<T>, value: T)
		table.insert(s.items, value)
	end
	function self.pop(s: Stack<T>): T?
		return table.remove(s.items)
	end
	function self.size(s: Stack<T>): number
		return #s.items
	end
	return self
end

-- 주석 없는 공개 함수: 반환 타입이 추론에만 맡겨진다
function Stack.fromList(list)
	local s = Stack.new()
	for _, v in list do
		s:push(v)
	end
	return s
end

return Stack
