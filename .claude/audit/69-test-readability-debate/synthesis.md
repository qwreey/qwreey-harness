---
format: 1
title: 69. 시험 코드 가독성 debate 종합
description: readable-code 규약에 시험 한 묶음을 더하고(시험마다 확인하는 동작 하나를 doc 주석이나 이름 글로, "and" 가 필요하면 두 시험, 보이지 않는 기대값 이유는 이유 줄이나 assert 메시지), 긴 맥락에서도 지키도록 conventions-check 의 doc 알림이 Rust 시험 함수도 본다
---
# 69. 시험 코드 가독성 debate 종합

> Snapshot 2026-11-22. May differ from now; check current files and git log before relying on it.

P(최소: 규약에 한두 줄, 새 장치 없음)와 Q(넓게: 시험 절과 훅 확인), opus 2개, 1회전, 종합은 메인 세션. 근거: `plugins/qwreey-conventions/rules/readable-code.md`, Q47 결정 기록, `plugins/qwreey-conventions/docs/how-it-works.md`, crate 시험 실측. 사용자(Q58): "b) 글과 시험 doc 알림(Rust #[test], Go Test*)", 그 전 코멘트 "근데 context rot 되어진 상황을 가정하지 않는것 아님? 예를 들어 언어 관련 이슈에서도 작은 맥락이면 상관 없는 경우가 많은데 좀만 커지만 안 지키거나 하잖아. 그런 경우에서도 훅이 없어도 일관성을 유지할 수 있을까?".

## Trigger
사용자가 crate 코드를 칭찬하면서 한 가지를 짚었다: "#[cfg(test)] mod tests { 부분들이 주석 없이 붙어있고 각 테스트 단위가 뭘 하는지, 그 안에서도 뭘 assert 하는지 코드를 읽지 않으면 모른다". Q47 a 로 전역 규약 문구는 토론 뒤에 정하기로 했다.

## Facts both sides confirmed
- 규약은 2026-11-16 부터 있었는데, 규약만 있고 브리프가 없던 11-20 오후에 쓴 crate 의 시험 doc 비율이 낮았다: sessions 2/14, proc-guard 8/38, harness-hook 40/75. 브리프(시험마다 한 줄 doc) 뒤에 쓴 crate 는 모두 100%였다(q 24/24, advisor 44/44, conventions 117/117 등). 전체 378개 중 doc 281개.
- 브리프를 받고도 이름표와 기대값 이유는 고르지 않았다(q 시험 이름표 0/24, assert 메시지 5/71).
- 규약의 이름표는 "no period, numbering or reason"(`readable-code.md`), 몸 안의 이유는 "one line at the trap, below the step label". 그래서 브리프의 "기대값 이유를 이름표에"는 규약과 부딪친다.
- 짧은 순수 함수 시험에는 나눌 준비·실행·확인이 없다. 본보기 시험(`crates/harness-hook/src/py/repr.rs`)도 AAA 가 아니라 사례 묶음마다 이름표를 단다.
- Luau 러너와 JS `it("...")` 는 이름을 글로 받고 시험은 이름 없는 클로저다(`packs/luau-kb/skills/luau-testing/references/runners.md`).
- layout 알림은 시험 함수에도 걸린다(15줄 이상, 빈 줄 없음). doc summary 알림은 공개 함수만 보므로 Rust 시험에는 나지 않는다. Python unittest 메서드와 Go 대문자 `Test*` 는 이미 공개로 잡힌다.
- 밖의 지침: Rust Book "Custom messages are useful for documenting what an assertion means", Go CodeReviewComments "Useful Test Failures", Google SWE book 12장("A test's name should summarize the behavior", 한 시험에 동작 하나, 실패 메시지에 기대값과 실제값).

## Accepted by both
- 규약에 시험을 직접 부르는 줄이 하나 있어야 한다(원칙만으로는 옮겨지지 않았다).
- 준비·실행·확인 이름표는 따로 요구하지 않고 이미 있는 단계 규칙에 맡긴다.
- 기대값 이유는 이름표가 아니라 이유 줄이나 assert 메시지에 둔다.
- 이름을 글로 받는 러너는 doc 주석 대신 그 글을 쓴다.
- 새 rule 파일이나 설정 스위치는 두지 않는다.

## Disagreements
| Issue | P | Q | Chosen and why |
|---|---|---|---|
| 훅 알림 | 두지 않는다(브리프 글만으로 100%, 언어마다 시험 알아보기 비용) | Rust `#[test]`, Go `Test*` 를 doc 알림 대상에 | Q(사용자 b). 100% 는 새 맥락의 서브에이전트가 브리프를 바로 위에 두고 쓴 결과라, 긴 세션에서 맥락당 한 번 실린 규약이 밀리는 경우를 재지 못했다(사용자 코멘트). 규약이 긴 맥락에서 버티는 것은 편집마다의 알림 몫이다 |
| "and" 면 두 시험 | 언급 없음 | 넣는다(Google) | 넣음(사용자 b, c 를 고르지 않음) |
| 낱말 수 | 55 단어 bullet 하나 | 약 90 단어 세 줄 | P 의 한 bullet 꼴에 Q 의 "and" 줄을 더함(약 70 단어) |

## Alternatives
| Option | Pros | Cons | Raised by |
|---|---|---|---|
| 바꾸지 않음 | 비용 0 | 실측이 반박 | P |
| 시험 파일 전용 rule(`paths`) | 시험을 열 때만 실림 | Rust 의 파일 안 `mod tests` 를 경로로 못 잡음 | P |
| 저장소 전용(Q47 b) | 전역을 안 건드림 | Q47 a 로 정해짐 | P, Q |
| 브리프 세 줄 그대로 | 실측에서 효과 | Rust 꼴, 이름표 규칙과 부딪침 | current |

## Proposed wording
`readable-code.md` 의 "The second time the same few-line loop ..." 줄 뒤(적용함):
```
- Tests follow the same layout. Each test says the one behavior it checks in a one-line doc comment, or in the name string where the runner takes one; a line that needs "and" means two tests. An expected value whose cause the test does not show gets a reason line or an assertion message (`512.0`: "x" is not a number, so the default).
```
훅: conventions-check 의 doc summary 가 Rust 의 `#[test]`, `#[<path>::test]` 함수도 본다. 이번 편집이 쓰거나 키운 함수에만, info, 막지 않음, python 과 Rust 양쪽.

## Not accepted
- P: 훅 없음. 긴 맥락의 일관성을 재지 못했다.
- 기대값 이유를 기계로 확인하는 것: 둘 다 방법이 없다고 했다. 글로만 남는다.

## Fix regardless
- 이 저장소의 시험 몸 안 이름표 가운데 한국어인 것(`crates/qwreey-workspace/src/pyval.rs`)을 영어로.
- 브리프 전 crate(sessions, proc-guard, harness-hook)의 시험을 새 규약대로 다듬는다(Q47 a, 동작은 그대로).

## For the user
1. 규약 글과 훅: (a) 글만 (b) 글과 시험 doc 알림 (c) b 에서 "and" 줄을 뺌. 답: b.

## Next
1. 훅(python, Rust, 대조 사례)과 기존 시험 다듬기를 에이전트 둘이 나란히 한다.
2. 둘을 합친 뒤 qwreey-conventions 판을 올린다.
