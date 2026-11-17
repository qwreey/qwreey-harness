---
format: 1
title: rule 끝 스킬 포인터를 "Before you …, load" 꼴로 바꿀 문구 확인
description: rule 끝 스킬 포인터를 "Before you …, load" 꼴로 바꿀 문구 확인 답 b) comments 는 지금 꼴 유지, 나머지 셋만
status: archived; answered b) comments 는 지금 꼴 유지, 나머지 셋만
id: Q5
recommended: b
created: 2026-11-16T07:03:54.418Z
answered: 2026-11-16T07:58:56.962Z
answer: b
---

# Q5. rule 끝 스킬 포인터를 "Before you …, load" 꼴로 바꿀 문구 확인

## 맥락

**왜:** audit 57 실측에서 지금 꼴("Details…: load X")은 스킬을 한 번도 로드하지 않았다(sonnet 0/21, opus 0/3). opus 는 다가올 행동을 짚은 "Before you <행동>, load X" 꼴에서만 3/3 로드했다. sonnet 은 어떤 꼴이든 0 이라, 효과는 opus 에서만 기대한다. 이미 승인하신 권고("권고대로 한번 시도해보자")의 2번이고, 늘 실리는 문구라 바꾸기 전에 보여 드린다.

**제안 문구 (영어, rule 마지막 줄을 바꿈)**
- comments: `Before you write or edit a comment, docstring or doc comment, load the qwreey-conventions:comments skill (repo comment settings, what a hook notice wants). A repo's own rules win.`
- code-reuse: `Before you add a @copy-of or @start-replace marker, or act on a reuse notice, load the qwreey-conventions:code-reuse skill. A repo's own rules win.`
- agent-docs: `Before you add a section, table or rule line to such a document, or act on a hook notice about one, load the qwreey-conventions:agent-docs skill. A repo's own rules win.`
- coderag agent-records: `Before you create, move, close or archive a record, or rewrite a README index, load the coderag:agent-records skill.` (coderag 저장소 수정)

**걸리는 점:** comments 는 코드 쓸 때마다 걸릴 수 있다. 스킬 본문이 약 11.8k자라 opus 가 매번 로드하면 비용이 는다. 실측에서는 그 대신 영어 주석 설정을 지켰다.

**함께 하는 것(승인됨, 진행 중):** 저장소 설정 값(`comment_language` 등)을 rule 과 함께 주입("This repo: comment_language = en"), code-reuse 스킬에 형제 저장소 `@copy-of` 예시.

## 선택지

- a) 제안 문구 그대로 네 개
  opus 에서 잰 효과가 있는 유일한 꼴
- b) comments 는 지금 꼴 유지, 나머지 셋만
  코드 쓸 때마다 11.8k자 로드를 피함; 설정 값은 주입으로 대신
- c) 문구 수정 후 적용
  메모로 고칠 곳 적기

**권장 b) comments 는 지금 꼴 유지, 나머지 셋만**
comments 스킬이 지키게 하던 핵심(comment_language)은 설정 값 주입이 맡는다. 코드 쓸 때마다 큰 스킬을 로드하는 비용은 피하고, 행동이 드문 나머지 셋만 트리거 꼴로 바꾼다.

## 코멘트

- 2026-11-16T07:58:44.545Z user: 다만 그러면 코멘트에 관한 코드 퀄리티가 유지되기 어렵다면 결국 나 또한 코드를 읽기 어렵기에 컨벤션의 도움이 떨어지긴 할것 같기도 하고. 필요했던걸 피하는 모양인건 조금 그래.

## 답

b
