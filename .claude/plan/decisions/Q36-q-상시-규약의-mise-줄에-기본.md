---
format: 1
title: q 상시 규약의 mise 안내를 어디로 옮길까?
description: q 상시 규약의 mise 안내를 어디로 옮길까? 권장 a) 상시 줄 빼고 오류 때 뜨는 훅
status: active
id: Q36
urgency: later
blocks: q ambient 문구 한 줄
recommended: a
created: 2026-11-19T06:14:25.567Z
---

# Q36. q 상시 규약의 mise 안내를 어디로 옮길까?

## 맥락

지금은 `plugins/q/context/ambient.md:6` 에 한 줄이 늘 실림(확정 문구):

> If a mise shim fails with "No version is set", call the binary under `<HARNESS_TOOL_INSTALLS>/<tool>/<ver>/` (`~/.claude/harness.env`) directly.

- shim 이 실패할 때만 쓸모 있는데 매 세션 실림.
- harness.env 가 없는 설치(플러그인만 설치)에서는 안내가 틀림. 기본값은 `~/.local/share/mise/installs`.
- 사용자 코멘트: "애초에 mise 를 쓸 수 있게 돕는 스킬로 분리해야하는 기능 아닌가"

## 선택지

- a) 상시 줄 빼고 오류 때 뜨는 훅
  Bash 출력에 'No version is set' 이 나오면 깔린 버전 경로를 찾아 그 자리에서 알림. 상시 비용 0, 경로가 정확함. 모델이 스킬을 안 골라도 됨
- b) 상시 줄 빼고 mise 스킬
  mise 사용법(설치, exec, 버전 고정)까지 담을 수 있음. 대신 에러를 보고 모델이 스킬을 불러야 함
- c) a + b 둘 다
  훅이 알리면서 스킬을 가리킴. 일은 가장 많음
- d) 상시 줄에 기본 경로만 더하기
  가장 작은 변경. 상시 비용은 그대로

**권장 a) 상시 줄 빼고 오류 때 뜨는 훅**
문제가 오류 한 가지일 때만 생기니, 그 오류에 반응하는 훅이 가장 싸고 확실함. 스킬은 mise 지식을 더 담을 일이 생기면 그때 얹으면 됨

## 코멘트

- 2026-11-19T06:16:04.137Z user: 애초에 mise 를 쓸 수 있게 돕는 스킬로 분리해야하는 기능 아닌가 싶기도 하네. 뭔가 그래
- 2026-11-19T06:16:19.412Z agent: 맞아요. 이 줄은 shim 이 실패했을 때만 쓸모 있는데 매 세션 실려요. 다만 스킬은 모델이 스스로 골라 불러야 해서, 에러를 보고도 안 부를 수 있어요. 더 확실한 건 훅이에요. Bash 출력에 "No version is set" 이 나올 때만 알리고, 실제로 깔린 버전 경로(`~/.local/share/mise/installs/<tool>/<ver>/`)를 찾아서 바로 적어 줘요. 상시 비용은 0 이고 경로도 정확해요. 그래서 선택지를 이렇게 바꿨어요. 상시 줄을 빼고 오류 때만 뜨는 훅을 두는 게 추천이고, mise 사용법을 더 담고 싶으면 스킬은 그 위에 얹어요.
- 2026-11-19T06:16:26.468Z agent: 결정을 다듬음: 질문 고침, 배경 고침, 선택지 d 추가, 선택지 a, b, c 고침, 권장 이유 고침
