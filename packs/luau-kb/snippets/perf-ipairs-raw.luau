--!strict
--@run
-- 주장: ipairs 와 일반화 for(for k, v in t, __iter 없음)는 메타테이블의 __index 를 보지 않고 raw 로 돈다.
--       그래서 MT 가 붙은 배열을 이 둘로 돌면 정수 칸 세금이 없다(bench/iter-forms.luau 의 mt-array 그룹).
--       반대로 t[i] 인덱싱은 __index 를 탈 수 있다(대조군). 의미가 다르므로 바꿔 쓸 때 확인한다.
-- 근거: 후보 S-P06, luau 0.734, 0.742 실측(이 파일)
local mt: { number } = setmetatable({ 1, 2 }, {
	__index = function(_, i: number): number?
		return if i == 3 then 3 else nil
	end,
}) :: any
local n1 = 0
for _, _v in ipairs(mt) do -- 변수 하나(for _ in ipairs)는 새 솔버가 "Argument count mismatch" 를 낸다(0.734, 0.742)
	n1 += 1
end
local n2 = 0
for _ in mt do
	n2 += 1
end
assert(n1 == 2, "ipairs 는 __index 가 주는 3번을 보지 않는다")
assert(n2 == 2, "일반화 for 도 raw 로 돈다")
-- 대조군: 인덱싱은 __index 를 탄다
assert((mt :: any)[3] == 3)
print("ok", n1, n2)
