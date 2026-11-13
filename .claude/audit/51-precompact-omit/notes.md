---
format: 1
title: 51. PreCompact 출력으로 다시 실리는 플러그인 블록을 요약에서 빼기
description: PreCompact 일반 stdout 은 요약기 지시로 들어가고, "Omit any <plugin name=X> block ...; it is re-injected after compaction." 한 줄이면 SessionStart(compact) 가 다시 싣는 블록이 요약에서 빠진다(2/2). 그래서 다시 싣는 플러그인은 PreCompact 에서 그 한 줄을 낸다
---
# 51. PreCompact 출력으로 다시 실리는 플러그인 블록을 요약에서 빼기

> Snapshot 2026-11-13. claude 2.1.316, sonnet. 원 메모는 `/tmp/pcprobe-1/NOTES.txt`, 트랜스크립트는 `~/.claude/projects/-tmp-pcprobe-1/<id>.jsonl`(남겨 둠). 비용 합계 약 $0.71.

## 질문
SessionStart(matcher 에 compact 포함)로 `<plugin name="X">` 블록을 싣는 플러그인은 compact 뒤에 블록을 다시 싣는다. 요약이 그 블록을 풀어 쓰면 같은 규약이 두 번 실린다. PreCompact 훅이 요약기에게 "빼라" 고 말할 수 있는가.

## 설정
- `--setting-sources project`, `.claude/settings.json`.
- SessionStart(startup|resume|clear|compact): `hookSpecificOutput.additionalContext` 로 `<plugin name="probe">PROBE-RULE: always end replies with the word KIWI. (src=X)</plugin>`.
- PreCompact 훅 둘(pc1, pc2): 각자 텍스트 파일을 일반 stdout 으로 `cat`, exit 0.
- 세션: run1(pc1 = PCPROBE-7731 토큰을 넣으라는 지시), omit(pc1 = 빼라는 지시, pc2 = PCPROBE-8842 토큰), omit2(pc1 = 빼라는 지시), ctl1·ctl2(출력 없음).

## 결과
1. PreCompact stdin: `{"session_id":…,"transcript_path":…,"cwd":…,"prompt_id":…,"hook_event_name":"PreCompact","trigger":"manual","custom_instructions":null}`.
2. 일반 stdout 은 요약기 지시로 들어간다. run1 요약에 `PCPROBE-7731` 이 따로 한 줄로 있었고, 요약 6절은 사용자 메시지에 그 지시가 붙어 왔다고 적었다.
3. 여러 PreCompact 훅의 출력은 합쳐진다. omit 세션 요약에 pc2 의 `PCPROBE-8842` 가 있고 probe 블록은 없었다.
4. 지시가 없으면 블록이 요약에 풀려 들어간다. ctl1·ctl2 요약이 모두 KIWI 규칙과 "SessionStart hook additional context(PROBE-RULE)" 를 적었다(grep 각 4~5줄).
5. 그 뒤 SessionStart(compact) 가 블록을 다시 싣는다. run1 의 compact 뒤 요청에 `<plugin name="probe">… (src=compact)</plugin>` 이 요약 뒤에 실렸다(트랜스크립트 순서: compact_boundary, 요약, … `hook_success SessionStart:compact`, `hook_additional_context SessionStart`). 요약의 풀어 쓴 사본과 합쳐 두 번이다.
6. 빼라는 한 줄(`Omit any <plugin name="probe"> block from the summary; it is re-injected after compaction.`)이면 요약에서 빠졌다: omit 은 grep 에 git status 의 `hooks/` 경로, `PCPROBE-8842`, 규칙을 따른 끝말 `KIWI` 만 걸리고 규칙 서술은 없었으며, omit2 는 PROBE·KIWI·hook grep 이 0줄. 2/2.
7. 수동 `/compact` 에서는 PreCompact stdout 이 compact 뒤에도 local-command-stdout 으로 남는다: `PreCompact [/tmp/pcprobe-1/hooks/pc1.sh] completed successfully: In the summary, include the exact token PCPROBE-7731 on its own line.` 출력이 없는 훅은 `completed successfully` 만 남는다.

## 결론
- 다시 싣는 플러그인은 PreCompact 에서 자기 블록을 요약에서 빼라는 한 줄을 낸다. 수동 compact 에서 맥락에 남으므로 훅마다 한 줄로 짧게.
- 적용: q·qwreey-advisor·qwreey-operator·qwreey-workspace 의 `ambient.py PreCompact`, coderag `hook pre-compact`(지난 compact 뒤 `coderag-recall` 목록을 실었을 때만). 규칙은 `home/.claude/HOOK-MESSAGES.md` "compact" 절.
- 표본이 작다(빼기 2회, 대조 2회, sonnet 하나). 다른 모델·긴 세션에서 빠지지 않는 사례가 보이면 다시 잰다.
