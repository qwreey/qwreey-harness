--!strict
-- 주장: 자기 참조 함수 필드를 가진 테이블 타입 A 를, 모양이 다른 자기 참조 타입 B 의 옵셔널(`B?`)에 대입하면 진단이 없다.
--       `B` 에 대입하면 잡힌다. 제네릭도 메서드 이름 충돌도 없는 최소 꼴이다(unions-recursive-in-optional, unions-same-name-method-hole 과 같은 계열).
-- 근거: 실측. 원천 moonwave-luau/.claude/audit/mrow-spike/README.md:127-147, mrow/review/REVIEW.md:774 (후보 M-19)
type A = { f: (A) -> string }
type B = { f: (B) -> number }
local a: A = (nil :: any)
local b1: B = a -- expect-error: Expected this to be 'B', but got 'A'
local b2: B? = a -- bug-present
local _ = b1, b2
