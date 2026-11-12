--!strict
-- 주장: 괄호 타입 목록은 함수 타입의 일부로만 쓸 수 있다. `type M = (number, string)` 같은 "튜플 별칭"은 구문 에러다.
-- 근거: rfcs docs/syntax-type-alias-type-packs.md "Type alias can't result in a type pack"
type M = (number, string); local _ = 1 -- expect-error: Expected '->' when parsing function type
-- (파서는 다음 토큰에서 '->' 를 기대하므로 같은 줄에 다음 문장을 두어 진단 줄을 고정한다)
