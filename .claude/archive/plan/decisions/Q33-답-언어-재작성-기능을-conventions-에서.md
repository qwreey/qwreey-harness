---
format: 1
title: 답 언어 재작성 기능을 conventions 에서 떼어 별도 플러그인으로 낼까? 이름은?
description: 답 언어 재작성 기능을 conventions 에서 떼어 별도 플러그인으로 낼까? 이름은? 답 a) 떼어냄, 이름 qwreey-reply-language
status: archived; answered a) 떼어냄, 이름 qwreey-reply-language
id: Q33
urgency: later
blocks: 동료 배포 안내
recommended: a
created: 2026-11-18T01:10:26.274Z
answered: 2026-11-18T01:12:42.806Z
answer: a
---

# Q33. 답 언어 재작성 기능을 conventions 에서 떼어 별도 플러그인으로 낼까? 이름은?

## 맥락

**사용자 제안**: 언어 재작성 유도는 규약(convention)이 아니고, 규약 전체는 필요 없지만 언어 때문에 불편한 사람은 이것만 켜고 싶을 수 있음

**지금 모양**
- `plugins/qwreey-conventions/hooks/reply_language.py`(414줄) 하나. 훅 세 곳(PostToolBatch 의 답 언어 알림, Stop 의 재작성 요구 등)
- 기대는 것: `conv_env.py`(끄기 스위치, 작음), `harness_nonce.py`(lib 사본). 다른 규약 코드와는 얽히지 않음
- 옵션 `harness_reply_language`(기본 켜짐), 테스트 `tests/test-reply-language.py`

**떼는 방법**
- 옮기기(복사 아님): 둘 다 켜면 재작성 요구가 두 번 나오므로 conventions 에서는 뺌
- 실행 중인 세션이 옛 경로를 부르므로 conventions 의 옛 스크립트 파일은 한 판 동안 아무것도 안 하는 껍데기로 남겼다가 나중에 지움
- conventions 만 깐 사람은 이 기능이 빠짐: README 와 HUMAN_TODO 에 새 플러그인 설치를 적음

## 선택지

- a) 떼어냄, 이름 qwreey-reply-language
  하는 일(답 언어)을 그대로 말함. 다른 qwreey-* 와 같은 줄
- b) 떼어냄, 이름 qwreey-language
  짧고, 나중에 언어 관련 기능(주석 언어 등)을 더 담을 여지. 대신 무엇을 하는지 덜 드러남
- c) conventions 에 둠
  할 일 없음. 대신 이것만 쓰려는 사람도 규약 전체를 깔아야 함

**권장 a) 떼어냄, 이름 qwreey-reply-language**
기능이 독립적이라(얽힌 코드 없음) 떼는 비용이 작고, '골라 설치' 원칙에 맞음. 이름은 카드만 보고도 무엇을 하는지 알 수 있는 쪽이 동료에게 쉬움

## 답

a
