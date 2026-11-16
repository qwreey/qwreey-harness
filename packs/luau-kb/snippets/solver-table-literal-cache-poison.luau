--!strict
-- 주장: 제네릭 함수를 담은 테이블 리터럴을 인자 자리에 두면, 읽기, 쓰기 필드의 불변 비교가 실패하고(위양성) 그 실패가
--       Subtyping 캐시에 남아 같은 모듈 뒷줄의 멀쩡한 비교(takeFn(id))까지 실패시킨다. 두 줄의 순서를 바꾸면 takeFn(id) 는 통과한다
--       (solver-table-literal-read-field-ok.luau 가 같은 비교를 오염 없이 돌린다). 원인 줄이 아닌 곳에 에러가 보이면 이것을 의심한다.
-- 근거: 실측. 원천 stl-luau-doctor/.claude/audit/luau-solver-issues/DRAFTS.md:194-202, research/luau-source/opus-probes/p5/12-poison.luau,
--       13-nopoison.luau (후보 S-139, 0.742 Subtyping.cpp:722 캐시)
local function id<T>(x: T): T return x end
type Spec = { process: (x: number) -> number }
local function takeFn(f: (x: number) -> number) end
local function takeSpec(s: Spec) end
takeSpec({ process = id }) -- expect-error: Expected this to be
takeFn(id) -- expect-error: Expected this to be
