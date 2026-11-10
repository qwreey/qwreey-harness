---
name: luau-types
description: >-
  Luau 타입 시스템 질문·타입 에러 디버깅용. 제네릭(<T>, f<<T>> 명시 타입 인자), 변성·서브타이핑(read/write 필드),
  유니온/인터섹션/싱글턴, narrowing, 재귀·순환 타입 별칭, type function(types.*), 타입팩·가변 인자,
  new solver(LuauSolverV2) vs old solver 차이·알려진 결함, "Code is too complex to typecheck", --!strict/--!nocheck.
  타입 에러가 말이 안 되거나 에러가 나야 할 곳에서 안 날 때 사용. Roblox API 사용법·성능 측정에는 쓰지 않는다.
---
# luau-types (초안)

## 5대 원칙 (각 줄 = references 의 검증된 사실로 연결)
1. "진단 0건"을 믿지 말 것: 음성 대조군(일부러 틀린 대입)이 잡히는지 먼저 -> luau-verify
2. 한계를 우회하려고 API/타입을 비틀지 말 것: 문서화 + 사용 관례 + 되돌릴 링크
3. 추론으로 "된다/안 된다" 결론 금지: 15줄 스파이크를 `luau-analyze` 로 돌릴 것
4. `.luaurc` 한 단어에 의존하지 말고 모든 파일에 `--!strict`
5. 타입 함수: 기본 쓰지 않음 / 허용 = 진단 전용 / 금지 = 결과 타입 합성 (type-functions.md)

## 결정 트리
- 에러가 **나야 하는데 안 난다** -> solver-limits.md 의 결함 표에서 증상 검색 전에 generics.md §1(any 누수) -> variance.md(공변 누수) 순
- 에러가 **말이 안 된다**(엉뚱한 타입 이름, unknown) -> recursion-and-limits.md §2(선언 순서), unions-singletons.md
- 버전을 올렸더니 수치가 바뀌었다 -> solver-limits.md + solver-bugs.tsv

## 질문 -> 파일 라우팅 (본문 §4-4 표 참조)
| 증상 | 파일 |
|---|---|
| 타입 인자가 any/unknown 으로 샌다 | references/generics.md §1-2 |
| 콜백 주석이 안 잡힌다 | references/generics.md §3, solver-limits.md S1 |
| 읽기 전용/마커/브랜드 대입이 통과 | references/variance.md |
| 문자열이 string 으로 뭉개진다 | references/unions-singletons.md §1 |
| 재귀 타입에서 진단 증발 | references/recursion-and-limits.md §2 |
| Code is too complex | references/recursion-and-limits.md §3 |
| type function 을 쓰고 싶다 | references/type-functions.md |
