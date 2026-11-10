---
name: audit
description: >-
  감사형 second opinion. 새 컨텍스트의 읽기 전용 리뷰어에게 짧은 브리프(목표·제약·검증할 주장)만 넘기고, diff·파일·
  테스트·사용자 원문은 리뷰어가 직접 보고 반증한다. 쓰는 때: 커밋·완료 선언 전 diff 검증, 같은 실패가 2번 이상 났을 때,
  구현이 주장대로 동작하는지(테스트·프로브·설치본 대조) 확인할 때, 되돌리기 어려운 접근을 확정하기 전.
  잘 잡는 것: 재현되는 구현 버그, 정본·설치본 차이, 말한 것과 한 것의 차이. 잘 못 잡는 것: 대화에만 있던 맥락
  (병행 작업 영향, 미결 질문)은 second-opinion:context. 비용: 메인 맥락 크기와 무관(브리프 + 리뷰어가 읽은 것),
  대신 도구 턴이 많아 1회 opus $1.0~1.2, sonnet 약 $0.4, 2~3분. `<harness-hook name="second-opinion">` 알림이나
  /second-opinion:audit, "검토 받아" 때도 쓴다. advisor 대신 쓰는 기본 검증 경로다.
argument-hint: "[plan|stuck|done] [범위 또는 한 줄 메모]"
---

# second-opinion:audit — 정해진 시점에, diff 를 독립된 눈으로

같은 묶음의 `second-opinion:context` 는 대화를 이어받아 흐름에서 놓친 것을 보고, 이 스킬은 diff 와 주장을 반증한다(`audit/18` §9, §11: 둘이 잡는 문제는 거의 겹치지 않았다).
advisor 는 대화 전체를 받아 맥락은 정확하지만 메인 관점에 끌려가고, 언제 부를지가 모델 판단이라 예측이 안 되며,
Opus 5 이상 advisor 의 조언은 암호화돼 사용자가 읽을 수 없다(`audit/18` §1). 이 스킬은 그 반대편이다.
- **언제**: 아래 시점표(훅이 알려 주는 것 + 메인 판단 하나)
- **누가**: 새 컨텍스트의 `second-opinion-reviewer`(읽기 전용). 강도는 저장소 등급으로 고정
- **무엇을 넘기나**: 목표·제약·검증할 주장 몇 줄. 사용자 원문은 리뷰어가 트랜스크립트에서 직접 뽑는다
- **결과**: 요약하지 않고 그대로 사용자에게. 받아들인 것과 버린 것을 원장에 남긴다

## 1. 시점과 강도

저장소 등급은 `~/.claude/harness.env` 의 `HARNESS_REVIEW_TIERS` 에 있다(없으면 `mid`). 훅도 같은 표를 쓴다.

| 시점 (kind) | 누가 알리나 | high | mid | low |
|---|---|---|---|---|
| 접근 확정 전 (`plan`) — 되돌리기 어려운 설계, 공개 API·데이터 형식·보안, 작업이 여러 파일·여러 단계 | 메인 판단(ExitPlanMode 를 쓰면 훅) | opus | sonnet | 생략 |
| 같은 실패 2회 (`stuck`) | 훅 `PostToolUseFailure` | opus | sonnet | sonnet |
| 완료·커밋 전 (`done`) — diff 가 임계 이상 | 훅 `PreToolUse(git commit)`, `Stop` | opus | sonnet | 생략 |

- 리뷰어 모델은 호출 인자로 정한다: `Agent(subagent_type="second-opinion-reviewer", model="sonnet")`. frontmatter 기본은 opus 다.
- haiku 는 쓰지 않는다(판단이 결과에 남는 일).
- 한 작업 단위에 `done` 검토는 한 번. 고친 뒤 다시 돌리는 것은 "반드시" 발견을 고쳤을 때만, 그 항목 범위로만.
- 다른 회사 모델의 시각이 필요한 취향 판단(이름, API 모양)은 이 스킬이 아니라 `/debate`. 전수 감사는 `/audit`(이 스킬은 플러그인 이름공간 `second-opinion:audit` 이라 겹치지 않는다). 보안 전수는 `/security-review`.
- 사용자가 예산을 좁혀 두었으면(프로젝트 CLAUDE.md·memory) 그것이 이긴다. 그때는 한 단계 낮춘다(opus→sonnet, sonnet→생략)고 응답에 밝힌다.

## 2. 브리프 쓰기 (메인, 5~15줄)

`templates/brief.md` 를 채운다. 넣는 것과 넣지 않는 것:
- 넣는다: 목표 한두 줄, 지켜야 할 제약, 범위(`git` 범위, 경로, 계획 파일), **검증할 주장**(내가 사용자에게 "했다/된다/안전하다"고 말하려는 것), 이미 기각된 갈래, 트랜스크립트 경로(모르면 생략. 리뷰어가 `CLAUDE_CODE_SESSION_ID` 로 찾는다)
- 넣지 않는다: 사용자 요구의 내 요약(리뷰어가 원문을 직접 본다), 내 결론의 근거 설명(앵커링), 파일 내용 붙여넣기(리뷰어가 직접 읽는다)
- 내가 가장 자신 없는 부분을 빼지 않는다. 그 부분이 검토의 이유다.
- **병행 작업을 "범위 밖"으로 적지 않는다.** "이 변경이 영향을 줄 수 있는 곳"으로 넘긴다. §9 재현에서 리뷰어가 병행 작업 쪽 위험을 놓친 직접 원인이었다.
- 메인이 사용자에게 던지고 답을 못 받은 질문이 있으면 한 줄로 넣는다(`user-asks.py --claims 3` 로 뽑아도 된다).

## 3. 부르기

```
Agent(subagent_type="second-opinion-reviewer", model="<opus|sonnet>",
      description="second opinion: <kind>", prompt=<브리프>)
```
- 백그라운드로 띄우고 다른 일을 해도 되지만, `done` 검토는 결과를 받기 전에 완료를 선언하지 않는다.
- 리뷰어가 실패하거나 maxTurns 에 닿으면 "검토 미완"으로 사용자에게 알리고, 다시 띄우지 않는다(폭주 방지).

## 4. 결과 다루기

1. 리뷰어 보고를 **요약하지 않고 그대로** 사용자에게 보인다(인용 블록 또는 그대로 붙임). 그 아래에 내 판단을 따로 쓴다.
2. 발견마다 받아들임 / 버림 / 확인 필요를 정하고, 버리면 근거(파일:줄, 실행 결과)를 댄다. 리뷰어와 내 증거가 부딪히면 실측으로 가린다.
3. 원장에 남긴다.
   ```bash
   python3 -I <이 스킬>/scripts/review-ledger.py add --kind done --reviewer opus-sub \
     --trigger hook:commit --verdict 고친뒤진행 --found 4 --adopted 3 --must 1 --note "MANIFEST 누락"
   ```
   훅 알림으로 왔으면 `--trigger hook:<commit|stop|failure|plan>`, 스스로 판단했으면 `self`, 사용자가 시켰으면 `user`.

## 5. 비용 [실측, §9.4]

- 리뷰어는 새 컨텍스트라 메인의 캐시를 쓰지 못한다. 대신 맥락이 메인 길이와 무관하다(첫 쓰기 약 6만 토큰: 시스템 + 브리프).
- 비용은 도구 턴 수가 정한다. §9 에서 opus 21~29턴 $0.96~1.17(200초 안팎), sonnet 16턴 $0.42(103초).
- 그래서 촘촘하게 부르는 용도가 아니다. 작업 단위당 `done` 한 번이 기본이다.

## 6. 측정

- 검토 효과: `review-ledger.py stats` — 종류·검토자·트리거별 발견, 채택률, "발견 없음" 비율. 채택률이 낮은 트리거는 임계를 올리거나 끈다.
- advisor 와 비교할 때: `advisor-stats.py --all` 로 advisor 호출 수, 결과 종류, 토큰, API 환산 비용, 직후 메인 반응을 본다.
- 사용자 원문 추출만 필요할 때: `user-asks.py [--since-compact] [--last N] [--claims K]`.
