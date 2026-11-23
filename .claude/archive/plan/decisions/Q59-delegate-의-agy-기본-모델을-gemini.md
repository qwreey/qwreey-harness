---
format: 1
title: delegate 의 agy 기본 모델을 gemini-3.8-flash-high 에서 gemini-4-hydrogen-high 로 바꿀까?
description: delegate 의 agy 기본 모델을 gemini-3.8-flash-high 에서 gemini-4-hydrogen-high 로 바꿀까? 답 a) gemini-4-hydrogen-high 로
status: archived; answered a) gemini-4-hydrogen-high 로
id: Q59
urgency: soon
blocks: delegate 기본 모델 변경
recommended: a
created: 2026-11-23T00:44:46.970Z
answered: 2026-11-23T00:45:43.336Z
answer: a
---

# Q59. delegate 의 agy 기본 모델을 gemini-3.8-flash-high 에서 gemini-4-hydrogen-high 로 바꿀까?

## 맥락

지금 qwreey-delegate 는 agy 를 `gemini-3.8-flash-high` 로만 부른다. 스킬 글에도 "agy uses only gemini-3.8-flash-high; treat pro as absent" 라고 적혀 있다(SKILL.md, plugin.json userConfig 기본값, delegate.py, README, how-it-works).

`agy models`(1.5.14) 에 `gemini-4-hydrogen-{low,medium,high,xhigh}` 가 있다. 사용자 말로는 가격이 flash 와 같고(12월 말까지 flash 가 프로모션으로 살짝 쌈), 할루시네이션이 크게 줄었으며 작업 성능도 올랐다. argon, neon 은 할당을 너무 많이 쓰고 carbon 은 목록에 없다.

delegate 는 "다른 모델 계열의 시선"으로 쓰고 메인이 검증하므로, 할루시네이션이 줄어든 것이 바로 득이다. 바꾸면 고칠 곳: plugin.json 기본값, delegate.py 기본값, SKILL.md 한 줄(hydrogen 을 쓰고 argon·neon·carbon 은 없는 것으로), README, how-it-works, 판 올림. 바꾸기 전에 hydrogen 으로 짧은 위임 한 번을 돌려 동작을 확인한다.

## 선택지

- a) gemini-4-hydrogen-high 로
  같은 가격에 할루시네이션이 적다. 지금 flash-high 와 같은 effort
- b) gemini-4-hydrogen-xhigh 로
  위임은 좁은 질문 하나라 더 깊게. 할당을 더 쓴다
- c) 12월 말 프로모션이 끝날 때까지 flash 그대로
  그동안 flash 가 살짝 싸다

**권장 a) gemini-4-hydrogen-high 로**
위임의 결과를 메인이 검증하는 구조라 할루시네이션 감소가 가장 큰 득이고, 가격 차이는 작다

## 답

a
