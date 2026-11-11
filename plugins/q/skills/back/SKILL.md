---
name: back
description: 자리에 돌아왔다고 알린다. away 모드를 끄고 비운 동안의 비용, 띄운·줄 세운 서브에이전트, 예산 초과 여부를 요약한다. 사용자 호출 전용.
disable-model-invocation: true
allowed-tools: Bash(python3 *subagent_ledger.py *)
---

# back

아래는 `/q:back` 을 실행한 결과다(출력이 이미 있으면 다시 실행하지 않는다. 실행 지시만 있으면 그 명령을 한 번 실행한다).

!`python3 "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/lib/subagent_ledger.py" back ${CLAUDE_SESSION_ID}`

## 할 일
1. 위 요약을 사용자에게 보여 준다(숫자는 그대로).
2. 이어서 비운 동안 한 일을 3줄 이내로 덧붙인다: 끝낸 것, 진행 중인 것(실행 중인 서브에이전트 포함), 사용자 결정이 필요한 것.
3. 예산을 넘겼다면 어느 작업이 비용을 많이 썼는지, 다음에는 어떻게 줄일지(작은 모델, 작은 패스) 한 줄로 적는다.
