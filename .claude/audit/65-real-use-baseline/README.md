---
format: 1
title: 65. 실사용 전 기준선 (2026-11-12 ~ 11-19, 하네스 개발 주간)
description: rules-inject 가 주에 712k 글자로 가장 많이 싣고, bash-bypass-reminder 가 584번(warn 442) 가장 자주 말함; Bash 한 번에 훅 18개, 체감 지연 약 140 ms; 세션 시작 상시 주입 p50 6.1k 글자
---

> Snapshot 2026-11-19. May differ from now; check current files and git log before relying on it.

다음 주(11-23~) 실사용과 비교할 기준선. 이 주는 하네스 자체를 만든 주라(메인 7세션, 서브에이전트 204, 거의 qwreey-harness 와 coderag) 평소 작업과 모양이 다르다. 비교할 때 그 점을 뺀다.

- 다시 재기: `python3 -I tools/usage-report.py --since 2026-11-12 --until 2026-11-19` (트랜스크립트가 남아 있을 때만), `python3 -I tools/usage-report.py --time-hooks --runs 3`.
- 전체 출력: [report-2026-11-19.md](report-2026-11-19.md), [hook-timing-2026-11-19.md](hook-timing-2026-11-19.md). 이름과 숫자만 들어 있다.

## 눈에 띄는 것
1. **rules-inject(qwreey-conventions)가 가장 많이 싣는다.** 204번, 711,998 글자(약 285k 토큰), 한 번에 p50 1,838 / 최대 8,580 글자. 대부분 서브에이전트가 처음 파일을 만질 때.
2. **bash-bypass-reminder 가 가장 자주 말한다.** 584번, 그중 warn 442. 셸로 파일을 고칠 때마다 뜬다(이 주는 스크립트 편집이 많았다). 실사용에서도 이 비율이면 소음 후보.
3. **도구 한 번의 훅 비용**(표본 실행, 조용한 경우): Bash 는 Pre 9개, Post 7개, Batch 2개. 같은 이벤트의 훅은 동시에 돌아 체감은 이벤트마다 가장 느린 것(약 46+49+41 ms), CPU 합은 약 530 ms. Edit 는 Post 11개(CPU 330 ms, 체감 48 ms). python 시작만 11 ms.
4. **세션 시작이 무겁다.** 상시 주입 p50 6,095 / 최대 6,857 글자(operator 1,905, q 1,066, session-log 970, workspace 718, advisor 562). `q:drift.py` 가 SessionStart 에서 p50 843 ms.
5. **서브에이전트 시작 주입** p50 963 / 최대 2,749 글자(q 906, workspace 386, operator 292).
6. **거부**: workspace-gate 43(Bash 40), auditor-readonly-guard 18, heavy-proc-guard 16, session-log Read 2. 옛 claude-doctor 설치의 없는 스크립트 때문에 난 오류 8 은 이름 바꾸기 전 일이다.
7. **서브에이전트**: general-purpose opus 118(출력 7.10M), sonnet 71(2.64M), 모두 백그라운드.

## 실사용 주간에 볼 것
- 위 1, 2 의 횟수와 글자 수가 평소 작업에서도 이만큼인가. 사용자가 거슬린다고 한 알림과 겹치는가.
- 세션 시작 6k 글자 중 줄일 수 있는 것(operator 가 가장 큼).
- `q:drift.py` 0.85 초가 체감되는가.
- coderag: 범위 검색 `--for` 없이 잡음이 나는가(coderag `.claude/plan/todo.md` 4절), doc-locator 출력 크기.

## 재는 법의 한계
- 아무것도 찍지 않은 훅은 트랜스크립트에 남지 않는다(Stop 만 `stop_hook_summary` 에 모두 남음). 그 시간은 `--time-hooks` 표본으로만 본다. 표본 저장소에는 기록과 `coderag.toml` 이 없어 아래 한계에 가깝다.
- UserPromptSubmit 훅은 실행 시간이 기록되지 않는다.
- 거부 글은 모델이 본 글로 셌고, systemMessage(사용자에게만 보이는 줄)는 모델 쪽 합계에서 뺐다.
