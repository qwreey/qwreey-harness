# 본문 토론 판결 초안 (중재자: 메인, 2026-11-11) — 사용자 확인 대기

## 양쪽 합의 (그대로 적용)
1. fresh-advisor 를 접근 확정 전으로 넓힌다. done 은 "말한 것 대 한 것, 사용자 요구 대조"로 좁히고, diff 결함은 `/code-review` 에 넘긴다.
   - reviewer.md: done 에서 "missing tests" 를 뺀다. "Run things" 는 주장을 확인하는 데 필요할 때만 한다.
   - 스킬 본문의 "threshold" 를 지운다.
   - 스킬은 쪼개지 않는다.
2. brief 와 템플릿을 종류별로 쓴다. plan 은 "the approach I am about to lock in, and the alternatives I dropped", stuck 은 "my current hypothesis". `:33` 에는 "for plan, state the approach itself" 를 덧붙인다.
3. inherit 호출 예시에서 `options: reqs` 를 뺀다. 인자 절에만 둔다.
4. inherit 의 호출 시점 문장을 "Call it in the same turn, at the decision point, before the step it guards; the fork reuses the prompt cache only while it is warm." 으로 바꾼다.
5. tier-off 줄은 지우지 않는다. 이유와 확인 방법을 적는다(P 문구). 사용자가 정한 opt-out 이고, inherit 에는 본문 말고 다른 장치가 없다.
6. fork 템플릿의 "injection paths" 를 "(other callers, other users and sessions)" 로 바꾼다.
7. ledger:
   - 예시를 자리표시자로 바꾼다.
   - `--reviewer` 허용값을 적고, 스크립트 docstring 목록도 맞춘다(fork, ctx-opus, ctx-sonnet 추가).
   - 기록하는 이유를 한 줄 넣는다.
8. low tier 의 skip 은 "do not call it on your own" 으로 쓴다.
9. relaunch 금지에 이유(연쇄 비용)를 붙이고, 반쪽 결과 처리("review incomplete: <what was not seen>")를 둔다.
10. 정반대 지시에 이유를 붙인다. fresh 에는 "the reviewer cannot see your doubts otherwise" 를 보탠다.
11. 불필요한 문장을 지운다: fresh `:16` 의 사실 서술은 "always pass `model`" 로 바꾸고, Stats 줄은 rationale 로 옮기고, inherit `:31` 의 되풀이를 지운다.

## 남은 차이와 판단
| 쟁점 | P | Q | 판단 |
|---|---|---|---|
| fresh 사용 조건 | "before you lock in an approach or tell the user work is done, when only you have checked that view" | "before you lock in an approach or a done claim that only you have checked, above all when your own framing may be the problem" | **P**. 문법이 분명하고, "tell the user work is done" 이 구체적이다. Q 의 "framing" 구절은 본문의 고르는 규칙이 맡는다 |
| fresh 성질 구절 | "without your assumptions" | (조건 끝의 framing 구절) | **P** |
| inherit 성질 구절 | "it sees your reasoning but may share your blind spots" | "cheap, but it shares your context" | **P**. 장점과 위험을 함께 말한다. 싸다는 것은 prompt cache 로 이미 드러난다 |
| 고르는 규칙(본문) | 되돌림 비용 기준 | 질문 기준: "추론이 버티나"는 inherit, "틀 자체가 틀렸을 수 있다"는 fresh. 되돌리기 어려우면 fresh, 같은 지점에 둘 다 쓰지 않는다 | **Q 를 바탕으로 P 를 덧붙인다**. 질문으로 고르고, 되돌리기 어려우면 fresh 를 우선한다. 같은 지점에 둘 다 부르지 않는다 |

## 최종 description 안
- inherit-advisor: "Get a second opinion on your own thinking. Forks you, with this conversation's prompt cache, into a reviewer that steps out of your role and challenges your reasoning, not your diff; it sees your reasoning but may share your blind spots. Reach for it whenever you want another view, and before you act on a conclusion that only you have checked and that would be costly to get wrong. The call is yours: the review serves your next step, so the user does not need to ask. 한 번 더 봐줘, 다른 눈으로 검토."
- fresh-advisor: "Get a second opinion from fresh eyes. Spawns a read-only reviewer in a new context with a short brief; it reads the user's own words and the files itself, without your assumptions, and tries to refute your view. Where a code review hunts defects in a diff, this tests your approach or claims against what the user asked. Reach for it before you lock in an approach or tell the user work is done, when only you have checked that view; no one needs to ask. <트리거: 사용자 결정>"

## 본문의 고르는 규칙 (두 본문의 Call 아래에 같은 문장)
"Which one: ask what you doubt. If it is whether your reasoning holds, inherit-advisor sees why you decided and costs little, but may share your blind spots. If the framing itself may be wrong, or the step is hard to undo, fresh-advisor starts without your assumptions and reads the files and the user's words. Do not run both on the same point."

## 사용자 결정
- fresh 트리거: 지금은 "완료 전 검증, 내 주장 반박"(사용자 확정). 양쪽 모두 "접근 확정 전 검토" 를 넣자고 제안했다. 제안: "접근 확정 전 검토, 완료 전 검증".
- 실측: 판정 실측(c5e60f5 대 d6dfb99)이 진행 중이다. 이 판결안을 적용한 뒤 P 가 낸 고르기 실험(되돌리기 어려운 결정 장면과 중간 결론 장면, 각 N=5)을 더 돌릴지.
