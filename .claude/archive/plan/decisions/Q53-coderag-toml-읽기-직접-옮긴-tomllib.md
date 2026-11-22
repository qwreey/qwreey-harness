---
format: 1
title: "coderag.toml 읽기: 직접 옮긴 tomllib(약 960줄)을 둘까, toml crate 로 바꿀까?"
description: "coderag.toml 읽기: 직접 옮긴 tomllib(약 960줄)을 둘까, toml crate 로 바꿀까? 답 a) python 이 물러날 때까지 직접 옮긴 판을 두고, 그때 toml crate 로"
status: archived; answered a) python 이 물러날 때까지 직접 옮긴 판을 두고, 그때 toml crate 로
id: Q53
urgency: later
blocks: 없음(지금 판으로 돈다)
recommended: a
created: 2026-11-22T03:35:04.529Z
answered: 2026-11-22T03:37:08.779Z
answer: a
---

# Q53. coderag.toml 읽기: 직접 옮긴 tomllib(약 960줄)을 둘까, toml crate 로 바꿀까?

## 맥락

conventions 2단계 에이전트가 bash-bypass-reminder 의 coderag.toml 읽기 때문에 python tomllib 을 harness-hook 에 손으로 옮겼다(`py/toml`, 시험 포함 약 1.1k 줄).

- 이유: 새 의존성은 사용자가 정한다. 그리고 python 은 못 읽은 파일 전체를 `{}` 로 보므로, 받는 글과 거절하는 글이 python 과 같아야 출력이 같다. toml crate 는 날짜, 정수 크기, 키 다시 쓰기의 판정이 조금씩 다르다.
- 시험: tomllib 과 글 약 1만 8천 개를 견줘 모두 같다.
- Q48 과 같은 모양이다. 거기서는 "python 이 물러날 때까지" 사용자 패턴을 py::re 로 두기로 했다.

## 선택지

- a) python 이 물러날 때까지 직접 옮긴 판을 두고, 그때 toml crate 로
  대조가 바이트로 맞고, 의존성이 늘지 않는다. Q48 과 같은 기준
- b) 지금 toml crate 로 바꾼다
  코드 약 1k 줄이 준다. 대신 거절하는 글이 달라 출력이 갈리는 자리가 생기고 의존성이 는다

**권장 a) python 이 물러날 때까지 직접 옮긴 판을 두고, 그때 toml crate 로**
출력 대조가 지금 이식의 안전장치이고, Q48 에서 같은 기준을 정했다

## 코멘트

- 2026-11-22T03:37:04.853Z user: 그냥 나중의 일이 늘어나고 지금의 일이 늘어나기만 하는건 유의해야하지 않을까 싶음
- 2026-11-22T03:37:17.284Z agent: 맞아요. 대조 때문에 넣은 것(py::re 사용자 패턴, py::toml, python 호환 json 파서 등)은 python 이 물러날 때 걷어낼 일이 돼요. 두 가지로 줄일게요.
  1) 계획에 "python 이 물러날 때 걷어낼 것" 목록을 한 곳에 둬서, 나중 일이 흩어지지 않고 크기가 보이게 해요.
  2) 앞으로는 이런 판을 새로 짜기 전에, 갈리는 입력이 실제로 오는지 먼저 재요. 오지 않는 입력에서만 갈리면 표준 crate 를 쓰고 그 차이는 대조에서 알려진 차이로 둬요(toml 은 이미 짜여 있어 a 그대로).

## 답

a
