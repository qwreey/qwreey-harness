---
format: 1
title: agent-docs rule 에 "손댄 줄만 고친다" 한 줄을 더할까?
description: agent-docs rule 에 "손댄 줄만 고친다" 한 줄을 더할까? 답 a) 더함
status: archived; answered a) 더함
id: Q15
urgency: later
blocks: agent-docs rule 마무리
recommended: a
created: 2026-11-17T00:30:55.935Z
answered: 2026-11-17T00:32:02.248Z
answer: a
---

# Q15. agent-docs rule 에 "손댄 줄만 고친다" 한 줄을 더할까?

## 맥락

**배경:** D13 으로 agent-docs 스킬을 없앴다(8b3c6b6, qwreey-conventions 0.12.0). 스킬에 있던 "추가한 줄만 고치고, 파일 전체 정리는 시키지 않으면 하지 않는다" 가 rule 에 없다. comments rule 에는 같은 뜻의 줄이 있다. 지금은 알림 문구의 "Fix those lines" 가 암시만 한다.

**더할 문구(comments rule 과 같은 꼴):**
- `Fix only lines you add or touch; old problems in a file are reported to the user at turn end, not cleaned up unprompted.`

**없으면:** 모델이 문서 하나를 고치다가 같은 파일의 옛 이력 줄까지 손댈 수 있다(사용자가 부탁하지 않은 정리). 정리는 이제 `/qwreey-conventions:docs-cleanup` 명령이 맡는다.

**크기:** 문서용 주입이라 코드 파일 상한(8,752/9,000)과는 별개.

## 선택지

- a) 더함
  comments 와 같은 원칙, 쓸데없는 정리 방지
- b) 안 더함
  알림 문구로 충분

**권장 a) 더함**
스킬이 없어진 지금 이 원칙이 남는 곳은 rule 뿐이고, comments 와 똑같이 맞춰 두는 편이 헷갈리지 않는다.

## 답

a
