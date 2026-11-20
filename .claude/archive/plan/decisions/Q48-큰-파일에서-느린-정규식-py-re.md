---
format: 1
title: Rust 훅의 정규식을 표준 regex crate 로 옮길까, 어떤 순서로?
description: "Rust 훅의 정규식을 표준 regex crate 로 옮길까, 어떤 순서로? 답 a) 단계: 고정 패턴은 지금 regex crate, 사용자 패턴은 python 이 물러날 때까지 py::re"
status: "archived; answered a) 단계: 고정 패턴은 지금 regex crate, 사용자 패턴은 python 이 물러날 때까지 py::re"
id: Q48
urgency: soon
blocks: conventions 큰 파일 CPU
recommended: a
created: 2026-11-20T09:28:40.439Z
answered: 2026-11-20T09:33:49.707Z
answer: a
---

# Q48. Rust 훅의 정규식을 표준 regex crate 로 옮길까, 어떤 순서로?

## 맥락

사용자: "파이썬 정본이 필요 없어지게 된다면 의미가 없을것 같기도 ... 지금은 정본과 테스트를 맞추려고 억지로 넣는거라면 regex crate 를 안 쓸 이유가 있나"

py::re 는 python 과 바이트 대조를 맞추려고 있음. python 정본이 물러나면 남길 이유가 없음.

잰 것(conventions 큰 파일, 19개 패턴 합계 µs): py::re 32,911 / python re 약 15,300 / regex crate 199(lookaround 4개 빼고)

regex crate 의 걸림
- lookaround 를 쓰는 고정 패턴(conventions 4개, proc-guard 몇 개)은 다시 써야 함(캡처 그룹이나 코드로)
- 사용자가 적는 패턴(pgrep -f, conventions.json, 키워드 목록)은 python re 와 끝자리 뜻이 다를 수 있어 대조 시험에 예외가 생김
- 크기와 빌드 시간이 늘어남(아직 안 잼)

## 선택지

- a) 단계: 고정 패턴은 지금 regex crate, 사용자 패턴은 python 이 물러날 때까지 py::re
  빠름과 표준을 지금 얻고, 대조 시험은 사용자 패턴에서 그대로 유지. python 이 물러나면 py::re 를 지움
- b) 전부 지금 regex crate, py::re 지움
  코드가 가장 줄음. 사용자 패턴의 뜻 차이는 문서로 두고 못 읽는 패턴은 막지 않고 통과
- c) py::re 에 첫 글자 건너뛰기만
  작은 변경, 대신 python 이 물러나면 버릴 코드에 더 투자

**권장 a) 단계: 고정 패턴은 지금 regex crate, 사용자 패턴은 python 이 물러날 때까지 py::re**
우리가 쓰는 패턴은 표준 엔진으로 빨라지고, 대조라는 안전망은 사용자 패턴처럼 뜻이 갈릴 수 있는 곳에만 남김. python 이 물러나면 py::re 를 지우기 쉬움

## 코멘트

- 2026-11-20T09:32:27.489Z user: 음. 파이썬 정본이 필요 없어지게 된다면 의미가 없을것 같기도. 좀더 표준적인 regex 를 쓰지 말아야할 이유도 없고. 언젠간 파이썬과 별계가 된다면 떨어져 나갈테니까. 지금은 정본과 테스트를 맞추려고 억지로 넣는거라면 regex crate 를 안 쓸 이유가 있나 싶어
- 2026-11-20T09:33:08.305Z agent: 맞아요. py::re 는 python 과 바이트까지 같게 하려고 만든 것이라, python 정본이 물러나면 이유가 사라져요. regex crate 를 안 쓸 이유는 두 가지뿐이에요.

  1. 고정 패턴 중 lookaround 를 쓰는 것(conventions 4개, proc-guard 몇 개)은 regex crate 가 못 돌림. 대부분 캡처 그룹이나 코드 한두 줄로 바꿔 쓸 수 있어요.
  2. 사용자가 적는 패턴(pgrep -f 패턴, conventions.json, 키워드 목록)은 python re 와 뜻이 조금 다를 수 있어요. 대조 시험이 이런 끝자리에서 어긋남으로 잡힘.

  그래서 단계로 가면 좋겠어요: 우리가 쓰는 고정 패턴은 지금 regex crate 로(lookaround 는 다시 써서), 사용자 패턴은 python 이 물러날 때까지 py::re, 물러나면 py::re 를 통째로 지움. 선택지를 이렇게 고칠게요.
- 2026-11-20T09:33:21.263Z agent: 결정을 다듬음: 질문 고침, 배경 고침, 선택지 a, b, c 고침, 권장 이유 고침

## 답

a
