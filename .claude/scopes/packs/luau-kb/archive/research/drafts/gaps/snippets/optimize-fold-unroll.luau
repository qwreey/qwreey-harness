--!strict
--@run
-- 주장: 상수 접기는 -O1 에서도 된다(산술, 문자열 연결, if-식, #"리터럴", 로컬 상수 전파). 내장 함수 호출 접기(math.sqrt(16))와
--       고정 횟수 루프 펼치기는 -O2 에서만 된다. 펼치기는 반복 수가 작을 때만(100 회는 "too many iterations").
--       tools/run_opt.sh 가 luau-compile --text/--remarks 로 검사한다. 이 파일 자체는 실행 결과가 레벨과 무관함을 assert 로 보인다.
-- 근거: Compiler/src/Compiler.cpp compileOrThrow("builtin folding is enabled on optimization level 2"), luau.org/performance
local K = 10
local a = K * 2 + 1
local b = math.sqrt(16)
local c = "a" .. "b"
local d = if K > 5 then "big" else "small"
local e = #"hello"
local s = 0
for i = 1, 4 do s += i * 2 end
local s2 = 0
for i = 1, 100 do s2 += i end
assert(a == 21 and b == 4 and c == "ab" and d == "big" and e == 5 and s == 20 and s2 == 5050)
print(a, b, c, d, e) -- 접힌 상수를 바이트코드에 남긴다(run_opt.sh F1, F2 가 본다)
