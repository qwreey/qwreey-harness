---
format: 1
title: agent-docs rule 에 두 줄 추가·한 줄 수정, 이 문구로 합칠까?
description: agent-docs rule 에 두 줄 추가·한 줄 수정, 이 문구로 합칠까? 답 a) 이 문구로 합침
status: archived; answered a) 이 문구로 합침
id: Q12
urgency: soon
blocks: D11 4번(S10) 합치기
recommended: a
created: 2026-11-16T10:36:12.657Z
answered: 2026-11-17T00:17:20.192Z
answer: a
---

# Q12. agent-docs rule 에 두 줄 추가·한 줄 수정, 이 문구로 합칠까?

## 맥락

**무엇:** CLAUDE.md, SKILL.md, rules 를 쓰거나 고칠 때 실리는 agent-docs rule. 스킬에만 있던 지킬 것 중 기계로 못 잡는 두 가지를 rule 로 옮긴다. 나머지는 훅 검사로 갔다(아래).

**더하는 두 줄**
- `State a principle once and let the model generalize; do not list cases it would infer.`
- `Why it is built this way, for maintainers, goes in the skill's references/rationale.md (linked in one line) or a docs/ folder, not in the entry document.`

**고치는 한 줄** ("or act on a hook notice about one" 을 뺌, 알림이 이제 고치는 법을 직접 주므로)
- `Before you add a section, table or rule line to such a document, load the qwreey-conventions:agent-docs skill. A repo's own rules win.`

**크기:** rule 926 → 1,140자. 코드 파일 주입 최대는 8,752/9,000 그대로(agent-docs 는 문서에만 실림).

**훅 검사로 간 것(문구 승인 불필요, 같이 합쳐짐)**
- 표시(@copy-of 등)가 문서 주석 안에 있거나, 언어에 맞지 않는 꼴(Astro HTML 주석, JSON), `../repo:path` 처럼 섞인 꼴 → 알림이 바른 꼴을 줌
- SKILL.md description 이 영어가 아니거나 "언제 쓰는지" 가 없거나 1·2인칭 → 알림
- 모델이 읽는 문서에 한국어 줄 → 알림(이미 한국어인 문서는 제외)
- 원장 id 옆 .md 가 함께 배포되지 않음 → 알림
- 이 저장소와 coderag 에 돌려 보니 살아 있는 파일의 오탐은 1줄(q doctor 의 사용자용 한국어 표 머리)

시험 모두 통과(conventions-check 218, reuse-check 78).

## 선택지

- a) 이 문구로 합침
- b) 문구 고친 뒤
  코멘트로
- c) rule 줄은 빼고 훅만 합침

**권장 a) 이 문구로 합침**
기계로 못 잡는 지킬 것은 rule 에 있어야 스킬을 안 읽어도 지켜진다(audit 62). 두 줄 모두 짧고 문서에만 실린다.

## 답

a
