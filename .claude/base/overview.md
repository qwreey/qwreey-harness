---
format: 1
title: qwreey-harness 개요(목표와 구조)
description: qwreey-harness 의 목표(공통 지식을 상시 로드 문서에서 켜고 끄는 플러그인·팩·기록으로)와 지금 구조: 세 층(사용자 home/, 플러그인·팩, 프로젝트), 저장소 배치, 상시 로드 목표
status: active
---

# qwreey-harness 개요

원칙과 사용자 결정은 [harness-principles.md](harness-principles.md), 지금 할 일과 열린 질문은 루트 `PLAN.md`.

## 목표
- 출발점(2026-11-10, `.claude/audit/01`~`06`): 지식이 각 프로젝트의 상시 로드 문서에만 쌓여 세션마다 수십 KB를 썼고(quad 약 28~31k 토큰, table-sim 73.6KB), 저장소 사이 지식은 복사한 뒤 갈라지는 식으로만 옮겨졌다.
- 목표: 여러 저장소가 함께 쓰는 지식은 켜고 끌 수 있는 플러그인과 도메인 팩으로, 프로젝트 고유한 것만 그 프로젝트에, 이유와 근거는 기록(`.claude/`)으로 둔다.
- 특정 언어나 sandbox 에 묶이지 않는다. 툴킷(luau, web)은 자리만 갖는다. 플러그인은 설치본만으로 돌고 설정은 각자 `/config` 옵션이며, `harness.env` 는 저장소 층과 튜닝용 선택 파일이다.
- 이 저장소는 사용자의 Claude 관련 지식과 플러그인을 모은 곳이다(사용자: "claude conf 같은 느낌…결국 내 오피니언임"). 나중에 공개할 수 있고, 동료에게는 플러그인 단위로 골라 설치하게 배포한다.

## 세 층
1. 사용자 레벨 `~/.claude`: 정본은 `home/`, 관리 목록은 `home/MANIFEST`(harness.env, lib/harness_env.py, statusline). settings.json 은 복사하지 않고 `home/settings-migrations/` 마이그레이션으로 반영한다. 전역 CLAUDE.md, 사용자 레벨 rules, 사용자 레벨 훅은 두지 않는다. 상시 규약과 훅은 플러그인이 싣는다.
2. 플러그인과 팩: 마켓 `.claude-plugin/marketplace.json`(`qwreey-harness`).
   - `plugins/`: `q`(사람이 치는 명령), `qwreey-*`(sessions, workspace, operator, delegate, debate, advisor, conventions, reply-language, proc-guard, desk, license), `luau-lsp`. 저자는 로컬 폴더 마켓으로 저장소에서 바로 싣고, 동료는 GitHub 마켓에서 설치본을 받는다.
   - `packs/`: 도메인 팩 `luau-kb`, `web-security`. 기본 꺼짐이고, 쓰는 저장소가 `coderag.toml` 의 `[[packs]]` 와 `coderag adapt --harness claude` 로 켠다. 팩 rule 주입은 coderag 플러그인이 한다. luau-kb 는 LSP 를 싣지 않는다(`plugins/luau-lsp`).
3. 프로젝트(각 저장소): CLAUDE.md 는 정체성, 넘지 않는 선, 빌드·검사 명령만. 경로 조건 rules, 프로젝트 고유 스킬, 기록 `.claude/`(import 하지 않음). 상시 로드되는 할 일 문서에서는 끝난 항목을 지운다(`.claude/base/decisions/D-07-finished-todos.md`).

## 상시 로드 목표
- 프로젝트 CLAUDE.md 80줄 이하. 우리 설치는 전역 CLAUDE.md 를 두지 않는다. 그래도 둔 사람에게 `/q:doctor` 는 40줄을 기준으로 알린다(`plugins/q/skills/doctor/scripts/scan.py` `USER_CLAUDE_GOAL`).
- 상시 로드 합계가 20KB 를 넘으면 `/q:doctor` 가 경고한다. 상시 문구 예산의 근거는 `.claude/audit/29-repo-audit-pass2-debate/verdict.md`.
- 상시 규약은 플러그인 주입(`lib/ambient.py`, 글은 `plugins/<p>/context/ambient.md`)이라 플러그인마다 끈다.

## 저장소 배치
- 소스: `home/`, `plugins/`, `packs/`, `lib/`(플러그인이 함께 쓰는 코드의 정본, 플러그인은 사본을 들고 `tools/sync-copies.py` 로 맞춤), `tools/`(home-sync, settings-migrate, sync-copies, 저장소 전체 테스트), `intake/`(외부 프로젝트 반입 자리).
- `plugins/` 와 `.claude-plugin/` 은 settings 의 마켓 경로가 가리키므로 옮기지 않는다. 훅 스크립트를 옮기거나 지우면 실행 중인 세션이 깨진다(저장소 `CLAUDE.md`).
- 기록: `.claude/`(`.claude/README.md`, 규약은 coderag `coderag:agent-records`). 플러그인·팩 하나에 관한 기록은 `.claude/scopes/<경로>/`.
- 사람용: `README.md`, 플러그인 README 카드, 사람이 할 일 `HUMAN_TODO.md`. 공개할 때는 `docs/` 를 따로 쓴다.

## 이웃 저장소
- coderag(`../coderag`): 기록 검색·낡음 검사·lint, 팩 rule 주입, 기록 규약 정본. 그쪽 할 일은 coderag `.claude/plan/todo.md`.
- 형제 Luau·웹 저장소(quad, stl-luau, table-sim, rbvm, tbox, devplorer, moonwave-luau, vitrine 등): 이 저장소에서는 읽기만 한다. 고칠 것은 `.claude/handoff/` 에 쓰고 전달은 사용자가 한다.
