## 검토(second opinion) — 두 갈래, 정해진 시점에
- advisor 는 평소에 쓰지 않는다(가격 대비 효용이 diff 기반 리뷰보다 낮다). 선택이며 사용자가 요청할 때만 `claude --advisor <model>` 로 그 세션에만 켠다.
- `second-opinion:context`: 대화를 이어받은 fork 를 독립 검토자로 돌려 세운다. 작업 단위를 끝내고 넘어가기 직전, 결정·방향·apply 안내를 사용자에게 말하기 직전에 부른다. 스킬의 후행 프롬프트(역할 전환 + 사각지대 범주)를 그대로 쓴다.
- `second-opinion:audit`: 새 컨텍스트 리뷰어(`second-opinion:reviewer`, 읽기 전용). 커밋·완료 선언 전 diff, 같은 실패 2회, 구현 검증. 반복 실패와 큰 커밋은 `<harness-hook name="second-opinion">` 이 알려 준다. 강도는 저장소 등급(`HARNESS_REVIEW_TIERS`)으로 정한다.
- 리뷰어에게는 목표·제약·검증할 주장만 짧게 준다. 병행 작업은 "범위 밖"이 아니라 "영향받을 수 있는 곳"으로 넘긴다.
- 결과는 요약하지 않고 그대로 전달하고, 받아들임/버림을 근거와 함께 밝힌 뒤 원장(`review-ledger.py add`)에 남긴다.
