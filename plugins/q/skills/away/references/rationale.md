# q:away 설계 근거

- 설계와 문턱값(1단계 = 정한 예산, 2단계 = 두 배, 슬롯, USD 보강)은 claude-doctor `audit/21-cost-disclosure.md` 에 있다.
- "쉬운 설명" 블록은 모델용 지시가 아니라 사용자에게 그대로 전달하는 안내문 원고라 한국어로 유지한다(audit/24 §4 언어 정책).
- `disable-model-invocation` 과 `allowed-tools: Bash(python3 *subagent_ledger.py *)` 는 audit/24 §4-7 기준에 맞는 값이라 바꾸지 않았다.
