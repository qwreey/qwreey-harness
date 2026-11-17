---
format: 1
title: 64. PLAN.md 대안 조사
description: 큰 markdown 계획 하나에 결과를 덧붙이는 방식은 모든 형제 저장소에서 자라고 낡는다; 외부 사례(beads, Backlog.md, Spec Kit, ExecPlan, Anthropic 하네스)는 상태를 항목 단위로 닫고 경과는 git 에 맡긴다; 권고는 PLAN.md 를 수명별로 나누고 desk 결정·계획을 .claude/plan 항목 파일로 뒷받침
---
# 64. PLAN.md 대안 조사

> Snapshot 2026-11-17. May differ from now; check current files and git log before relying on it.

사용자: "PLAN.md 는 좀 큰 문제라 생각해. markdown 이 뭐 복제성은 좋지만 도구가 붙던가 해야할 수도. 리마인더가 최소한이라도 필요해. 거의 항상 stale 이 되기도 하고 늘 불어난다는것도 문제야. 사람이 읽기도 어렵고. 이건 모든 프로젝트에서 같게 발견되는 문제더라고." 서브에이전트(opus)가 조사하고 메인이 결정 id 와 desk 저장소 크기를 다시 확인해 기록했다.

## 실측
- PLAN.md: 248줄, 45,659 B, 400자 넘는 줄 14개. §3.9 가 본문의 56%(15.7k자, 5단계 중첩 날짜·인용 로그).
- PLAN.md 커밋: 11-10 3, 11-11 8, 11-12 25, 11-13 16, 11-16 5, 11-17 0. 저장소 7일 커밋 366개.
- 계획의 실제 자리가 desk 로 옮겨감: transcript 기준 11-10..11-16 세션은 PLAN.md 언급 도구 호출 47회, desk 23회; 11-16..11-17 세션은 PLAN.md 0회, desk 144회. desk 저장소(`/code/.claude/plugins/store/qwreey-desk_inline-*.json`, 73.9 KB, git 밖)에 결정 16, 단계 4, 로그 109건.
- 결정 id: 커밋 메시지가 desk id D4~D16 을 인용하지만 git 안에는 세션 반입본의 답 줄만 있고 질문·선택지·맥락은 없다. `base/decisions/D-01`~`D-13` 과 이름 공간이 겹친다("D13 a" 가 어느 쪽인지 글만으로 모름).
- 낡은 본문: §1 의 전역 CLAUDE.md 40줄 목표(전역 CLAUDE.md 는 없앰, `plugins/q/skills/doctor/references/load-and-rules.md:21` 이 인용), luau-kb `.lsp.json`(luau-lsp 로 분리됨). §2 단계 표에 상태 열이 없다.
- `.claude/base/decisions/D-07-finished-todos.md` 안 B("상시 로드 아님이면 형식 자유")는 PLAN.md 의 성장을 막지 못했다. `records_check.py` 크기 한도(200 KB)는 `.claude/` 아래만 보고, 루트 PLAN.md 는 대상이 아니다.
- 형제 저장소: quad ROADMAP 39 KB(09-07 archive 이동 뒤 다시 자람), HUMAN_TODO 67 KB, `base/*-plan.md` 최대 347 KB; table-sim `.claude/todos.md` 40.6 KB(42% 가 끝난 것); devplorer todos 16.6 KB; coderag `plan/todo.md` 15.4 KB(끝난 46, 열린 44); claude-doctor HUMAN_TODO 23 KB.

## 외부 사례
| 방식 | 모양 | 낡음과 성장 | 비고 |
|---|---|---|---|
| beads (`bd`) | Dolt DB, `.beads/issues.jsonl` 내보내기, 의존 그래프 | close, ready, 닫힌 것 compaction | 저자가 낡은 markdown plan 605개를 계기로 만듦; DB 라 diff 어려움 |
| Backlog.md | 작업마다 md 파일 | archive, cleanup | CLI·MCP, 웹 칸반 |
| Taskmaster | tasks.json 한 파일 | 상태 필드 | 브랜치 충돌(#1132), 태그 깨짐(#477) |
| Spec Kit, Kiro | 기능마다 spec, plan, tasks | 수동 동기화 | 전체 그림 없음, 낡은 spec 을 확신 있게 따름 |
| OpenAI ExecPlan | 큰 변경마다 자족 문서(Progress, Decision Log, Retrospective) | 끝나면 회고로 닫음 | |
| Anthropic 장기 하네스 | feature_list.json 의 passes, progress 파일, git log | 상태는 JSON, 경과는 git | "JSON 은 markdown 보다 덜 덮어써진다" |
| Claude Code Tasks | `~/.claude/tasks`, git 밖 | 세션 단위 | 2.1.268 이상은 옛 모델에만 기본 제공 |
| ADR/MADR | 결정마다 파일, superseded by | 대체 관계 | 우리 `base/decisions` 와 같은 꼴 |

공통점: 상태(열림, 닫힘, 막힘)는 항목 단위로 기계가 읽게 두고 닫거나 옮긴다. 설명은 markdown, 경과는 git log. 에이전트가 스스로 문서를 갱신하리라 기대하지 않고 갱신을 도구 호출의 부산물로 만든다(desk 144 대 PLAN.md 0 과 같은 현상).

출처: github.com/steveyegge/beads, yegge-ai.pages.dev/listings/introducing-beads-a-coding-agent-memory-system, gascity.com/guide/when-markdown-todos-stop-working, github.com/MrLesk/Backlog.md, docs.task-master.dev, kiro.dev/docs/specs, developers.openai.com/cookbook/articles/codex_exec_plans, anthropic.com/engineering/effective-harnesses-for-long-running-agents, code.claude.com/docs/en/agent-sdk/todo-tracking.md, adr.github.io/madr.

## 진단
PLAN.md 에 수명이 다른 다섯 가지가 섞였다: 목표와 구조(약 2.7k자), 확정 결정과 원칙(10k+), 실행 결과 로그(8k+), 열린 질문, 다음 단계. 실행 로그가 앞의 둘을 덮어 읽기 어렵고, 열린 질문과 다음 단계는 desk 로 갔지만 git 에 남지 않아 진실이 둘이 됐다.

## 선택지
- A 최소: PLAN.md 를 `archive/plan/` 으로 옮기고 짧게 다시 씀(8 KB 이하, 긴 줄 0). 결정은 `base/decisions` 새 D-xx 로, 목표는 README 나 `base/overview.md` 로, 실행 로그는 옮기지 않음(archive 와 git). 크기와 "마지막 갱신 뒤 커밋 N개" info 알림. D-07 기준 보강, desk id 접두 분리.
- B 권고: desk 결정과 단계를 항목마다 `.claude/plan/` 파일(coderag living record)로 쓰고, 답하면 landed 로 archive 하거나 `base/decisions` 로 승격. PLAN.md 는 짧은 목표와 생성 목록. desk 저장 형식 마이그레이션이 필요하고, 동시 세션 충돌은 git 충돌로 바뀜(항목마다 파일이라 범위 작음). 비프로그래머는 패널로만 다루고 결과는 저장소 웹에서 읽음.
- C: Backlog.md(웹 칸반이 장점, records 규약과 desk 와 겹침). beads, Taskmaster, Claude Code Tasks, Linear 는 조건에 맞지 않음.

## 판정 측정
- 지표: 정본 크기와 긴 줄 수, 마지막 갱신 뒤 커밋 수, 커밋이 인용한 결정 id 중 git 기록으로 풀리는 비율(지금 0%), 세션별 PLAN 대 desk 사용 비.
- 실험(승인 뒤): 저장소만 보는 새 에이전트가 "다음 할 일", "열린 결정", "X 는 왜" 다섯 질문에 답하는 정답률과 읽은 토큰을 전후로 잰다.
