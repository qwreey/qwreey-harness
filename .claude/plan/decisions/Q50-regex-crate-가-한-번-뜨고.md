---
format: 1
title: regex crate 가 한 번 뜨고 죽는 훅에서는 오히려 조금 느림. 그래도 고정 패턴은 전부 regex crate 로 갈까?
description: regex crate 가 한 번 뜨고 죽는 훅에서는 오히려 조금 느림. 그래도 고정 패턴은 전부 regex crate 로 갈까? 권장 a) 전부 regex crate, lazy 와 단순화로 비용을 줄임
status: active
id: Q50
urgency: soon
blocks: 정규식 옮기기 마무리, advisor 합치기
recommended: a
created: 2026-11-20T10:15:33.452Z
---

# Q50. regex crate 가 한 번 뜨고 죽는 훅에서는 오히려 조금 느림. 그래도 고정 패턴은 전부 regex crate 로 갈까?

## 맥락

advisor, reply-language 이식(Q48 a 적용)에서 잰 것: regex crate 는 패턴을 만드는 비용이 프로세스마다 듦.
- `[^\n]{1,80}` 같은 큰 글자 집합의 반복 약 840 µs, `(?i)` 와 유니코드 `\b` 약 320~375 µs, 맨 `\w` 약 115 µs, 단순 패턴 10~50 µs
- 그래서 호출 한 번이 py::re 판보다 0.1~1.6 ms 느려짐(예: reply-language Stop 0.99 -> 2.11 ms, advisor SubagentStop 1.54 -> 3.01 ms). 그래도 python(33~41 ms)보다 11~34배 빠름
- 바이너리는 약 2배(advisor 1.3 -> 2.0 MB, reply-language 0.7 -> 1.4 MB). `perf` 기능은 CPU 이득 없이 0.5 MB 더함
- 큰 파일(conventions, 주석 줄 수백)에서는 반대로 regex crate 가 크게 빠를 것으로 봄(19개 패턴 33 ms -> 0.2 ms, 다만 패턴 만드는 비용은 그 잴 때 빠짐)

지금 다른 에이전트가 proc-guard, sessions, conventions 를 옮기는 중이고, 필요한 패턴만 그때그때 만들기(lazy)와 패턴 단순화를 하고 훅마다 전후를 재도록 했어요.

advisor 쪽 다른 것: regex-syntax 를 직접 의존성으로 씀(regex 가 이미 끌고 오는 같은 판, 글자 분류 함수 하나), SHA-1 을 손으로 짰음(Q49 a 전이라 몰랐음, 합칠 때 sha1 crate 로 바꿀게요).

## 선택지

- a) 전부 regex crate, lazy 와 단순화로 비용을 줄임
  py::re 를 나중에 지우기 쉬움. 더 드는 것은 호출당 1 ms 안팎, python 대비 미미
- b) 비싼 패턴(0.3 ms 넘는 것)만 예외로 py::re
  CPU 를 조금 더 아낌. 대신 py::re 를 지울 때 그 패턴을 다시 보아야 함
- c) 작은 입력 훅은 py::re, 큰 파일 보는 훅만 regex crate
  각 훅에 더 싼 쪽. 엔진 둘을 오래 둠

**권장 a) 전부 regex crate, lazy 와 단순화로 비용을 줄임**
사용자가 Q48 에서 본 이유(정본이 물러나면 py::re 는 떨어져 나감)가 그대로이고, 차이는 호출당 1 ms 안팎이라 python 대비 이득을 거의 깎지 않음
