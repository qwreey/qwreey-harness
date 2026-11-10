---
name: away
description: 자리를 비운다고 선언한다. 세션 예산 상한과 서브에이전트 동시 슬롯을 정해, 넘치는 서브에이전트는 거절 대신 줄을 세운다(세션은 멈추지 않음). 사용자 호출 전용.
argument-hint: "[예산: 15 | $15 | 8a] [슬롯: 2]  |  status | off | reset"
disable-model-invocation: true
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/../../lib/subagent_ledger.py *)
---

# away

아래는 `/away` 를 실행한 결과다(출력이 이미 있으면 다시 실행하지 않는다. 실행 지시만 있으면 그 명령을 한 번 실행한다).

!`python3 ${CLAUDE_SKILL_DIR}/../../lib/subagent_ledger.py away ${CLAUDE_SESSION_ID} $ARGUMENTS`

## 할 일
1. 위 결과를 사용자에게 그대로 한두 줄로 전한다. 오류가 나왔으면 형식(`/away [예산] [슬롯]`)을 알려 준다.
2. 켜졌다면 이후 동작:
   - 서브에이전트를 띄우기 전에 남은 일의 규모를 보고, 작은 패스(찾기 → 리뷰 → 고치기 → 리뷰)를 순서대로 돈다.
   - `subagent-slots` 훅이 `queue: …` 로 거절하면 실패가 아니다. 실행 중인 에이전트의 완료 알림을 기다렸다가 다음 것을 띄운다.
     기다리는 동안 에이전트 없이 할 수 있는 일을 하거나 턴을 끝낸다. 같은 호출을 바로 다시 하지 않는다.
   - 예산을 넘겼다는 알림이 오면 남은 일마다 "sonnet 으로 되는가, 더 작은 패스로 나눌 수 있는가"를 따져 보고 다음 보고에 적는다.
   - 사용자가 돌아와 `/back` 하면 요약이 나온다.

## 인자
- 예산: 숫자 또는 `$숫자` 는 API 목록가 환산 USD(메인 + 서브에이전트, `/away` 이후). `8a` 는 서브에이전트 8개.
  생략하면 `HARNESS_AWAY_BUDGET_USD`(기본 20).
- 슬롯: 동시에 돌 서브에이전트 수. 생략하면 `HARNESS_AWAY_SLOTS`(기본 2). 예산을 넘기면 `HARNESS_AWAY_OVER_SLOTS`(기본 1).
- `status` 지금 상태, `off` 끄기(= `/back`), `reset` 슬롯 카운터 비우기(카운트가 어긋났을 때).
- 설계와 문턱값: claude-doctor `audit/21-cost-disclosure.md`.
