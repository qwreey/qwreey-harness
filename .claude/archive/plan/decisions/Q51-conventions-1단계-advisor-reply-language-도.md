---
format: 1
title: conventions(1단계), advisor, reply-language 도 주간 전에 바이너리로 켤까?
description: conventions(1단계), advisor, reply-language 도 주간 전에 바이너리로 켤까? 답 a) 셋 다 지금 켬
status: archived; answered a) 셋 다 지금 켬
id: Q51
urgency: soon
blocks: 세 플러그인 hooks.json 전환
recommended: a
created: 2026-11-20T12:05:15.971Z
answered: 2026-11-22T02:17:59.544Z
answer: a
---

# Q51. conventions(1단계), advisor, reply-language 도 주간 전에 바이너리로 켤까?

## 맥락

세 플러그인 모두 이식, 검토(opus), 검토 반영이 끝남(96ac750). python 과 대조 모두 같음: conventions 재생 72·세션 기록 255·형제 저장소 실제 파일 4303 x 3, advisor 126·334, reply-language 22·실제 답 글 810.

켜면 훅 CPU(호출 한 번)
- conventions: Edit 한 번 네 훅 약 160 -> 20 ms 안팎, 큰 파일 conventions-check 83 -> 10.6 ms
- advisor: 15~42 -> 1~7 ms(Bash, PostToolBatch, Stop 등)
- reply-language: 약 33 -> 1~3 ms(PostToolBatch, Stop)

막는 훅이 둘: advisor 의 reviewer 쓰기 금지, reply-language 의 Stop 막기. 검토에서 무작위 명령 22,000개, 답 1,500개로 판단이 같음을 확인.
그대로 python: conventions 의 rules_inject, bash-bypass-reminder, bash_writes, compact_epoch(2단계), advisor 의 ambient SessionStart·PreCompact.
되돌리기: 그 플러그인 hooks.json 만.

## 선택지

- a) 셋 다 지금 켬
  주간 데이터가 한 상태로 모이고, 남은 훅 CPU 의 큰 몸을 줄임
- b) conventions 만 지금, advisor·reply-language 는 뒤에
  막는 훅을 가진 두 플러그인은 주간 뒤에
- c) 주간은 지금 상태로
  바꾸는 것을 줄여 원인을 좁히기 쉬움

**권장 a) 셋 다 지금 켬**
proc-guard, sessions 와 같은 기준(대조 0, 검토 반영)을 넘었고, 되돌리기가 hooks.json 하나라서

## 답

a
