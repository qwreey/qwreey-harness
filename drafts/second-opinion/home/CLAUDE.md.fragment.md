## 검토(second opinion) — 두 갈래, 정해진 시점에
- advisor 는 쓰지 않는다(꺼 둠). 두 도구를 시점에 따라 고른다. 둘은 잡는 문제가 거의 겹치지 않는다(audit/18 §11).
- `second-opinion:context`: 대화를 이어받은 눈. 작업 단위를 끝내고 넘어가기 직전, 결정·방향을 사용자에게 제안하기 직전에 fork 로 싸게 부른다. apply·배포·되돌리기 어려운 확정 직전에는 다른 프레임(`ask-other-frame.py`)으로 부른다.
- `second-opinion:audit`: 새 컨텍스트 리뷰어(`second-opinion-reviewer`, 읽기 전용). 커밋·완료 선언 전 diff, 같은 실패 2회, 구현 검증. ②③은 `<harness-hook name="second-opinion">` 이 알려 준다. 강도는 저장소 등급(`HARNESS_REVIEW_TIERS`)으로 정한다.
- 리뷰어에게는 목표·제약·검증할 주장만 짧게 준다. 병행 작업은 "범위 밖"이 아니라 "영향받을 수 있는 곳"으로 넘긴다.
- 결과는 요약하지 않고 그대로 전달하고, 받아들임/버림을 근거와 함께 밝힌 뒤 원장(`review-ledger.py add`)에 남긴다.
