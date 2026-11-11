# Q: 본문 토론 2라운드

**받아들인 것**
- P 의 '판단 하나'를 받는다. 시점을 둘로 늘어놓지 않고, 조건 "only you have checked" 하나에 대상 둘(접근, 완료 주장)을 건다.
- P 의 고유 항목 셋(injection paths 흔적, ledger 예시 값, skip 의 뜻)은 반대 없이 모두 채택한다. 내 고유 항목 둘(relaunch 금지 이유, ledger 를 쓰는 이유)도 넣는다.
- ledger 쪽에 한 가지를 보탠다. `review-ledger.py:13` docstring 의 reviewer 목록(`opus-sub | sonnet-sub | codex | agy | advisor-*`)에는 inherit 가 쓰는 `fork` 와 other-frame 이 쓰는 `ctx-opus|ctx-sonnet` 이 없다. `--reviewer` 는 자유 문자열이라(95행) 오류는 나지 않는다. 그래도 허용값을 본문에 적을 때 스크립트 목록도 같이 맞춰야 한다.
- P 의 "threshold 는 본문에 정의가 없으니 지운다" 도 받는다.

**반박**
- P 문구의 "before you commit to an approach or a claim" 은 "commit" 이 git commit 과 겹친다. 이 스킬을 커밋 시점으로 되돌리려는 것이 이번 토론의 목적인데, 하필 커밋 훅이 울리는 그 단어다. 모델이 "커밋 전에 부르라"로 읽을 위험이 있다(추론). 그래서 "lock in" 으로 바꾼다.
- "a claim" 하나만 두면 중간 주장까지 모두 걸린다. 비싼 opus 경로라 과발동 비용이 크다. "a done claim" 으로 좁힌다.

**fresh 최종 description (477자)**
"Get a second opinion from fresh eyes. Spawns a read-only reviewer in a new context with a short brief; it reads the changes and the user's own words itself and tries to refute your approach or claims. Where a code review hunts defects in a diff, this tests your view against what the user asked. Reach for it before you lock in an approach or a done claim that only you have checked, above all when your own framing may be the problem; no one needs to ask. 접근 확정 전 검토, 완료 전 검증."
- "above all when your own framing may be the problem" 이 inherit 과 가르는 구절이다.
- 트리거 "완료 전 검증, 내 주장 반박" 을 "접근 확정 전 검토, 완료 전 검증" 으로 바꾸자는 것은 제안이다. 사용자가 정한 트리거이므로 사용자가 결정한다.

**inherit 과 fresh 중 무엇을 고르나: 두 곳에 나눠 둔다**
- description 에는 한 구절씩만 둔다. 고르는 일은 목록 단계에서 일어나기 때문이다.
  - inherit 에 "cheap, but it shares your context" 를 넣는다. 471자다. 전문은 "Get a second opinion on your own thinking. Forks you, with this conversation's prompt cache, into a reviewer that steps out of your role and challenges your reasoning, not your diff; cheap, but it shares your context. Reach for it whenever you want another view, and before you act on a conclusion that only you have checked and that would be costly to get wrong. The call is yours: the review serves your next step, so the user does not need to ask. 한 번 더 봐줘, 다른 눈으로 검토."
  - fresh 에는 위의 "above all when your own framing may be the problem" 이 그 역할이다.
- 본문에는 이유를 적는다. 두 본문의 Call 바로 아래에 같은 2줄을 둔다.
  "Which one: inherit-advisor sees why you decided and costs little, so use it when the question is whether your reasoning holds; it may share your blind spots. fresh-advisor starts without your assumptions and reads the artifacts and the user's words, so use it when the framing itself may be wrong or the step is hard to undo. At a hard-to-undo approach, prefer fresh-advisor; do not run both on the same point."

**tier-off: 이유와 확인 방법을 적는다. 지우지 않는다**
- 이유: off 는 사용자가 저장소별로 정한 opt-out 이다(nudge.py:18 "off 등급은 아무것도 하지 않는다"). 줄을 지우면 사용자가 정한 정책이 말없이 바뀐다. 이 사용자의 규약은 사용자 결정을 고치지 말고 제안하라는 것이다. description 과 부딪치는 문제는 이유를 적으면 풀린다.
- 확인 방법은 한 줄로 한다. 비싼 절차를 만들지 않는다.
  "If `~/.claude/harness.env` sets this repo to `off` in `HARNESS_REVIEW_TIERS` (the user opted it out of reviews), call it only when the user asks."
- 이 규칙을 inherit 에도 적용할지(훅은 inherit 를 막지 않는다)는 사용자가 정할 일이다. 결정이 필요한 곳으로 표시해 둔다.
