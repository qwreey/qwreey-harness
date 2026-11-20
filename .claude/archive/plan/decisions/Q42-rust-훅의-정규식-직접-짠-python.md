---
format: 1
title: "Rust 훅의 정규식: 직접 짠 python re 호환 엔진을 둘까, fancy-regex 를 쓸까?"
description: "Rust 훅의 정규식: 직접 짠 python re 호환 엔진을 둘까, fancy-regex 를 쓸까? 답 c) 지금은 a, conventions 때 다시 재기"
status: archived; answered c) 지금은 a, conventions 때 다시 재기
id: Q42
urgency: later
blocks: qwreey-conventions 이식(정규식이 가장 많음)
recommended: c
created: 2026-11-20T05:17:39.863Z
answered: 2026-11-20T06:21:54.750Z
answer: c
---

# Q42. Rust 훅의 정규식: 직접 짠 python re 호환 엔진을 둘까, fancy-regex 를 쓸까?

## 맥락

proc-guard 를 옮기며 에이전트가 `harness-hook` 에 python `re` 의 부분 구현을 넣었어요(`py::re` 약 1.65k 줄, 생성된 유니코드 표 0.9k 줄). 훅의 고정 정규식이 lookahead, lookbehind 를 써서 표준 `regex` crate 로는 안 돼요.

이미 커밋(aaf316a), 출력 대조 모두 같음, `cargo test` 마다 python re 와 약 6,800 사례 비교.

잰 것(이 기기, release, strip)
- 지금(직접 짠 엔진, 패턴 전부): 바이너리 842 KB, heavy-proc-guard 0.60 ms CPU
- fancy-regex 패턴 하나만 든 빈 바이너리: 1.93 MB, 0.98 ms CPU
- python: 21~31 ms

차이
- 직접 짠 엔진: python 과 뜻이 같아 바이트 대조가 그대로 맞음. 대신 유지할 코드가 늘고, 안 옮긴 문법(조건 그룹, `(?i:...)` 등)은 pgrep 패턴에서 부분 문자열 검사로 물러남
- fancy-regex: 널리 쓰는 crate, 우리 코드가 줄어듦. 대신 크기 2배 넘게, 띄울 때 CPU 가 더 들고, `\w` 같은 뜻이 python 과 조금 달라 대조에서 예외 목록이 생김
- 나중에 qwreey-conventions(렉서, 큰 파일) 를 옮길 때 성능을 다시 재야 함

## 선택지

- a) 직접 짠 엔진 유지
  더 작고 빠르고 python 과 뜻이 같음. 매 cargo test 가 python re 와 비교해 지켜 줌
- b) fancy-regex 로 바꿈
  우리가 유지할 코드가 줄고 검증된 crate. 크기와 CPU 가 늘고 대조 예외가 생김
- c) 지금은 a, conventions 때 다시 재기
  규약 검사기가 정규식을 가장 많이 쓰니 그때 두 안을 실제 파일로 재서 정함

**권장 c) 지금은 a, conventions 때 다시 재기**
CPU 를 줄이려고 옮기는 것인데 지금 수치는 직접 짠 쪽이 낫고, 진짜 시험대는 conventions 라 그때 재고 정하는 게 버릴 일이 적음

## 답

c
