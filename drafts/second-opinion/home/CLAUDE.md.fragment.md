## 검토(second opinion) — 정해진 시점에, 독립된 눈으로
- advisor 는 쓰지 않는다(꺼 둠). 독립 검토는 `second-opinion` 스킬로 `second-opinion-reviewer`(새 컨텍스트, 읽기 전용)를 부른다.
- 시점: ① 되돌리기 어려운 접근을 확정하기 전(내 판단) ② 같은 실패 2회 ③ 완료·커밋 선언 전. ②③은 `<harness-hook name="second-opinion">` 이 알려 준다.
- 강도는 저장소 등급(`harness.env` `HARNESS_REVIEW_TIERS`)으로 정한다: high=opus, mid=sonnet, low=②만, off=없음. 프로젝트 예산 지침이 더 좁으면 그쪽을 따른다.
- 리뷰어에게는 목표·제약·검증할 주장만 짧게 준다. 사용자 원문, diff, 테스트는 리뷰어가 직접 본다.
- 리뷰 결론은 요약하지 않고 그대로 전달하고, 받아들임/버림을 근거와 함께 밝힌 뒤 원장(`review-ledger.py add`)에 남긴다.
