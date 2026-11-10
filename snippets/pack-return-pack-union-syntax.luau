--!strict
-- 주장: 반환 팩끼리의 유니온 `(boolean, T...) | (false, E)` 는 쓸 수 없다. 괄호 목록은 함수 타입의 인자·반환 자리에만 오므로
--       파서가 '|' 를 만나는 순간 "Expected '->'" 구문 에러를 낸다. 성공/실패를 나눠 돌려주려면 레코드 유니온
--       ({ ok: true, value: T } | { ok: false, err: E })이나 `-> (boolean, T...)` 하나로 적는다(pcall 과 같은 한계).
-- 근거: 실측. 원천 mrow/review/REVIEW.md:840-845 (후보 M-09)
type P<T...> = (number) -> ((boolean, T...) | (false, string)); local _ = 1 -- expect-error: Expected '->' when parsing function type, got '|'
