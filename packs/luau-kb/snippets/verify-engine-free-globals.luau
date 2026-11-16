--!strict
-- 주장: 엔진 무관이어야 하는 패키지는 Roblox 정의 파일 없이(luau-analyze, 또는 luau-lsp --platform=standard) 검사하면
--   Roblox 전역 사용이 "Unknown global" 타입 에러로 드러난다. 이것이 '엔진 무관 보장' 게이트다(Roblox 그룹만 정의 파일로 본다).
--   함정: typeof(v) == "Instance" 처럼 문자열 비교에 쓴 Roblox 클래스 이름은 타입 에러가 아니라 UnknownType 린트(rc=0)다.
--   `(typeof(v) :: string) == "Instance"` 로 쓰면 린트도 사라진다(하네스는 린트를 판정하지 않으므로 수동 확인, RESULTS.md).
-- 근거: 후보 Q-114(quad scripts/test.sh:28-31,42-44), Q-115(quad archive m5-implementation-round14.md:47). luau 0.734, 0.742,
--   luau-lsp 1.70.1 analyze --platform=standard 도 같은 두 줄을 잡는다(수동).
local p = game:GetService("Players") -- expect-error: Unknown global 'game'
local part = Instance.new("Part") -- expect-error: Unknown global 'Instance'
local function isInst(v: unknown): boolean
	return (typeof(v) :: string) == "Instance"
end
print(p, part, isInst(1))
