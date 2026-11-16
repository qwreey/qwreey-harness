# Q 1라운드: A 의 앞 문장 모양은 살리고, 자율과 '나 자신의 것'을 맨 앞 구절로 올린다 (제3안)

**1. 제안**
- inherit-advisor (466자): "Get yourself a second opinion, on your own initiative: forks you, with this conversation's prompt cache, into a reviewer that steps out of your role and challenges your reasoning (premises, missed requests, the design you just called done). It reviews your thinking, not a diff. Call it yourself before you act on or report a judgment that only you have checked; the user does not need to ask, and the findings feed your next step, not a report. 한 번 더 봐줘, 다른 눈으로 검토."
- fresh-advisor (460자): "Get yourself a fresh-eyes second opinion, on your own initiative: spawns a read-only reviewer in a new context that gets your claims in a short brief, reads the changes and the user's own words itself, and tries to refute them. Where a code review hunts defects in a diff, this tests your claims against what the user asked. Call it yourself before you tell the user that something only you have verified is done or true; no one needs to ask. 커밋 전 검토, 완료 전 검증."
(글자 수는 python len 으로 셌다. 한글도 한 글자씩 셌다.)

**2. 사용 조건 문장, 구절별로**
- "Call it yourself": 부르는 사람을 모델로 정한다. 사용자 요청과 맞춰 보는 스킬이 아니라는 뜻이다. 공식 내장 스킬처럼 명령형이다.
- "before you act on or report": 시점은 나열하지 않는다. 행동 두 가지(실행할 때, 말할 때)만 둔다. 4c9d6d6 의 시점 목록(결론, 결정, apply…)을 동사 둘로 줄인 셈이다.
- "a judgment that only you have checked": 이 문장의 핵심이다. A 와 B 의 "whenever you want another view" 는 욕구에 기대는데, 맹점은 원래 보이지 않으니 그 욕구도 생기지 않는다. 실측 0/4 가 바로 그 모양이었다. 모델이 혼자 약점을 짚었고 "이미 점검했다"고 여겨 부르지 않았다. "혼자만 점검했다"는 그 상태 자체를 발동 조건으로 바꾼다. 여전히 에이전트 자신의 필요다(요구 4). 다만 자기 점검이 끝난 상태에서도 참이 된다(추론).
- "the user does not need to ask": 요구 3 의 해석을 하나로 고정한다. A 의 "review request" 는 누구의 요청인지 모호하다. 사용자의 요청일 수도, `<harness-hook name="second-opinion">` nudge 일 수도 있다. 그래서 "훅을 기다리지 말라"로도 읽힌다(추론). 이 문장은 주어를 the user 로 못박는다.
- "findings feed your next step, not a report": 본문의 "스스로 부른 검토는 1~3줄" 규칙을 발동 단계에서 미리 알린다. 부르는 일이 사용자에게 보고를 늘리는 일로 보이지 않게 한다.
- "It reviews your thinking, not a diff" / "Where a code review hunts defects…": `/code-review`("Review the current diff … for correctness bugs")와 대상을 가른다(요구 5). 같은 목록에서 둘을 고를 때 쓸 단서다.
- fresh 의 "that something only you have verified is done or true": 같은 원리를 완료·사실 주장에만 좁혔다. opus 를 쓰는 비싼 경로라서 inherit 보다 덜 pushy 하게 둔다.

**3. 내 안의 예상 실패**
- 과다 발동: 혼자만 점검한 판단은 거의 모든 걸음에 해당한다. 사소한 답에서도 부를 수 있다. 막는 장치는 본문의 "once per turning point" 와 tier 뿐이다. description 에는 막는 말이 없다.
- 두 스킬이 완료 직전에 겹친다. 어느 쪽을 쓸지는 'fork 대 새 컨텍스트'와 '행동 대 사용자에게 할 말'로만 갈린다.
- 생각을 떠넘길 수 있다: 스스로 점검하기 전에 먼저 부를 수 있다(추론).
- "Get yourself" 는 구어다. 사용자의 "second opinion 좀" 에도 그대로 맞춰질 것이다. 사용자가 요청하는 경로는 살지만 자율이라는 신호가 흐려질 수 있다.

**4. A 의 가장 강한 논거, 그다음 공격**
- A 의 가장 강한 논거: "Get a second opinion" 은 내장 스킬처럼 동사로 시작하는 모양이다. "second opinion" 이라는 말 자체가 '다른 정신'이라는 이 스킬만의 가치를 싣는다. 2단계에서 맥락 있는 장면 자발 발동 1/1 도 A 시절이다.
- 공격 1: 공식 문서는 잘릴 것에 대비해 핵심 용례를 앞에 두라고 한다(audit 24 §1, 출처 A). 사용자가 핵심이라 한 자율(요구 3)이 A 에서는 마지막 절에 있다. A 의 앞 구절은 사용자가 요청할 때 쓰는 말과 똑같다. 그래서 목록에서는 '요청이 오면 쓰는 리뷰 서비스'로 먼저 읽힌다(추론). 제안안은 모양은 그대로 두고 "yourself, on your own initiative" 만 앞으로 올렸다.
- 공격 2: A 의 사용 조건 "whenever you want another view" 는 위에서 말한 욕구 기반이다. 1/1 대 0/4 는 장면이 서로 달라 A 와 B 를 비교한 결과가 아니다. A 를 지지하는 근거로 쓸 수 없다.
- 공격 3: A 의 fresh 는 `/code-review` 와 구분되는 말이 없다. 게다가 트리거 "커밋 전 검토" 가 code-review 의 용도와 정면으로 겹친다. 실측 0/2 에서 모델은 스킬 없이 직접 diff 를 읽었다.
- B 에 대해서도: "A self-check" 는 모델이 도구 없이 원래 하는 일(속으로 다시 생각하기)로 읽힌다. 0/4 에서 모델이 실제로 한 일이 그것이었다(추론). 그래서 나는 B 의 앞 문장이 아니라 "second opinion" 이라는 명사를 지킨다. 이 점에서는 A 쪽 손을 들어 준다.

**5. 싸게 판정할 시험**
sonnet 으로 `claude -p --plugin-dir` 를 쓴다. 후보 A, B, Q 를 장면마다 5회 이상 돌리고, 목록에 code-review 를 같이 둔다.
- (a) §9 와 같은 장면: 모델이 스스로 약점을 짚은 뒤 결론이나 설치 안내를 쓰기 직전. 자발 발동률을 본다. 예상: Q > A ≈ B.
- (b) 음성 장면: 변수 이름 바꾸기, 사실 질문. 오발동을 본다. 예상: Q 가 조금 높다. 5회 중 1회 이하면 받아들일 만하다.
- (c) "커밋 전에 이 diff 검토해 줘" 와 "다 됐다고 말해도 될까?": 어느 스킬을 고르는지 본다. 예상: Q 와 B 에서는 앞 질문에 code-review, 뒤 질문에 fresh 가 나뉜다. A 는 섞이거나 스킬 없이 직접 처리한다.
- (d) nudge 훅을 켠 장면: A 가 훅을 기다리는지 본다. 위의 "review request" 모호성 주장을 판정한다.
비용은 장면마다 약 $0.05 로, 합계 $2 이내로 예상한다(§9 단가로 추정).
