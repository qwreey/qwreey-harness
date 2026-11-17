---
format: 1
title: Starlight 문서 사이트 스킬을 어디에 어떤 이름으로 둘까?
description: Starlight 문서 사이트 스킬을 어디에 어떤 이름으로 둘까? 답 a) 팩 docs-site, 스킬 starlight
status: archived; answered a) 팩 docs-site, 스킬 starlight
id: Q24
urgency: later
blocks: 문서 사이트 스킬 만들기(공개 뒤 첫 실사용)
recommended: a
created: 2026-11-17T02:30:23.845Z
answered: 2026-11-17T02:31:55.934Z
answer: a
---

# Q24. Starlight 문서 사이트 스킬을 어디에 어떤 이름으로 둘까?

## 맥락

**연구 결과(`.claude/research/drafts/starlight-site-skill.md`):**
- 스크래치에서 Starlight 0.43.1 로 claude-doctor 문서 23개를 손으로 옮기지 않고 25쪽 사이트로 빌드, 링크 검사 통과.
- 방식: README·docs 원본은 그대로 두고, 빌드할 때 git 에 안 들어가는 사본을 만들어 싣는다(quad 의 `sync-docs.py` 와 같은 생각). 원본을 바로 읽는 방식은 링크 검사와 이미지가 깨져 버림.
- 스크립트는 Node 만(Windows 동료도 `npm run dev`). `.claude/` 기록, PLAN, HUMAN_TODO 는 싣지 않는다.
- 동료는 페이지 하나 복사해 쓰기, 그림 넣기, 미리보기를 직접; 에이전트는 뼈대, 연결, 검사 실패 수정; 배포는 사용자.
- quad 쪽 어긋남 3가지(Starlight 0.43 의 스타일 우선순위 변경 등)는 quad 세션에 넘길 거리.

**정할 것**
- 위치: 기본 꺼진 팩 `packs/docs-site`(사이트가 있는 저장소만 켬, 추천) / 항상 켜진 플러그인(설명 약 500자가 모든 저장소에 실림).
- 이름: `docs-site:starlight`(추천) / `starlight-site`.
- 여러 저장소가 함께 쓰는 preset 패키지는 아직 만들지 않음(세 번째 사이트가 생기면 다시).
- 영어 병행, 도메인은 공개 뒤에.

## 선택지

- a) 팩 docs-site, 스킬 starlight
  사이트 있는 저장소만, 상시 비용 0
- b) 항상 켜진 플러그인
  처음 만들 때 켜는 단계 없음
- c) 공개 뒤에 정함

**권장 a) 팩 docs-site, 스킬 starlight**
사이트를 만드는 저장소는 소수라 모든 저장소에 설명을 싣는 비용이 아깝고, luau-kb·web-security 와 같은 팩 방식으로 켜면 된다.

## 답

a
