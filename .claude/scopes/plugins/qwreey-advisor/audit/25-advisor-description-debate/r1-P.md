# P 1라운드: "Get a second opinion …" 틀(A안 개선)

**1. 제안**
- inherit-advisor (394자): "Get a second opinion on your own thinking. Forks you, with this conversation's prompt cache, into a reviewer that steps out of your role and challenges your reasoning, not your diff. Reach for it whenever you want another view on your reasoning or a check on what you might have missed. The call is yours: the review serves your next step, so the user does not need to ask. 한 번 더 봐줘, 다른 눈으로 검토."
- fresh-advisor (488자): "Get a second opinion from fresh eyes. Spawns a read-only reviewer in a new context with a short brief; it reads the changes and the user's own words itself and tries to refute your claims. Where a code review hunts defects in a diff, this tests your claims against what the user asked. Reach for it whenever you want your claims tested by someone who does not share your assumptions. The call is yours: the review serves your next step, so the user does not need to ask. 커밋 전 검토, 완료 전 검증."

**2. 사용 조건 문장을 구절별로**
- "Reach for it": 에이전트가 주어인 명령형이고 조금 pushy 하다(skill-creator). "가까이 둔 도구를 집는다"는 뜻이라 부르는 문턱이 낮다. 사용자가 버린 "Call it right before …" 처럼 시점을 늘어놓지 않는다.
- "whenever you want": 발동 기준이 에이전트 자신의 상태다(요구 4). 장면 목록도 사용자 요청도 기준이 아니다. "whenever" 가 넓게 열어 준다(원칙 9 와 pushy).
- "another view on your reasoning / a check on what you might have missed": 원칙 11 의 두 필요를 그대로 옮겼다. "might have" 는 틀렸다고 확신할 때뿐 아니라 확신이 없을 때도 부르게 한다.
- "The call is yours:": A 의 부정문 "no need to wait for a review request" 를 긍정문으로 바꿨다. A 의 원문은 세 군데가 모호하다(추론). (a) 누구의 요청인지 모른다. 사용자일 수도, 훅 nudge 일 수도 있다. (b) "wait" 는 요청이 언젠가 온다는 전제를 깐다. (c) "review request" 가 훅 알림과 겹쳐 읽히면 훅을 기다리게 될 수 있다. "call" 은 결정과 도구 호출 두 뜻으로 함께 읽힌다.
- "the review serves your next step": 이유를 밝힌다(skill-creator "explain the why"). 결과가 사용자나 PR 에게 가는 산출물이 아니라 내 다음 행동의 입력이라는 점도 말해 준다. `/code-review` 와 갈라지는 두 번째 지점이다.
- "so the user does not need to ask": "should not" 이 아니라 "does not need" 다. 그래서 사용자가 요청하는 경로(한국어 트리거, 본문의 "The user asked for it")는 막지 않으면서 사용자 의사와 무관함을 분명히 한다.
- `/code-review` 와의 구분: inherit 는 "reasoning, not your diff", fresh 는 "Where a code review hunts defects in a diff …" 다. 대상(추론·주장 대 diff 결함)과 기준(사용자 요구 대 정확성)으로 가른다.

**3. 내 안의 예상 실패**
- description 으로 "원함"을 만들 수는 없다. 실측 0/4 에서 모델은 혼자 약점을 짚고 끝냈다. 이 문구도 그 장면에서는 0 일 수 있다. 사용 빈도는 CLAUDE.md 와 훅의 몫이 크다.
- 과발동: 전역 목록에 "whenever" 와 "the user does not need to ask" 가 함께 있으면 사소한 턴에도 fork 가 뜰 수 있다. description 에서 비용을 알리는 단서는 "prompt cache" 하나뿐이고, 억제는 본문("once per turning point", tier off)에 기댄다.
- 두 스킬의 마지막 문장이 똑같아서 그 문장으로는 둘을 가를 수 없다. 구분은 앞 문장이 맡는다(머리 쪽이 더 크게 읽힌다는 것은 추론).
- "second opinion" 이라는 관용구는 사람이 남에게 구하는 장면을 떠올리게 해서, 사용자가 시키는 일로 읽힐 수 있다. 끝 문장이 이를 상쇄하리라 기대한다.
- "커밋 전 검토" 트리거는 `/code-review` 영역과 겹친다. 사용자가 정한 것이므로 제안만 한다.

**4. B 의 가장 강한 형태, 그리고 반박**
- 가장 강한 형태: B 는 "self-check … on your own initiative, for your own use" 로 주도권과 용도를 첫 토큰부터 박는다. 목록을 훑을 때 자율성이 가장 먼저 보이므로 요구 3·4 를 가장 직접 담는다.
- 반박:
  (a) 사용자가 앞 문장은 A 모양이라고 명시했다(요구 1).
  (b) "self-check" 는 모델이 이미 인라인으로 하는 행동의 이름이다. 0/4 장면에서 모델은 바로 그 자기 점검을 혼자 하고 끝냈다. 대체 행동을 이름으로 붙이면 대체를 허락하는 셈이다(추론). "second opinion" 은 혼자서는 만들 수 없는 다른 시점을 가리키고, 그것이 이 스킬의 가치다.
  (c) 공식 스킬 목록은 하는 일을 동사로 시작한다(code-review "Review the current diff…", simplify "Review the changed code…"). B 는 동기 명사구로 시작하고 하는 일이 뒤로 밀린다.
  (d) "findings feed your next step, not a report" 는 결과 처리라서 본문에 갈 내용이다(원칙 10). 괄호 목록은 나열이다(원칙 9).
  (e) "whether or not the user asked" 는 조건을 다시 사용자 기준으로 정의한다. 요구 4 가 빼려던 축이다.
  (f) 두 description 의 앞 62자가 같다. 목록에서 나란히 놓인 두 스킬의 머리가 같으면 서로 구분하기 어려워진다(추론). A 틀은 머리가 다르다("on your own thinking" 대 "from fresh eyes").

**5. 싸게 판가름할 실험**
- 장면: 맥락 있는 합성 대화. 메인이 "끝, apply 안내 쓰겠다" 직전이고, 메인 자신의 마지막 응답에 적히지 않은 약점 하나를 심는다. 0/4 장면은 메인이 약점을 이미 적어 둬서 판별력이 없었다.
- 방법: description 만 A′, B, 스킬 없음으로 바꿔 sonnet `-p --resume --fork-session --plugin-dir` 로 각 5회 돌린다.
- 잴 것: (1) 스스로 부른 비율. (2) 부르지 않고 "self-check:" 류로 인라인 자기 점검을 하고 끝낸 비율. B 쪽이 더 높을 것으로 예측한다.
- 음성·경계 질의 세 가지:
  - "이 diff 커밋 전에 버그 봐줘": `/code-review` 로 가야 맞다. 두 안의 오발동을 잰다.
  - "한 번 더 봐줘": 두 안 모두 발동해야 한다. A′ 의 "does not need" 가 사용자 요청 경로를 막지 않는지 확인한다.
  - 무관 질의 1개: 과발동을 잰다.
- 예상 비용: 장면당 약 $0.05~0.1, 합계 $2 이내(§9 단가로 추정).
