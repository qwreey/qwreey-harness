--!strict
-- 주장: solver-table-literal-cache-poison.luau 의 우회. 받는 타입의 필드를 `read` 로 적거나(공변 비교), 리터럴을 주석 단 지역에
--       먼저 담으면 제네릭 함수 필드가 통과하고 캐시도 오염되지 않아 뒤의 takeFn(id) 가 통과한다.
-- 근거: 실측(0.734, 0.742). 후보 S-139
local function id<T>(x: T): T return x end
type Spec = { process: (x: number) -> number }
type RSpec = { read process: (x: number) -> number }
local function takeFn(f: (x: number) -> number) end
local function takeSpec(s: Spec) end
local function takeR(s: RSpec) end
takeR({ process = id })
local sp: Spec = { process = id }
takeSpec(sp)
takeFn(id)
takeFn(function(x: string) return 1 end) -- expect-error
