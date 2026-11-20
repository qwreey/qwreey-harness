---
format: 1
title: qwreey-sessions 의 도구마다·말마다 도는 훅도 주간 전에 바이너리로 켤까?
description: qwreey-sessions 의 도구마다·말마다 도는 훅도 주간 전에 바이너리로 켤까? 답 a) 지금 켬(주간 전)
status: archived; answered a) 지금 켬(주간 전)
id: Q46
urgency: soon
blocks: sessions hooks.json 전환
recommended: a
created: 2026-11-20T08:15:04.284Z
answered: 2026-11-20T08:17:41.449Z
answer: a
---

# Q46. qwreey-sessions 의 도구마다·말마다 도는 훅도 주간 전에 바이너리로 켤까?

## 맥락

검토(opus)는 심각한 것 없음, 낮은 것은 모두 고침(1af251b). python 과 대조: 재생 73, 세션 기록 343 모두 같음, python 과 번갈아 돌아도 상태 파일 같음.

- 켜면: PostToolUse, PreToolUse(Bash|Skill), UserPromptSubmit, records-read 둘이 바이너리. 도구 한 번 약 80 ms -> 약 1~1.5 ms
- 그대로 python: SessionStart, PreCompact, PostCompact, SessionEnd, 요약 작업자
- proc-guard 처럼 python 파일은 남기고, 문제가 보이면 hooks.json 만 되돌림
- 위험: 세션 기록은 proc-guard 보다 상태가 많음(알림 커서, 작업자 띄우기). 섞여 도는 것은 시험으로 확인함

## 선택지

- a) 지금 켬(주간 전)
  주간 데이터가 한 상태로 모이고 CPU 가 가장 크게 줌
- b) 주간은 proc-guard 만, sessions 는 뒤에
  바꾸는 것을 하나로 줄여 문제가 생기면 원인을 좋히기 쉬움

**권장 a) 지금 켬(주간 전)**
도구마다 드는 훅 CPU 의 가장 큰 몫이고, 대조와 섞여 돌기 시험이 모두 통과했으며 되돌리기가 hooks.json 하나라서

## 답

a
