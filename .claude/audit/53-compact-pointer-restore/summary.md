---
format: 1
title: 53. compact 뒤 가리킴(coderag-recall) 실측과 스킬 복원 예산
description: 가리킴 유무와 무관하게 필요할 때 다시 읽음(가리킴 4/4, 대조 4/4), 불필요할 때 0/11. CC 2.1.316 은 읽은 파일 5개를 mtime 순으로 되살리고 요약이 경로를 남긴다. 스킬 예산 밀려남 0/37, coderag get 읽기는 원장에 안 남음
---
# 53. compact 뒤 가리킴(coderag-recall) 실측과 스킬 복원 예산

> Snapshot 2026-11-16. May differ from now; check current files and git log before relying on it.

claude 2.1.316, sonnet, `claude -p --input-format stream-json` 한 프로세스에 턴을 차례로 보내고 `/compact` 를 턴으로 보냄(한꺼번에 넣으면 큐가 턴을 합친다). 임시 `CLAUDE_CONFIG_DIR`(플러그인은 `--plugin-dir` 의 probe 훅과 luau-kb 만; luau-kb 는 `defaultEnabled:false` 라 임시 settings 의 `enabledPlugins["luau-kb@inline"]` 가 있어야 스킬이 뜬다), 임시 `CODERAG_HOME`, coderag 새 release 빌드. 서브에이전트(opus)가 측정하고 메인이 이 요약을 썼다. 원자료 `/tmp/cpr/`(커밋 안 함). 모델 비용 합계 USD 3.62.

## 질문
`.claude/audit/41-knowledge-packs-debate/synthesis.md` "열린 문제: compact 뒤 복원" 의 두 확인 거리. (a) 가리킴만 받은 에이전트가 필요할 때 다시 읽고 필요 없을 때 안 읽는가. (b) 팩 스킬 본문이 25,000토큰 복원 예산에서 동작 스킬을 얼마나 밀어내나.

## 1. `hook session-start` 출력(모델 호출 없음)
- 원장 `state/used/<sid>.c<회차>` 에 Read(팩 안 .md)와 Skill(팩 스킬)이 한 줄씩 쌓이고 팩 밖 Read 는 기록하지 않는다. `source=compact` 에서만 `coderag-recall` 블록을 내고 resume, 서브에이전트는 출력 없음. 두 번째 PreCompact 에서 OMIT 줄. 모두 설계(coderag `.claude/base/layers-and-packs.md` §13.3)대로.
- 항목 한 줄 약 250~300자. 잔흠: offset 으로 읽은 절은 `§ §2 ...` 처럼 § 가 두 번 찍힌다. `coderag get`(Bash)로 읽은 문서는 원장에 남지 않는다.

## 2. CC 2.1.316 이 compact 뒤에 스스로 붙이는 것 (설계 전제와 다름)
- 읽은 파일을 되살린다: compact 직후 파일 전체를 디스크에서 다시 읽어 붙인다(Read 가 `limit 5` 였어도 전체). 큰 파일(12.5KB, 21KB)은 내용 대신 "too large to include. Use Read tool if you need to access it." 참조(6.7K자 파일은 전체).
- 최대 5개, 읽은 순서가 아니라 파일 mtime 이 새 것부터(1회 관찰). 실제 세션 compact 136회 중 105회가 5개로 꽉 찼다. 이번 세션에서 고치거나 만든 파일이 우선이라 읽기만 하는 팩 문서는 실제 세션에서 거의 밀려난다.
- 요약이 읽은 파일 경로를 남긴다: 11/11 회. `/compact <문서·경로를 빼라>` 지시도 무시했다.
- 스킬 복원(`invoked_skills`): 스킬당 상한은 문자/4 추정(update-config 가 4개 세션에서 정확히 20,000자). dataviz + luau-kb 12개 49,901자를 모두 붙였다. 실제 토큰은 약 41k(한국어 본문은 추정의 약 3배). 예산 25,000 "토큰" 은 실제로 약 100k자까지 받는다.

## 3. (a) 가리킴 탐침
흐름: T1 에서 `src/Search.luau` 를 고치며 luau-kb strings.md 를 Read, T2 프로젝트 파일 6개 검토(파일 복원 슬롯을 채움), `/compact`, (ii) 문서가 필요 없는 작업, (i) strings.md §4 의 수치(0.742 native 47.7배)가 필요한 작업. P = 가리킴, C = 대조, S = 대조 + 스킬 호출(CC 본문 복원).

| 변형 | (i) 문구 | P | C | S |
|---|---|---|---|---|
| a: 문서 전체 읽음 | "per our measured data ... factor" | 다시 읽음, 정답(strings.md 바로 Grep) | 다시 읽음, 정답(팩 전체 Grep) | - |
| b: §2 만 읽음 | "If we have measurements, cite them" | 다시 읽음, 정답 | 다시 읽음, 정답(bench 까지 Grep) | 다시 읽음, 정답 |
| c: b 와 같음 x2 | 힌트 없음 | 0/2 | 0/2 | - |
| d: b + 문서 빼라 지시(무시됨) | b 와 같음 | 다시 읽음, 정답 | 다시 읽음, 약 47 | - |

- 필요할 때: P 4/4, C 4/4, S 1/1. 차이는 찾는 경로뿐(P·S 는 그 파일, C 는 팩 전체).
- 힌트 없으면 양쪽 0/2. 불필요할 때 다시 읽음 0/11.
- "가리킴만 받은" 조건은 만들지 못했다: 요약이 늘 경로를 남긴다.

## 4. (b) 실제 트랜스크립트 (읽기만, 메인 대화 359개)
- luau-kb 스킬을 부른 세션 47개는 모두 `/tmp` 탐침이고 compact 0회.
- compact 136회 중 스킬 복원이 있는 37회: 복원 본문 최대 29,301자, 예산에 닿은 적 없음, 예산 때문에 빠진 스킬 0회.
- 첨부에 없던 스킬: code-review(늘), qwreey-advisor:fresh-advisor, q:away·q:back. 예산이 아닌 다른 규칙(원인 미확인).

## 판단
- 설계 전제 "Read 로 연 references 는 되살리지 않는다" 는 2.1.316 에서 틀렸다. "팩 문서는 mtime 이 오래돼 대개 되살아나지 않는다" 로 고쳐 쓰면 맞다(coderag §13.3, 사용자 승인 뒤).
- 가리킴은 해가 없다(항목당 약 300자, 불필요한 다시 읽기 0/11). 이번 탐침에서 이득은 찾는 경로가 짧아진 것뿐이고, CC 요약의 경로와 스킬 목록이 같은 일을 한다.
- 가리킴이 이길 수 있는 자리는 측정 못 함: 요약이 경로를 잃는 긴 세션, 여러 팩 문서, CC 복원이 없는 codex·agy. 더 큰 빈틈: coderag 가 권하는 읽기 경로(`coderag get`)가 원장에 안 남는다.
- (b) 밀어내기는 지금 크기에선 일어나지 않는다. SKILL.md 를 줄일 이유는 실비용(compact 마다 한국어 본문이 추정의 약 3배 토큰)이다.

## 남은 측정
- 실제 장시간 세션(auto compact)에서의 다시 읽기, 칸마다 n=1~2, opus 메인.
- 파일 복원 크기 경계, mtime 순서(1회 관찰).
- code-review·fresh-advisor 가 스킬 복원에서 빠지는 규칙, 서브에이전트 트랜스크립트(1,459개) 미스캔.
