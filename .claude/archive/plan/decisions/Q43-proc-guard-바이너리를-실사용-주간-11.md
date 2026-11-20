---
format: 1
title: proc-guard 바이너리를 실사용 주간(11-23~) 전에 이 기기에서 켤까?
description: proc-guard 바이너리를 실사용 주간(11-23~) 전에 이 기기에서 켤까? 답 a) 검토 통과 뒤 주간 전에 켬
status: archived; answered a) 검토 통과 뒤 주간 전에 켬
id: Q43
urgency: soon
blocks: proc-guard hooks.json 전환
recommended: a
created: 2026-11-20T05:18:14.191Z
answered: 2026-11-20T06:21:54.750Z
answer: a
---

# Q43. proc-guard 바이너리를 실사용 주간(11-23~) 전에 이 기기에서 켤까?

## 맥락

바이너리는 준비됐어요(aaf316a). python 과 출력 대조 모두 같음, Bash 한 번에 훅 CPU 약 94 ms -> 2.5 ms. 지금 검토자(opus)가 따로 보고 있고, 켜는 건 검토 통과 뒤예요.

켜는 방법
- `plugins/qwreey-proc-guard/hooks/hooks.json` 을 실행 형식(`${CLAUDE_PLUGIN_ROOT}/native/qwreey-proc-guard`, `hook <이름>`)으로 바꾸고 버전을 올림. python 파일은 그대로 둠(열린 세션이 옛 경로를 부를 수 있음)
- 바이너리는 gitignore 라 이 기기에만 있음. 동료 설치본에는 바이너리가 없어서 이 훅들이 조용히 꺼짐(막지 않는 오류). 지금 동료 설치는 없다고 알고 있어요
- 바이너리가 없을 때 막는 훅(heavy-proc-guard)은 진행(오늘 python 이 실패할 때와 같음)

실사용 측정
- 기준선 audit 65 는 python. 주간 전에 켜면 주간 데이터가 새 상태를 보여 주고 전후 비교가 깔끔함

## 선택지

- a) 검토 통과 뒤 주간 전에 켬
  주간 내내 새 상태로 재고 audit 65 와 비교. 문제가 보이면 hooks.json 만 되돌리면 됨
- b) 주간은 python 으로, 끝난 뒤 켬
  주간은 느낀 점 모으기에 집중, 바꾸는 것 하나를 줄임
- c) 지금 바로 켬(검토 전)
  가장 빨리 CPU 를 줄임. 대조는 다 같았음

**권장 a) 검토 통과 뒤 주간 전에 켬**
CPU 가 가장 큰 불만이었고 되돌리기 쉬움. 주간 전에 바꿔야 주간 데이터가 한 상태로 모임

## 답

a
