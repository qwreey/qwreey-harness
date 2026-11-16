# Q 2라운드

**받아들인 것 (내 안에 반영)**
- 앞 문장: P 가 맞다. 공식 스킬은 하는 일을 동사로 시작한다. 또 "Get yourself … on your own initiative" 는 구어라서 사용자가 "second opinion 좀" 이라고 할 때와 겹쳐 읽힌다. P 의 "Get a second opinion on your own thinking." 과 "… from fresh eyes." 를 그대로 쓴다. "on your own thinking" 이 이미 이 검토가 '나'의 것임을 표시하므로, 앞으로 올리려던 자율 신호는 끝의 "The call is yours" 가 맡는다.
- "findings feed your next step, not a report": 결과 처리라서 본문에 갈 내용이다. 뺐다. 이유(why)는 P 의 "the review serves your next step" 이 더 짧게 말하므로 그것으로 바꿨다.
- 괄호 목록 "(premises, missed requests, …)" 는 나열이다. 뺐다. 구분은 P 의 "your reasoning, not your diff" 로 한다.
- "The call is yours: … so the user does not need to ask" 를 채택한다. "does not need" 는 사용자 요청 경로를 막지 않는다.

**반박 (논점 1, 발동 기준)**
- 원함 기준 "whenever you want another view" 는 맹점이 있는 바로 그 장면에서 꺼진다. 보이지 않는 것은 원하게 되지 않는다. P 도 자기 실패 목록에서 "description 으로 '원함'을 만들 수는 없다" 고 인정했다. 0/4 도 원함이 생기지 않은 경우다(§9). 이 기준이라면 description 이 할 일을 CLAUDE.md 와 훅에 떠넘긴다.
- 과발동을 막는 장치는 장면을 나열하지 않고 원리 두 개로 건다.
  - (a) 시점: "before you act on or report". 결정하는 행동 직전으로 한정한다. 중간 사고 단계에서는 걸리지 않는다.
  - (b) 무게: "that would be costly to get wrong". 기준은 하나다. 판단은 Claude 에게 맡긴다("Claude is already very smart").
  - 상태 기준 "only you have checked" 는 남긴다. 혼자 점검하고 끝내는 0/4 행동을 직접 겨냥하는 유일한 구절이다.
- fresh 는 "your work is done or correct" 로 좁혔다. 대상이 작업물 주장이라서 사실 질문에 답할 때마다 opus 를 부르지 않는다.
- P 의 두 마지막 문장은 서로 같다. P 스스로 "그 문장으로는 둘을 가를 수 없다" 고 썼다. 내 안은 두 문장을 갈랐다. inherit 는 판단을 실행하거나 보고하기 직전, fresh 는 작업이 끝났거나 맞다고 사용자에게 말하기 직전이다.

**최종안**
- inherit-advisor (408자): "Get a second opinion on your own thinking. Forks you, with this conversation's prompt cache, into a reviewer that steps out of your role and challenges your reasoning, not your diff. Reach for it before you act on or report a judgment that only you have checked and that would be costly to get wrong. The call is yours: the review serves your next step, so the user does not need to ask. 한 번 더 봐줘, 다른 눈으로 검토."
- fresh-advisor (455자): "Get a second opinion from fresh eyes. Spawns a read-only reviewer in a new context with a short brief; it reads the changes and the user's own words itself and tries to refute your claims. Where a code review hunts defects in a diff, this tests your claims against what the user asked. Reach for it before you tell the user your work is done or correct when only you have verified it. The call is yours, so the user does not need to ask. 커밋 전 검토, 완료 전 검증."
- 글자 수는 python len 으로 쟀다.
- 이제 P 안과 다른 곳은 사용 조건 문장 하나뿐이다(앞 문장, 이유, 구분 구절은 같다). 아래 시험이 그 한 문장만 가른다.

**판정 시험 (이 결과를 받아들인다)**
- 양성 장면: P 가 제안한 장면을 쓴다. 메인이 "끝, apply 안내 쓰겠다" 직전이고, 메인의 마지막 응답에 적히지 않은 약점 하나를 심는다.
  - 변형 하나를 더 둔다. 메인이 다른 약점을 스스로 짚어 둔 장면이다. 0/4 처럼 혼자 점검했다는 상태를 재현한다.
- 음성 장면 3개: 무관 질의, 변수 이름 바꾸기 뒤 "됐어", "이 diff 커밋 전에 버그 봐줘"(정답은 `/code-review` 또는 직접 처리).
- 확인 장면 1개: "한 번 더 봐줘". 두 안 모두 발동해야 한다.
- 방법: sonnet `-p --resume --fork-session --plugin-dir` 로 돌린다. description 만 바꾸고 목록에 code-review 를 같이 둔다. 각 장면·각 안을 N=10 씩 돌린다.
- 잴 것: 양성 두 장면의 자발 발동률(20회 중), 음성 세 장면의 오발동(30회 중).
- 판정:
  - Q 안이 이기려면 두 조건을 모두 채워야 한다. 양성 발동이 P 안보다 4/20 이상 높고, 오발동이 3/30 이하이면서 P 안보다 2회 넘게 많지 않아야 한다.
  - 그렇지 않으면 P 안을 쓴다. 동률이면 사용자가 선호한 더 단순한 P 안이다.
  - 확인 장면에서 실패한 안은 실격이다.
- 비용: 회당 약 $0.05 로 잡으면 약 120회, $6 안팎이다(§9 단가로 추정). 예산이 $2 이면 N=4 로 줄이고 판정선도 같은 비율로 낮춘다. 그 경우 결과는 방향만 본다.
