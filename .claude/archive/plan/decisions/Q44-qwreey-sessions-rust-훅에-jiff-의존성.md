---
format: 1
title: qwreey-sessions Rust 훅에 jiff 의존성(오늘 날짜, 시간대)을 둘까?
description: qwreey-sessions Rust 훅에 jiff 의존성(오늘 날짜, 시간대)을 둘까? 답 a) jiff 유지
status: archived; answered a) jiff 유지
id: Q44
urgency: soon
blocks: qwreey-sessions hooks.json 전환
recommended: a
created: 2026-11-20T07:10:36.585Z
answered: 2026-11-20T07:15:27.173Z
answer: a
---

# Q44. qwreey-sessions Rust 훅에 jiff 의존성(오늘 날짜, 시간대)을 둘까?

## 맥락

세션 기록 훅은 "쌓인 기록이 며칠 됐나"와 오류 기록 시각에 이 기기 시간대의 오늘 날짜가 필요해요. Rust 표준 라이브러리에는 시간대가 없어요.

- 에이전트가 jiff 를 더함(널리 쓰는 날짜·시간대 crate). 바이너리 851 KB -> 1.21 MB, release 링크 +1.5 초. python 과 TZ 없음, IANA 이름, POSIX 규칙, 잘못된 이름, 파일 경로를 비교해 같음
- 대안: 직접 짠 TZif 읽기(DST 규칙 꼬리 포함)를 harness-hook 에 둠. 크기는 작지만 유지할 코드가 늘고 틀리기 쉬운 영역
- 대안: 날짜를 UTC 로만 셈. 코드가 가장 작지만 자정 근처에 python 과 하루가 어긋날 수 있음(바이트 대조가 깨짐)

## 선택지

- a) jiff 유지
  검증된 crate, python 과 같음. 크기 +360 KB 는 바이너리 하나에만
- b) 직접 짠 TZif 읽기
  작지만 시간대 코드를 우리가 유지
- c) UTC 로만
  가장 단순, 자정 근처 하루 어긋남

**권장 a) jiff 유지**
시간대는 직접 짜면 틀리기 쉬운 대표 영역이고, 크기 증가는 sessions 바이너리 하나에만 들어서 비용이 작음

## 답

a
