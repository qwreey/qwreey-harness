--@luaurc {"languageMode": "nonstrict"}
--@args --fflags=DebugLuauForceStrictMode=true
-- 주장: luau-analyze 는 --fflags=이름=true|false 로 불리언 FFlag 를 바꿀 수 있다(--help 에는 나오지 않는다).
--   예: DebugLuauForceStrictMode=true 는 .luaurc 의 nonstrict 와 --!strict 없음에도 파일을 strict 로 검사한다.
--   같은 파일을 --fflags 없이 돌리면 아래 줄은 0건이다(짝: modes-luaurc-nonstrict-silences.luau 의 같은 조건).
--   모르는 이름은 stderr 에 "Warning: unrecognized flag", 정수 한도(LuauTypeInferIterationLimit=10 등)는
--   "Warning: unrecognized value" 로 무시되고 rc 에 영향이 없다. 정수 한도는 luau-lsp --flag: 로만 바뀐다.
-- 근거: luau 0.742 소스 CLI/src/Analyze.cpp:434(--fflags=), CLI/src/Flags.cpp(불리언 FValue 만 순회). 0.734, 0.742 실측.
--   후보 S-129, claude-doctor .claude/scopes/packs/luau-kb/audit/09 6 모순 1. 이 저장소의 옛 서술("플래그 옵션이 없다")을 정정한다.
local x: number = "a" -- expect-error: Expected this to be 'number', but got 'string'
print(x)
