--!strict
-- 주장: type function 의 결과는 별칭 이름을 잃는다. 진단 메시지와 `--annotate` 에 구조 전체가 펼쳐져 나온다.
--       같은 값을 별칭으로 직접 주석하면 메시지에 `Big` 이 나온다.
--       hover 는 둘 다 펼쳐서 보여 준다(luau-lsp 1.69.0·1.70.1, tools/lsp_probe.py). 차이는 메시지와 annotate 에 있다.
--       type function 이 만든 테이블에서도 키 자동완성은 된다.
--       반면 줄지 않은 `index<Map, K>` 파라미터를 가진 무주석 콜백은 hover 가 `unknown` 이고 `v.` 자동완성도 없다(tf-dx-hover.luau).
-- 근거: quad/.claude/audit/decl-typefn-probe-2026-10-16/REPORT.md:9-10,43,577-579(hover 펼침), 8.7 ③ 2026-10-16 정정
type function Pass(t: type): type
	return t
end
type Big = { alpha: number, beta: string }
local viaTf = (nil :: any) :: Pass<Big>
local direct = (nil :: any) :: Big
local _s1: string = viaTf -- expect-error: got '{ alpha: number, beta: string }'
local _s2: string = direct -- expect-error: got 'Big'
