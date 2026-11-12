---
title: records-in-coderag
description: 기록 규약을 coderag 정본 하나로 합치는 초안 — coderag:agent-records 스킬·내장 rule, frontmatter(들어갈 때 필수로 되돌림), 닫기 기준, 바뀔 파일 목록, 질문 4개
status: landed in ../../../../../../coderag/skills/agent-records/SKILL.md
---

# records-in-coderag

에이전트 기록 규약 하나를 coderag 에 정본으로 두는 초안. qwreey-conventions 의 `agent-records` 스킬·rule 과 coderag 의 `docs-frontmatter` 스킬을 합치고, rule 은 coderag 플러그인이 직접 싣는다(사용자 선택 (a)). q `records_check.py` 를 coderag 로 옮기는 일은 다음 단계다.
- [skills/agent-records/SKILL.md](skills/agent-records/SKILL.md) - 합친 스킬 초안(coderag `skills/agent-records/` 자리)
- [skills/agent-records/references/frontmatter-keys.md](skills/agent-records/references/frontmatter-keys.md) - docs-frontmatter 에서 옮긴 키·절 메타·kind 표
- [rules/agent-records.md](rules/agent-records.md) - coderag 내장 rule 초안, 경로는 지금 qwreey-conventions rule 과 같음
- [changes.md](changes.md) - 들어갈 때 바뀌는 파일 전부와 정확한 고침, coderag 내장 팩 구현, lint 수준, Codex·agy, 순서
- [open-questions.md](open-questions.md) - 사용자에게 물을 4가지

`skills/`, `rules/` 아래 파일은 대상 파일의 사본이라 자기 frontmatter(name, paths)만 갖는다. coderag post-edit 훅이 이들을 기록으로 보고 "frontmatter 없음/title 없음" 을 알리는데, 그 알림이 바로 이 초안이 고치려는 동작이다.

## 스킬을 늘리나 새로 두나

`docs-frontmatter` 를 넓히면 coderag 안의 참조(README.md:18, tech-design.md:333, hook.rs:94 알림 문구, docs-backfill SKILL.md:11·28, 완료 항목 TODO.md:26)가 그대로 살지만, 이름이 "frontmatter" 라서 이제 선택이 된 부분을 이름으로 내세우고, 닫기·archive·폴더 같은 작업에서 스킬 라우팅이 덜 걸린다. 새 스킬을 두면 그 참조 다섯 곳을 고쳐야 하는데, 넷은 어차피 이번에 고치는 파일(알림 문구는 frontmatter 선택 때문에 바뀐다, backfill 은 status 추정이 바뀐다)이라 추가 비용이 작다. claude-doctor 쪽 참조(CLAUDE.md:11, .claude/README.md:3, doctor SKILL.md:43·67, records_check.py:2, .gitignore:10, test-rules-inject.py:61)는 어느 쪽이든 접두어가 바뀌므로 고친다. 다른 형제 저장소와 `home/` 에는 두 이름 모두 언급이 없다. 추천은 새 스킬 `coderag:agent-records` 와 같은 이름의 rule, `docs-frontmatter` 는 지우고 키는 references 로: 짧은 이름 `agent-records` 가 rule 이름(`rules_exclude` 값), 주석, doctor 문구에 이미 쓰여 접두어만 바뀐다. 이름은 사용자가 정한다(open-questions Q1).

## 정한 것

- frontmatter 는 선택. 새 살아 있는 문서에 title·description 권함(검색 요약), 스냅샷에는 요구하지 않음, 옛 문서는 채우지 않음. 팩 지식 문서는 지금처럼 필수.
- active 를 떠나면 같은 커밋에서 `archive/<원래 폴더>/` 로 `git mv`, 필수. docs-frontmatter 의 "status: archived 로 두거나 옮긴다" 는 없앤다.
- 닫는 기준은 "지금 정본으로 읽을 사람이 있나". 일을 끝낸 것은 이유가 아니다(구현을 마친 base 스펙은 active). 폴더별 한 줄씩과 rule 본문 한 줄에 넣었다. "끝난(finished) 문서" 표현은 changes.md 에서 모두 "닫힌(active 아님)" 으로 바꾼다.
- 갈음 표기는 쓰기 정본 `status: superseded by <경로>` 하나, `superseded_by:` 는 읽기만(Q2).
- coderag 플러그인 루트를 내장 팩 `coderag` 로 보고 그 `rules/` 를 프로젝트 팩 목록과 무관하게 싣는다(Q3).
- lint: frontmatter 없음·title 없음·description 없음은 프로젝트 문서에서 권고(info), 새 살아 있는 문서 Write 때만 훅이 알림. 값 오류는 그대로 오류.
- coderag 가 frontmatter 없는 문서의 첫 줄 `status:` 도 읽게 한다(audit/38 은 넣지 않기로 했지만, 그 전제였던 "첫 줄 status 는 옛 초안뿐" 이 frontmatter 선택으로 바뀐다).
- 스킬·references·rule 은 영어(원천 agent-records 가 영어, 사용자가 coderag 스킬이 한국어일 필요 없다고 함). 다른 coderag 스킬은 참조 고침만 하고 그대로 둔다. coderag 훅 알림 문구는 그 파일 언어(한국어)로 적었다.
- 크기: 스킬 86줄 6.3KB + references 3.9KB, 지금 둘의 합 10.9KB 보다 작다. rule 본문 7줄.
