---
format: 1
title: coderag 형식 버전과 L0/L1/L2 단계 공개 설계
description: 기록·팩 문서에 형식 버전(format)을 달아 버전대로 읽고 active 문서만 마이그레이션하는 법, 검색 결과를 L0(제목·설명)·L1(절 목차)·L2(절 본문)로 예산 안에서 펼치는 법, compact 뒤 가리킴 상한. 사용자 결정 반영.
status: active
---
# coderag 형식 버전과 L0/L1/L2 단계 공개

근거: `.claude/audit/42-memory-systems-survey/A.md`, `B.md`(메모리 시스템 8개 정적 조사), `.claude/audit/41-knowledge-packs-debate/synthesis.md`(coderag 구조).
사용자: "파일 마다 쓰여진 대상 coderag 버전을 두고 필요한 경우 마이그레이션을 하는게 좋을것 같기도", "메모리 래밸을 'L0-L1-L2' 식으로 장기 단기를 나눈다던가 하는것도 괜찮은 아이디어 같고. 우린 archive 같은 래밸을 두었지만 그것보다 폭넓은 구조를 택하는 곳들이 있더라고".

## 1. 지금 있는 것
- 색인: `cache.rs` `SCHEMA_VERSION` 2. 원문에서 다시 만드는 파생물이라 버전이 바뀌면 `coderag gen` 으로 다시 만든다(옛 캐시는 경고). 이 원칙은 유지한다.
- 원문 문서(기록, 팩 reference)에는 형식 버전이 없다. 규약은 `coderag:agent-records` 스킬과 `references/frontmatter-keys.md` 에 있다.
- 단계 공개의 바탕은 이미 있다: `search` 의 두 줄(경로:줄, 제목, kind / 요약)이 L0, `get --sections` 가 L1, `get --section <절> --body` 가 L2. 빠진 것은 이것을 한 번의 호출에서 예산에 맞춰 섞는 일이다.
- compact 뒤 가리킴(M6): 제목 — 경로를 최대 20개. 글자 상한이 없고 설명이 없다.

## 2. 우리 구조와 다른 시스템의 "계층"
조사한 시스템의 계층은 두 종류다. 둘을 섞지 않는다.
- 역할 계층(openJiuwen 6종, Letta core/recall/archival): 무엇을 기억하는가. 우리는 이미 폴더와 장치로 나눠 두었다.

| 역할 | 우리 쪽 |
|---|---|
| core(늘 켜짐) | rule(경로 주입), CLAUDE.md, 스킬 설명 |
| semantic(정본 지식) | `base/`, 팩 references |
| episodic(있었던 일) | `sessions/`, `audit/`, `handoff/`(스냅샷) |
| procedural(하는 법) | 스킬 본문 |
| working(지금 작업) | 세션 맥락, compact 뒤 가리킴 |
| archival(지난 것) | `archive/`, active 아닌 status |

  새 역할 계층은 더하지 않는다. 대신 doctor 가 core 크기 상한을 본다(Letta 의 core 65,536자 상한과 같은 생각): 늘 켜진 스킬 설명 합계, rule 본문 합계.
- 공개 단계(openJiuwen L0/L1/L2, memU, Letta 의 색인 따라 한 단계씩): 같은 항목을 얼마나 펼쳐 보여 주나. 이것을 coderag 에 들인다(4절).

## 3. 형식 버전
버전을 다는 곳은 셋이다.
1. 문서: frontmatter `format: <정수>`. 새로 만드는 frontmatter 에는 늘 적는다(사람이 쓴 기록, 세션 기록 반입처럼 도구가 만든 것 모두). 옛 문서는 채우지 않고 없으면 1로 읽는다. 지금의 규약(agent-records + frontmatter-keys)을 형식 1로 고정한다.
2. 팩 매니페스트 `[pack] format`, 프로젝트 `coderag.toml` 최상위 `format`. 없으면 1.
3. 색인: 지금처럼 `SCHEMA_VERSION`, 바뀌면 다시 만든다(마이그레이션 없음).

언제 올리나(openJiuwen 규칙):
- 선택 키를 더하는 것은 올리지 않는다. 모르는 키는 지금처럼 보존한다.
- 있던 키의 뜻이나 문법(status 문법, 절 메타 줄, 키 이름)이 바뀔 때만 올린다.

읽기:
- coderag 는 지원하는 모든 형식을 그 형식대로 읽는다(형식마다 읽는 함수). 원문을 고치지 않고도 옛 문서가 계속 검색된다.
- 지원 범위보다 새 형식이면 경고하고 제목·설명만 색인한다(뜻을 추측하지 않는다).
- 새로 쓴 frontmatter 에 `format` 이 없으면 lint 가 알린다(Write 때만, 옛 문서는 알리지 않는다).

마이그레이션(Cognee 단계 목록):
- `coderag migrate [--to N] [--dry-run]`. 단계는 덧붙이기만 하는 목록(이름, from→to)이고 각 단계는 여러 번 돌려도 같은 결과다. 한 번 내보낸 단계는 고치지 않는다.
- 다시 쓰는 것은 status 가 active 인 살아 있는 문서(`plan/`, `base/`, `research/`, 팩 references)뿐이다. active 가 아닌 문서, `archive/`, 스냅샷(`audit/`, `handoff/`, `sessions/`)은 읽기만 한다(그때의 원문을 남기는 규약).
- `--dry-run` 은 git diff 형태로 보여 준다. 쓰는 것은 사람이 본 뒤, 커밋은 그 저장소의 일.
- 모르는 단계 이름이나 형식을 만나면 경고하고 아무것도 바꾸지 않는다.

doctor: 지원 범위 밖 형식, 선언 없이 새 문법, 마이그레이션 대기 문서 수, 팩·프로젝트 설정 형식.

## 4. L0/L1/L2 단계 공개
정의(결정적, LLM 없음):
- L0: 문서 한 줄 = 경로:줄, 제목, kind·status, `description`. 지금 search 결과와 같다.
- L1: 문서의 절 목록 = 절 제목, 줄 범위, 첫 문장(또는 절 메타 요약). 질의에 맞은 절에 표시.
- L2: 맞은 절의 본문(원문에서 읽음).

출력: `coderag search <질의> --level auto --budget <토큰>`
- 모든 결과를 L0 로 낸다. 남은 예산 안에서 위에서부터 L1 로, 첫 한두 결과는 맞은 절을 L2 로 펼친다. 같은 문서의 절은 문서 하나로 묶는다(memU 의 절→문서 올림).
- 토큰은 글자 수로 어림한다. 한국어와 영어의 비율이 달라 실측해 정한다.
- `--level 0|1|2` 로 고정할 수도 있다. MCP 도구(데몬 단계)는 같은 인자를 받는다.

compact 뒤 가리킴(M6 보강, AgentMemory 선례): 항목마다 L0 한 줄(제목 — 설명 앞부분 — 경로), 개수 상한 20에 더해 글자 상한(예: 2,000자). 넘치면 최근 것부터 남기고 "나머지 N개" 한 줄.

## 5. 단계와 측정
1. 형식 1 고정: 지금 규약 문서에 "형식 1" 한 줄, 매니페스트·설정의 `format` 읽기, doctor 검사. 측정: 기존 테스트 그대로 통과.
2. L0/L1/L2 와 `--level auto --budget`. 측정: audit/39 의 12문항에서 hit@5 와 결과 바이트, 예산별 정답 절이 L2 로 펼쳐지는 비율.
3. M6 가리킴 상한과 L0 한 줄. 측정: 주입 글자 수.
4. 형식 2가 실제로 필요해질 때 첫 마이그레이션 단계와 `migrate`. 그 전에는 만들지 않는다.

## 6. 사용자 결정 (2026-11-12)
1. 키 이름: `format:`(추천안, 따로 말씀이 없어 그대로).
2. "format 늘 적는 편으로 두자": 새로 만드는 frontmatter 에는 늘 적는다. 옛 문서는 채우지 않는다.
3. "자동 펼침의 경우 실측부터 하는거 동의": `--level auto` 를 옵션으로 넣고 실측 뒤 기본값을 정한다.
4. "상태가 archive 거나 해서, 액티브 아니면 마이그레이션 안 하는것도 괜찮은것 같음": active 문서만 다시 쓴다.
