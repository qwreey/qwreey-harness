# 판결 초안 (중재자: 메인, 2026-11-11) — 사용자 결정 대기

## 수렴한 것 (양쪽 최종안에 공통)
- "second opinion" 명사 유지. "self-check" 는 모델이 도구 없이 원래 하는 일의 이름이라 대체를 허락한다(양쪽).
- 하는 일을 동사로 시작한다(공식 스킬과 같은 모양).
- `/code-review` 와 대상을 가른다: inherit "challenges your reasoning, not your diff", fresh "Where a code review hunts defects in a diff, this tests your claims against what the user asked".
- 상태 조건: "only you have checked/verified". 맹점은 욕구를 만들지 않는다(Q 가 제기하고 P 가 받아들임).
- 무게 조건: "that would be costly to get wrong". 상태 조건의 과발동을 나열 없이 막는다(P 가 제기하고 Q 가 받아들임).
- 자율: "The call is yours … the user does not need to ask". "does not need" 는 사용자 요청 경로를 막지 않는다.
- 결과 처리 문구, 괄호 목록은 description 에서 뺀다.

## 남은 차이와 판단
| 쟁점 | P | Q | 판단 |
|---|---|---|---|
| 첫 구절 | "Get yourself a second opinion" | "Get a second opinion" | **Q**. 사용자가 고른 모양이고, "yourself" 의 자율 신호는 끝의 "The call is yours" 가 이미 맡는다. Q 의 "구어라서 사용자 요청과 겹쳐 읽힌다" 는 우려도 맞다 |
| inherit 시점 동사 | "act on a conclusion" | "act on or report a judgment" | **P**. "report" 는 보류 보고 같은 사소한 답까지 넓힌다. 사용자에게 결론을 말하는 것도 결론에 따라 행동하는 일에 들어간다 |
| inherit 욕구 조건 | "whenever you want another view, and before …" | 없음(상태만) | **P**. 욕구와 상태를 둘 다 둔다. 사용자가 처음 말한 "다른 의견을 듣고 싶을 때" 를 살린다 |
| fresh 자율 | "no one needs to ask" | "The call is yours, so the user does not need to ask" | **P**. 훅 nudge 를 기다리지 않는다는 뜻까지 담고 더 짧다 |
| fresh 시점 | "before you tell the user that something only you have verified is done or true" | "… your work is done or correct when only you have verified it" | **P**(Q 의 1라운드 문장). 작업물뿐 아니라 사실 주장도 덮는다 |

## 종합안
- inherit-advisor: "Get a second opinion on your own thinking. Forks you, with this conversation's prompt cache, into a reviewer that steps out of your role and challenges your reasoning, not your diff. Reach for it whenever you want another view, and before you act on a conclusion that only you have checked and that would be costly to get wrong. The call is yours: the review serves your next step, so the user does not need to ask. 한 번 더 봐줘, 다른 눈으로 검토."
- fresh-advisor: "Get a second opinion from fresh eyes. Spawns a read-only reviewer in a new context with a short brief; it reads the changes and the user's own words itself and tries to refute your claims. Where a code review hunts defects in a diff, this tests your claims against what the user asked. Reach for it before you tell the user that something only you have verified is done or true; no one needs to ask. 커밋 전 검토, 완료 전 검증."

## 사용자에게 올릴 것
- 한국어 트리거 "커밋 전 검토" 는 `/code-review` 의 용도와 겹친다(양쪽 모두 지적). 사용자가 정한 것이라 바꾸지 않고 제안만 한다: "완료 전 검증, 내 주장 반박".
- 판정 시험(종합안 대 현재 d6dfb99, 공동 시험 설계, N=5, 약 $2.5)을 돌릴지.
- "항상 3인칭" 권고: 양쪽 다 명령형("you")이다. 내장 스킬과 같은 모양이라 쟁점에서 뺐다.
