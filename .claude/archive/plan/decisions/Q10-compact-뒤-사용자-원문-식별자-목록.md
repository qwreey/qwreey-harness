---
format: 1
title: compact 뒤 사용자 원문·식별자 목록 주입을 qwreey-sessions 에 넣을까?
description: compact 뒤 사용자 원문·식별자 목록 주입을 qwreey-sessions 에 넣을까? 답 a) 넣는다
status: archived; answered a) 넣는다
id: Q10
urgency: soon
blocks: qwreey-sessions compact 복원 강화
recommended: a
created: 2026-11-16T08:23:42.560Z
answered: 2026-11-16T08:40:38.692Z
answer: a
---

# Q10. compact 뒤 사용자 원문·식별자 목록 주입을 qwreey-sessions 에 넣을까?

## 맥락

**실측(audit 61, USD 9.7):** 이 세션의 실제 compact 구간 3개(346k~568k 토큰)에서 그 구간 앞쪽 사실(커밋, 경로, 오류, 사용자 원문, 버린 방안)을 물었다.

| | 정답 |
|---|---|
| CC compact 만 | 17/27 (63%) |
| 지금 qwreey-sessions | 21/27 (78%) |
| + 사용자 원문·식별자 목록 | 26/27 (96%) |

158k 짧은 구간은 셋 다 만점이라 긴 세션에서만 차이가 난다. 외부 hermes(+22.5pt)와 방향이 같다.

**무엇을 넣나:** compact 직후 한 번(SessionStart compact), 8,000자 이하, 모델 호출 없음.
1. 그 구간의 사용자 발화 원문(알림·명령 줄 빼고, 붙여넣은 큰 글은 잘라서)
2. 오류 첫 줄, 바뀐 파일, 커밋과 첫 줄, id
3. 트랜스크립트 검색 요령 한 줄(경로는 CC 가 이미 줌; JSONL 줄이 길어 Grep 이 생략하니 `.{0,120}` 패턴으로)

**약한 점:** 칸당 1회라 크기는 믿기 어렵다. 채점이 블라인드가 아니다. 서브에이전트가 고친 파일은 목록에 안 잡힌다. compact 마다 약 2~3k 토큰이 는다.

**덤:** 지금 PreCompact 요약 지시는 효과가 안 보였다(지울지는 따로).

## 선택지

- a) 넣는다
  방향이 외부 근거와 같고 모델 호출 없이 싸다
- b) 2회 더 잰 뒤 결정
  약 USD 1~1.5, 표본을 늘림
- c) 보류

**권장 a) 넣는다**
값이 싸고(모델 호출 없음, 2~3k 토큰) 되돌리기 쉽다. 끌 수 있게 만들고, 쓰면서 효과를 보는 편이 추가 실측보다 낫다. 자고 오셨을 때 맥락이 끊기는 문제와 바로 이어진다.

## 답

a
