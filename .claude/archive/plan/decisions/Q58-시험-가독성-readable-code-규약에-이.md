---
format: 1
title: "시험 가독성: readable-code 규약에 이 한 묶음(약 70 단어)을 넣고, 시험 함수도 doc 알림 대상에 넣을까?"
description: "시험 가독성: readable-code 규약에 이 한 묶음(약 70 단어)을 넣고, 시험 함수도 doc 알림 대상에 넣을까? 답 b) 글과 시험 doc 알림(Rust #[test], Go Test*)"
status: "archived; answered b) 글과 시험 doc 알림(Rust #[test], Go Test*)"
id: Q58
urgency: soon
blocks: 규약 반영, 그 뒤 기존 crate 시험 다듬기
recommended: b
created: 2026-11-22T07:43:38.606Z
answered: 2026-11-22T07:52:46.326Z
answer: b
---

# Q58. 시험 가독성: readable-code 규약에 이 한 묶음(약 70 단어)을 넣고, 시험 함수도 doc 알림 대상에 넣을까?

## 맥락

audit 69 토론(P 최소, Q 넓게)이 거의 모였다.
- 실측: 규약만 있고 브리프가 없을 때 쓴 crate 는 시험 doc 이 낮았다(sessions 2/14, proc-guard 8/38). 브리프 뒤에 쓴 crate 는 100%였다. 다만 이 100% 는 새 맥락의 서브에이전트가 브리프를 바로 위에 두고 쓴 결과다. 긴 세션(context rot)에서는 맥락당 한 번 실린 규약이 뒤로 밀린다(답 언어가 긴 도구 실행 뒤에 새던 것과 같은 모양, 사용자 코멘트).
- 지금 규약이 긴 맥락에서 버티는 것은 편집마다 다시 알리는 훅 몫이다(공개 함수 doc 없음, 빈 줄 없는 긴 함수). 시험 함수는 doc 알림에서 빠져 있다(python 시험 메서드만 이미 걸림).
- 브리프의 "준비·실행·확인 이름표"는 짧은 시험에서 소음이라 이미 있는 단계 규칙에 맡기고, "기대값 이유를 이름표에"는 "이름표에 이유를 쓰지 않는다"와 부딪쳐 이유 줄이나 assert 메시지로 옮긴다.

넣을 글(예시 코드 앞, "The second time ..." 줄 뒤):
```
- Tests follow the same layout. Each test says the one behavior it checks in a one-line doc comment, or in the name string where the runner takes one; a line that needs "and" means two tests. An expected value whose cause the test does not show gets a reason line or an assertion message (`512.0`: "x" is not a number, so the default).
```

훅(b): conventions-check 의 doc summary 알림이 Rust `#[test]`(와 `#[<path>::test]`), Go `func Test*` 도 본다. 이번 편집이 쓰거나 키운 함수에만, info, 막지 않음. python 과 Rust 두 구현에 넣고 대조 사례를 더한다. 기대값 이유(셋째 문장)는 기계로 잴 수 없어 글로만 남는다.

## 선택지

- a) 글만 넣는다(훅 알림 없음)
  구현 비용 0. 대신 긴 세션에서 시험 한 줄이 빠지기 쉽다
- b) 글과 시험 doc 알림(Rust #[test], Go Test*)
  긴 맥락에서도 편집마다 상기. 지금 규약이 버티는 방식과 같다
- c) b 에서 "and 는 두 시험" 줄을 뺀다
  기존 시험을 다듬을 때 나누기까지 하지 않는다

**권장 b) 글과 시험 doc 알림(Rust #[test], Go Test*)**
긴 맥락에서는 글만으로 일관성이 유지되지 않는다는 점(사용자 코멘트)이 맞고, 규약을 지키게 하는 지금 장치가 편집마다의 알림이다

## 코멘트

- 2026-11-22T07:51:00.101Z user: 근데 context rot 되어진 상황을 가정하지 않는것 아님? 예를 들어 언어 관련 이슈에서도 작은 맥락이면 상관 없는 경우가 많은데 좀만 커지만 안 지키거나 하잖아. 그런 경우에서도 훅이 없어도 일관성을 유지할 수 있을까?
- 2026-11-22T07:51:21.239Z agent: 맞아요, 그 가정이 빠졌어요. doc 100% 는 새 맥락에서 막 시작한 서브에이전트가 브리프를 바로 위에 두고 쓴 결과예요. 긴 세션에서 규약은 맥락당 한 번만 실리고 점점 뒤로 밀려요. 답 언어도 같은 모양이었어요(긴 도구 실행 뒤에 몰려 영어로 샜다). 그래서 reply-language 를 훅으로 만들었죠.

  지금 규약이 긴 맥락에서도 버티는 것은 훅이 편집마다 다시 알려 주는 몫이에요. 공개 함수의 doc 없음, 빈 줄 없는 긴 함수가 그 예예요. 시험 함수는 이 doc 알림에서 빠져 있어요(python 시험 메서드만 이미 걸린다). 그러니 훅이 없으면 (1)은 긴 세션에서 무너질 가능성이 커요.

  정리하면:
  - (1) 시험의 한 줄: 훅으로 지킬 수 있다. Rust `#[test]`, Go `Test*` 를 doc 알림 대상에 넣는다. 이번 편집이 쓰거나 키운 함수에만 뜨고 막지 않는다.
  - (2) 단계: 이미 layout 알림이 시험 함수에도 걸린다.
  - (3) 기대값 이유: 기계로 못 잰다. 글로만 남고, 긴 맥락에서 약해지는 것을 받아들여야 한다.

  권장을 b(글 + 시험 doc 알림)로 바꿀게요. 비용은 python·Rust 두 구현과 대조 사례 몇 개예요.
- 2026-11-22T07:51:34.080Z agent: 결정을 다듬음: 질문 고침, 배경 고침, 선택지 a, b, c 고침, 권장 a → b, 권장 이유 고침

## 답

b
