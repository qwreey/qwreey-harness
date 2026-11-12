--!strict
-- 주장: 새 솔버의 "넘친 인자 무진단"(pack-extra-args.luau)은 호출 대상의 타입이 함수 '정의'에서 왔는지로 갈린다.
--   잡힘: 함수 타입 주석을 단 지역, 함수 타입 파라미터, 생성 뒤 필드에 캐스트로 대입(M.f = f :: Fn), 빈 테이블을 주석 타입으로 만든 뒤 대입.
--   안 잡힘: function M.h 정의, 메서드, 함수 리터럴 지역, 제네릭 함수, 정의를 그대로 받은 별칭 지역,
--            주석 단 테이블을 리터럴로 초기화({ k = take }), 리터럴 안의 캐스트({ k = take :: Fn }), 그런 필드를 읽어 둔 지역.
--   모듈 경계(require)를 넘어도 같다: 다른 모듈의 function M.f 는 안 잡히고 M.h = g :: Fn 는 잡힌다(수동 실측, 0.734/0.742).
-- 근거: 실측(luau-analyze 0.734, 0.742 새 솔버). 옛 솔버는 아래 모든 줄을 잡는다(pack-extra-args-old.luau 와 같은 성질).
local function take(a: number, b: number) end
type Fn = (number, number) -> ()
local M = {}
M.f = take :: Fn
M.f(1, 2, 3) -- expect-error: Argument count mismatch
local g: Fn = take
g(1, 2, 3) -- expect-error: Argument count mismatch
local function useParam(cb: Fn) cb(1, 2, 3) end -- expect-error: Argument count mismatch
local R = {} :: { k: Fn }
R.k = take
R.k(1, 2, 3) -- expect-error: Argument count mismatch
function M.h(a: number, b: number) end
M.h(1, 2, 3) -- bug-present
local O = {}
function O:m(a: number) end
O:m(1, 2) -- bug-present
local lam = function(a: number) end
lam(1, 2) -- bug-present
local function gen<T>(a: T) end
gen(1, 2) -- bug-present
local alias = take
alias(1, 2, 3) -- bug-present
local N: { k: Fn } = { k = take }
N.k(1, 2, 3) -- bug-present
local Q = { k = take :: Fn }
Q.k(1, 2, 3) -- bug-present
local read = N.k
read(1, 2, 3) -- bug-present
local _ = useParam
