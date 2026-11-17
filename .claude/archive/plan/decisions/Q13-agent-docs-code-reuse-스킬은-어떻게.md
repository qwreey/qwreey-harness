---
format: 1
title: agent-docs·code-reuse 스킬은 어떻게 둘까?
description: agent-docs·code-reuse 스킬은 어떻게 둘까? 답 a) 둘 다 제안대로
status: archived; answered a) 둘 다 제안대로
id: Q13
urgency: later
blocks: 스킬 정리(D6 원칙을 나머지에)
recommended: a
created: 2026-11-16T10:36:21.809Z
answered: 2026-11-17T00:17:20.192Z
answer: a
---

# Q13. agent-docs·code-reuse 스킬은 어떻게 둘까?

## 맥락

**원칙(D6):** 규약 = rule + 훅, 절차 = 사용자 명령이나 과제 이름의 스킬, 사람용 참고 = docs.

**agent-docs 스킬:** 이번 작업 뒤 지킬 것은 모두 rule 이나 훅에 있다. 남는 건 참고(무엇을 남기고 옮기나 예시, 진입 문서와 참고 문서 표, 원장 메모)와 정리 절차 하나.
- 제안: comments 처럼. 참고는 `docs/agent-docs.md`, 정리는 사용자 명령(`/qwreey-conventions:docs-cleanup` 또는 comments-cleanup 에 합침), rule 의 포인터 줄은 뺌.

**code-reuse 스킬:** 모델이 그 순간에 쓰는 실제 절차가 있다(region 옵션과 sync, 사본 비교 시험 쓰는 법, 라이브러리 대 직접 구현 측정 순서, 중복 처리 순서). 실제로 불린 2번도 이 스킬이었다.
- 제안: 모델이 부르는 스킬로 남기되 과제 이름에 맞게 description 을 좁힘(패키지·저장소 사이 정의 복사, region 표시, 라이브러리 고르기). 설정 키와 정책·불변 표는 docs 로.

## 선택지

- a) 둘 다 제안대로
  agent-docs 는 docs+명령, code-reuse 는 절차 스킬로 좁힘
- b) agent-docs 만
- c) 그대로 둠

**권장 a) 둘 다 제안대로**
D6 와 같은 기준을 적용한 결과다. 지킬 것은 이미 rule·훅으로 옮겨져서 스킬은 지킴 경로가 아니다.

## 답

a
