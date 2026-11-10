--!strict
--@run
-- 주장: table.move 는 원본·대상의 메타메서드(__index, __newindex)를 부르지 않고 raw 로 복사한다.
--       그래서 MT 가 붙은 표의 정수 칸 세금(bench/mt-index.luau)을 내지 않는다. 손으로 쓴 복사 루프는 메타메서드를 부른다(대조군).
-- 근거: luau VM/src/ltablib.cpp tmove/moveelements(array 직접 복사 또는 lua_rawgeti/lua_rawseti), 후보 S-P03,
--       stl-luau-doctor/.claude/base/perf-measurements.md 2절. 시간 비교는 bench/tbl-move.luau
local calls = 0
local src: any = setmetatable({}, { __index = function(_, i: number) calls += 1; return i * 10 end })
rawset(src, 1, 1)
rawset(src, 2, 2)
local dst: any = setmetatable({}, { __newindex = function(t, k, v) calls += 1; rawset(t, k, v) end })

table.move(src, 1, 3, 1, dst)
assert(calls == 0, "table.move 가 메타메서드를 불렀다")
assert(rawget(dst, 1) == 1 and rawget(dst, 2) == 2)
assert(rawget(dst, 3) == nil, "원본 3번은 비어 있고 __index 를 거치지 않았다")

-- 대조군: 같은 복사를 손 루프로 하면 __index 와 __newindex 가 불린다
local dst2: any = setmetatable({}, { __newindex = function(t, k, v) calls += 1; rawset(t, k, v) end })
for i = 1, 3 do
	dst2[i] = src[i]
end
assert(calls > 0, "손 루프는 메타메서드를 부른다")
assert(rawget(dst2, 3) == 30)
print("ok", calls)
