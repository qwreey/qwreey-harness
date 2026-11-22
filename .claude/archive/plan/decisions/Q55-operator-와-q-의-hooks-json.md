---
format: 1
title: operator 와 q 의 hooks.json 도 바이너리로 켤까?
description: operator 와 q 의 hooks.json 도 바이너리로 켤까? 답 a) 둘 다 지금 켬다
status: archived; answered a) 둘 다 지금 켬다
id: Q55
urgency: soon
blocks: operator·q hooks.json 전환
recommended: a
created: 2026-11-22T04:53:46.089Z
answered: 2026-11-22T04:57:14.412Z
answer: a
---

# Q55. operator 와 q 의 hooks.json 도 바이너리로 켤까?

## 맥락

둘 다 main 에 합쳤고(99e61a8), 검토 반영까지 끝났다(1a1ae3f).

- **옮긴 것**: operator 의 delegate-nudge, subagent-bg-tasks. q 의 subagent-slots(모든 이벤트), stale-work, mise-hint, ambient(UserPromptSubmit).
- **대조**: q 재생 120·실제 입력 214, operator 57·197, 모두 같음. 여덟 crate 전부 다시 돌려 모두 같음. 플러그인 시험 python 판·바이너리 판 통과.
- **검토**: q 에서 Rust 가 python 보다 더 말하던 자리 하나(아주 깊은 transcript 줄)를 고쳐 재현 스크립트로 확인. python 과 Rust 가 같은 ledger 를 번갈아 써도 결과가 같음을 리뷰어가 확인.
- **속도**: 훅 하나 12~27 ms -> 1~1.6 ms. 도구마다 도는 delegate-nudge(약 25 ms)와 subagent-slots(약 15 ms)가 빠진다.
- subagent-slots 는 자리 비움 중에 거절하는 훅이다. 바이너리가 없으면 거절하지 않는다(다른 막는 훅과 같다).
- 켜면 도구마다 도는 python 훅이 사실상 없어진다(남는 것은 세션 시작, compact 쪽).

## 선택지

- a) 둘 다 지금 켬다
  대조 0, 검토 반영 끝. 앞의 플러그인들과 같은 기준
- b) operator 만 켜고 q(거절하는 subagent-slots)는 나중에
  거절하는 훅을 한 번 더 지켜본 뒤에
- c) 아직 켜지 않는다
  실사용 주간을 지금 상태로

**권장 a) 둘 다 지금 켬다**
같은 기준을 넘었고, 켜야 도구마다 도는 python 비용이 끝난다

## 답

a
