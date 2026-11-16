--!strict
-- 주장: 진단용 type function 은 '그 타입이 실제로 대조되는 자리'에서만 평가된다.
--   - 제네릭 없는 별칭 선언은 쓰이지 않아도 바로 평가된다(type Unused = F<number>). 프라이밍이 이 성질을 쓴다.
--   - 캐스트(`::`)나 값 대입이 있는 주석 자리는 평가된다.
--   - `any` 를 대입한 주석 자리(`local c: Checked<string> = nil :: any`)는 대조가 없어 진단이 0건이다.
--   - 제네릭 함수 몸통 안의 지역 별칭(`type _C = Check<T>`)은 호출마다 다시 평가되지 않아 진단이 0건이다.
--   - 반환 타입 자리에 두면 호출부마다 평가된다.
--   - 같은 인스턴스(Checked<string>)의 print 메시지는 처음 평가한 자리에 한 번만 뜬다. 다음 자리는 "unreachable" 만 남는다.
-- 근거: quad/.claude/base/typing-limits.md 6 "그래서 우리가 하는 것" 2), quad/.claude/base/quad-types-plan.md:253-278,
--       quad/.claude/audit/type-recursive-issue-try-callback/REPORT.md:192-196(지연 평가)
type function MustLit(t: type): type
	if t.tag == "singleton" then
		return types.singleton(true)
	end
	print("MustLit: got " .. t.tag)
	return types.never
end
type Unused = MustLit<number> -- expect-error: MustLit: got number
type Checked<T> = { __check: MustLit<T> }
local _c1 = (nil :: any) :: Checked<string> -- expect-error: MustLit: got string
local _c2: Checked<string> = nil :: any -- bug-present
local _c3: Checked<string> = { __check = true } -- expect-error: Expected this to be unreachable
local function inBody<T>(x: T): T
	type _C = MustLit<T>
	return x
end
local _r1 = inBody("x" :: string) -- bug-present
local function retSite<T>(_x: T): Checked<T>
	return nil :: any
end
local _r2 = retSite("x" :: string) -- expect-error: MustLit: got string
local _ok = retSite("x" :: "x")
