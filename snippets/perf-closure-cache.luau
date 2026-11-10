--!strict
--@run
-- 주장: 업밸류가 반복마다 바뀌지 않는 클로저 식은 반복마다 '같은 함수 객체'를 돌려준다(클로저 캐시). 할당이 없다.
--       반복 변수를 캡처하면 매번 새 객체다. GC 잔여를 세는 측정에서 "1개 남음"으로 보이는 원인이다.
-- 근거: 후보 Q-005, quad/.claude/audit/round13-e42-gc-sweep/README.md:92-93
local shared = 0
local a: { () -> number } = {}
local b: { () -> number } = {}
local c: { () -> () } = {}
for i = 1, 3 do
	a[i] = function() return shared end -- 바뀌지 않는 업밸류
	b[i] = function() return i end -- 반복 변수 캡처(대조군)
	c[i] = function() end -- 업밸류 없음
end
assert(rawequal(a[1], a[2]) and rawequal(a[2], a[3]), "고정 업밸류 클로저는 같은 객체")
assert(rawequal(c[1], c[3]), "업밸류 없는 클로저도 같은 객체")
assert(not rawequal(b[1], b[2]), "반복 변수를 캡처하면 새 객체")
print("ok")
