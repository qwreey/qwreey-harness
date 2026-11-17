---
format: 1
title: compact 뒤 사용자 원문·식별자 목록 복원을 실측해 볼까?
description: compact 뒤 사용자 원문·식별자 목록 복원을 실측해 볼까? 답 a) 실측부터
status: archived; answered a) 실측부터
id: Q3
recommended: a
created: 2026-11-16T06:57:34.647Z
answered: 2026-11-16T07:58:56.962Z
answer: a
---

# Q3. compact 뒤 사용자 원문·식별자 목록 복원을 실측해 볼까?

## 맥락

**출처:** hermes-agent 자체 압축기 실측(audit 59): compact 구간의 사용자 발화 원문 + 정규식으로 뽑은 식별자 목록(파일·커밋·오류) + 복구 경로를 붙이니 회상 +22.5pt(68.3 대 45.8), 세부 사실 질문 23 -> 60.

**우리 쪽:** qwreey-sessions 의 compact 뒤 주입은 기록 경로와 pending 만 준다. Claude Code compaction 위에 덧붙여도 효과가 있는지는 모른다.

**실측안:** 긴 transcript 에서 compact 를 일으키고, 그 구간 질문에 답하게 해 끔/켬 비교(hermes 방식). 비용 대략 USD 5-10.

## 선택지

- a) 실측부터
  효과가 확인되면 qwreey-sessions 에 넣는다
- b) 나중에
  패널과 다른 일이 먼저

**권장 a) 실측부터**
외부 근거가 이번 조사에서 가장 강했고, 자고 오셨을 때나 긴 세션의 맥락 손실과 바로 이어진다.

## 답

a
