---
format: 1
title: regex crate 는 매번 뜨는 훅에서 패턴 만드는 비용이 듦. 고정 패턴은 전부 regex crate 로, perf-dfa 는 어디에?
description: regex crate 는 매번 뜨는 훅에서 패턴 만드는 비용이 듦. 고정 패턴은 전부 regex crate 로, perf-dfa 는 어디에? 답 a) 고정 패턴 전부 regex crate, perf-dfa 는 전부 켬(워크스페이스 한 줄)
status: archived; answered a) 고정 패턴 전부 regex crate, perf-dfa 는 전부 켬(워크스페이스 한 줄)
id: Q50
urgency: soon
blocks: 정규식 옮기기 마무리, advisor 합치기
recommended: a
created: 2026-11-20T10:15:33.452Z
answered: 2026-11-22T02:17:59.544Z
answer: a
---

# Q50. regex crate 는 매번 뜨는 훅에서 패턴 만드는 비용이 듦. 고정 패턴은 전부 regex crate 로, perf-dfa 는 어디에?

## 맥락

잰 것(다섯 crate 모두 옮긴 뒤, 96ac750)
- 패턴을 만드는 비용이 프로세스마다 듦: 큰 글자 집합 반복 약 840 µs, `(?i)` 와 유니코드 `\b` 약 320 µs, 단순 패턴 10~50 µs. 필요한 패턴만 그때 만들고(lazy) 다듬어서, 0.3 ms 넘게 드는 패턴은 없음
- 작은 입력 훅: py::re 판보다 0~0.3 ms 느림(structure-reminder 0.9 -> 1.2 ms 등). python 은 15~40 ms
- 큰 파일: conventions-check 3.3k 줄 41.5 -> 10.6 ms(python 83 ms)
- 바이너리 약 1.5~2.4 MB(전에는 0.8~1.5 MB)

perf-dfa: regex 의 빠른 DFA 기능
- conventions 에만 켬: 없으면 큰 파일 50.5 ms, 있으면 10.6 ms, +124 KB
- cargo 는 한 번에 빌드한 crate 들의 기능을 합치므로, conventions 만 켜려면 release 를 crate 마다 따로 빌드해야 함(지금 그렇게 함)
- 모두 켜면 빌드가 단순하고 바이너리마다 +124 KB 쯤

advisor 쪽 regex-syntax 직접 의존은 없앴고, 손으로 짠 SHA-1 은 sha1 crate 로 바꿈.

## 선택지

- a) 고정 패턴 전부 regex crate, perf-dfa 는 전부 켬(워크스페이스 한 줄)
  빌드가 단순하고 나중에 큰 입력을 보는 훅이 늘어도 그대로 빠름. 바이너리마다 +124 KB
- b) 고정 패턴 전부 regex crate, perf-dfa 는 conventions 만(지금)
  다른 바이너리가 작음. crate 마다 따로 빌드해야 함
- c) 비싼 패턴만 예외로 py::re
  0.3 ms 더 아낌, py::re 를 지울 때 다시 봐야 함

**권장 a) 고정 패턴 전부 regex crate, perf-dfa 는 전부 켬(워크스페이스 한 줄)**
Q48 의 이유(py::re 는 물러날 것)가 그대로이고, 기능을 하나로 맞추면 배포 CI 와 빌드가 단순해짐. 크기 차이는 작음

## 코멘트

- 2026-11-20T12:05:05.523Z agent: 결정을 다듬음: 질문 고침, 배경 고침, 선택지 a, b, c 고침, 권장 이유 고침
- 2026-11-22T02:17:54.890Z user: 데몬 형태에서 어떻게 달라질지도 기대되는 부분이긴 하네
- 2026-11-22T02:18:05.661Z agent: 데몬이 되면 패턴을 한 번만 만들고 계속 쓰니, 지금 호출마다 내는 컴파일 비용(작은 입력에서 regex crate 가 느렸던 원인)이 사라져요. 그러면 perf-dfa 의 이점만 남고, 큰 파일에서 차이가 더 벌어질 거예요. 데몬을 만들 때 같은 대조 도구로 다시 재 볼게요.

## 답

a
