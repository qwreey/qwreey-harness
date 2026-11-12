--!strict
--@run
-- 주장: 테이블 리터럴 { a = 1 } 은 레코드 { a: number } 라서 { [K]: V } 파라미터에서 K/V 를 뽑지 못하고
--       unknown 으로 굳는다. 그 뒤의 쓰기는 무엇을 넣어도 진단 0건. 명시적 타입 인자 f<<K, V>> 로 해결.
-- 근거: stl-luau/.claude/base/typing-limits.md "조용히 타입을 잃는 자리 셋" 2번
type Box<K, V> = { data: { [K]: V } }
local function FromTable<K, V>(t: { [K]: V }): Box<K, V>
	return { data = t }
end
local function Put<K, V>(b: Box<K, V>, k: K, v: V)
	b.data[k] = v
end
local leaked = FromTable({ a = 1 }) -- Box<unknown, unknown>
Put(leaked, 5, "bad") -- bug-present
leaked.data[true] = {} -- bug-present
local fixed = FromTable<<string, number>>({ a = 1 })
Put(fixed, "b", "bad") -- expect-error: Expected this to be 'number', but got 'string'
local readBack: boolean = leaked.data.a -- expect-error: got 'unknown'
print(leaked.data[5])
