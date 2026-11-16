--!strict
-- 주장: read 필드는 T 에 공변이고, 읽기, 쓰기 필드는 불변이다. (옛 솔버는 read 키워드 자체를 거부한다)
-- 근거: quad/.claude/base/typing-limits.md 8.11 (luau-test/done/34)
type RO<T> = { read v: T }
type RW<T> = { v: T }
local ro: RO<number> = { v = 1 }
local rw: RW<number> = { v = 1 }
local roWide: RO<number | string> = ro
local rwWide: RW<number | string> = rw -- expect-error: Expected this to be 'RW<number | string>', but got 'RW<number>'
local roOther: RO<string> = ro -- expect-error: Expected this to be 'RO<string>', but got 'RO<number>'
