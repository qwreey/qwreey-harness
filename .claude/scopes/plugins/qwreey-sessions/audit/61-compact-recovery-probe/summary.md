---
format: 1
title: 61. compact 뒤 원문·식별자 복원 실측
description: 긴 구간(346k~568k)에서 CC compact 위에 사용자 원문·식별자 목록·복구 경로(A+B+C)를 주입하면 정답 26/27(96%), 지금 qwreey-sessions 21/27(78%), CC 만 17/27(63%) (칸당 1회). 158k 구간은 셋 다 만점. A+B 를 SessionStart(compact)에 넣고, C 는 CC 가 이미 경로를 주므로 JSONL 검색 요령 한 줄만 둔다
---
# 61. compact 뒤 원문·식별자 복원 실측

> Snapshot 2026-11-16. May differ from now; check current files and git log before relying on it.

사용자 결정(패널 D3 "compact 뒤 사용자 원문·식별자 목록 복원을 실측해 볼까?" → "a) 실측부터"). 서브에이전트(opus)가 재고 메인이 이 기록을 썼다. 원자료 `/tmp/compactprobe/`(커밋 안 함).

## 설정
- 질문: CC 자체 compact 뒤에 (A) 요약된 구간의 사용자 발화 원문, (B) 기계로 뽑은 식별자(바뀐 파일, 커밋, 오류 첫 줄, id), (C) 복구 경로(트랜스크립트 경로와 찾는 법)를 다시 넣으면 그 구간 질문에 더 잘 답하는가. 비교 근거는 hermes 자체 압축기 +22.5pt(audit 59).
- 대상: 메인 세션 `c9a9e895` 의 실제 compact 구간을 /tmp 사본으로 잘라 씀. S1 7101~7483(158k 토큰), L1 7101~8464(346k), L2 15849~17873(424k), L3 17873~20445(568k). L1~L3 은 그 세션이 실제로 compact 한 구간이다.
- 질문: 구간 앞쪽(약 100k 토큰 안)에 대해 9~10개. 커밋 해시, 파일 경로, 오류(workspace-gate 의 tbox 차단), 수치, 사용자 원문, 버린 방안(MessageDisplay). T2q10 은 같은 구간 뒤에서 결정이 바뀌어 모호하므로 뺐다.
- 갈래: 0 = CC compact 만. 1 = 지금 qwreey-sessions(`--plugin-dir`, 임시 `SESSION_LOG_HOME`, compact 전에 동기 flush 로 기록을 만들어 둠, PreCompact 지시·상기와 SessionStart(compact) 가리킴). 2 = 1 + A+B+C(SessionStart `hook_additional_context` 첨부를 덧붙임; 훅 출력이 실제로 저장되는 꼴과 같음을 먼저 확인). 3 = 0 + A+B+C(S1 만).
- 실행: claude 2.1.316, sonnet. 임시 `CLAUDE_CONFIG_DIR`(credentials 와 트랜스크립트만)에서 `claude -p --resume <sid> "/compact"`. 답은 `--fork-session --tools Read,Grep --max-turns 14`, 갈래마다 같은 `--add-dir`. 채점은 정확 문자열 키와 자유 응답 수동 확인(갈래를 알고 봄; judge 는 예산 때문에 생략).
- 비용: compact 8회 USD 5.99(구간 토큰 x 약 $2/M, 회당 0.34~1.10) + 시험 compact 약 0.36 + haiku flush 0.11 + 답 23회 3.23 = 약 USD 9.69.

## 결과
| 구간 | 0 CC 만 | 1 지금 sessions | 2 + A+B+C | 3 0 + A+B+C |
|---|---|---|---|---|
| S1 158k (3회) | 9,9,9 | 9,9,9 | 9,9,9 | 9,9,9 |
| L1 346k | 9, 9 | 7, 9 | 9 | - |
| L2 424k (/9) | 5 | 5 | 8 | - |
| L3 568k | 3 | 9 | 9* | - |

\* L3 갈래 2 의 Q7 은 `-p` 에서 `--add-dir` 밖 Grep 이 허용되어 저장소 문서를 읽었을 수 있다(빼면 8/8).

- 긴 구간 합(1회차): 0 = 17/27(63%), 1 = 21/27(78%), 2 = 26/27(96%).
- L2 갈래 2 는 도구 없이 주입 글만으로 오류(workspace-gate, tbox), 경로(`registry.tsv`), 사용자 원문을 맞혔다. 0·1 은 셋 다 "모름".
- L3 은 갈래 1·2 가 트랜스크립트를 뒤져(각 17회, 9회) 다 맞혔다. 갈래 0 은 Grep 한 번에 "[Omitted long matching line]"(JSONL 줄이 길다)을 받고 멈췄다. 1·2 는 `[^"]{0,120}` 처럼 길이를 묶은 패턴을 썼다.
- 어느 갈래도 못 맞힌 것: 커밋 당시 q 버전(0.8.12). 에이전트 응답에만 있었고 뒤에 버전이 바뀌었다.
- 지금 PreCompact 요약 지시의 효과는 보이지 않았다(L2 0=1, L1 1회차는 1 이 낮음).
- 주입 크기: 갈래 2 의 A+B+C 는 6,951~8,699자(S1 2,608자)로 10,000자 아래. 갈래 1 의 SessionStart(compact) 는 804자, PreCompact 상기는 약 1.5~2.5k자(요약기에게 감). CC 요약 본문은 13~27k자.
- CC 2.1.316 compact 요약 끝에 이미 "If you need specific details from before compaction … read the full transcript at: <경로>" 가 붙고, 마지막 메시지 몇 개를 그대로 남긴다. 그래서 C 의 경로 자체는 이미 있다.

## 결론
- 158k 구간에서는 CC 요약만으로 충분하다(모든 갈래 만점).
- 실제 compact 크기(350k~570k)에서는 A+B 가 바늘 질문(오류, 경로, 원문)을 도구 없이 살리고, 전체로 CC 만 대비 +33pt 다. hermes(+22.5pt)와 방향이 같다. 다만 칸당 1회라 크기는 믿지 못한다.
- 지금 qwreey-sessions 주입(기록 가리킴, PreCompact 지시)은 바늘 질문에서 CC 만과 비슷하다. L3 의 이득은 트랜스크립트 검색에서 왔다.

## 권고
- qwreey-sessions SessionStart(compact) 출력에 A+B 를 넣는다. 지금의 804자 가리킴과 합쳐 약 8,000자 이하.
  - A 가 먼저: 요약된 구간의 사용자 발화 원문. 큐 중복 제거, task-notification·local-command 제외, 붙여넣은 블록은 상한 안에서.
  - 다음 B: 오류 첫 줄, 바뀐 파일, 커밋과 첫 줄, id.
  - 뽑아 낸 글도 `redact.py` 를 거친다.
- C 는 경로를 다시 주지 말고 검색 요령 한 줄만 둔다: JSONL 줄이 길어 Grep 이 생략하므로 `.{0,120}` 같은 묶은 패턴이나 `-o`, 찾은 뒤 offset/limit 로 Read.
- PreCompact 요약 지시는 이번 측정에서 효과가 보이지 않았다. 지울지는 따로 정한다.
- 출시 전에 확인을 원하면 L2·L3 의 갈래 0·2 를 2회 더(compact 재사용, 약 USD 1~1.5).

## 한계
- 칸당 1회(L1 의 0·1 만 2회), 갈래·구간당 compact 표본 1개. 실제 세션의 compact 모델은 opus, 여기서는 sonnet.
- 채점은 갈래를 알고 했다. judge 는 생략.
- L3 갈래 2 에서 저장소 누수 가능성(Q7).
- B 는 메인 세션의 도구 호출만 본다: 서브에이전트가 고친 파일은 빠진다. 커밋 목록은 예산에서 잘린다(L2 "+21 more").
- 갈래 3(CC 만 + A+B+C)은 짧은 구간에서만 쟀다.
