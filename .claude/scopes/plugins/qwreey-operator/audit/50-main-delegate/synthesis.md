---
format: 1
title: 50. 메인 대화·서브에이전트 구현 규약 토론 종합
description: 큰 구현(코드 파일 3개+, 새 줄 150+, 많은 읽기)은 백그라운드 서브에이전트로, 근거는 비용보다 대화 유지와 fresh 맥락. 훅은 q 의 delegate-nudge info 하나(12회/8파일)와 다음 턴 이월 알림, 스킬은 사용자 판단
---
# 50. 메인 대화·서브에이전트 구현 규약 토론 종합

> Snapshot 2026-11-13. P(최소)와 Q(넓게) opus 의견서 1라운드를 메인 세션이 종합했다. 근거는 `.claude/scopes/plugins/qwreey-operator/research/drafts/main-delegate-evidence.md`.

## 두 쪽이 함께 받아들인 것
- 전역 `home/.claude/CLAUDE.md` Subagents 절에 위임 경계 문구를 넣는다. 지금 어느 저장소에도 구현 위임 규정이 없어, 지시 없이는 위임이 0 건이었다(stl-luau).
- 근거는 비용이 아니라 대화 유지와 fresh 맥락이다. 돈은 sonnet 으로 내릴 때만 준다(100줄당 메인 0.63, opus 서브 0.60, sonnet 서브 0.19 달러). 비용을 근거로 쓰면 opus 위임 남용을 정당화한다.
- 모델: 다 정해진 일은 sonnet, 설계 판단이 남았으면 opus.
- 메인이 할 일: 작은 수정, 방금 정한 결정 반영, 문서·설정, 중간에 사용자 답이 필요한 일(먼저 묻고 넘긴다), 지시문이 작업보다 큰 일.
- 훅은 q 플러그인 `delegate-nudge`. 위임 원장과 `subagent-slots.py`(PostToolUse `*`, 메인·서브 구분)가 q 에 있다. 메인(`agent_id` 없음)의 Edit/Write/MultiEdit/NotebookEdit 와 코드 경로에 쓰는 Bash(헤레독, `sed -i`, `>`)를 센다. Bash 를 빼면 메인 코딩이 1/10 로 덜 세진다. `.md .json .toml .yaml` 는 뺀다. 끄는 스위치를 둔다.
- 막지 않는다(deny 없음). 프롬프트 키워드로 구현 요청을 판별하는 선제 훅은 두지 않는다(한국어·비개발자 문장 오탐).
- 다른 벤더 위임(`delegate`, agy/codex)과 한 스킬로 섞지 않는다.

## 갈린 것과 종합안
| 쟁점 | P | Q | 종합 |
|---|---|---|---|
| 문구 틀 | 조건(3파일·150줄·많은 읽기)이면 넘김 | 기본은 넘김, 예외만 메인 | P 틀. 사용자가 경계한 남용을 문구가 직접 막는다 |
| 백그라운드 | 필수 조건으로 명시 | "기다리지 말고 대화 계속" | P. 전경 서브는 메인 코딩과 똑같이 사용자를 막는다 |
| 훅 문턱 | info 하나, 12회/8파일 | info 5/4, warn 10/6 | P. 5/4 는 오탐이 측정되지 않았고 8/5 도 약 50% |
| 카운터 리셋 | 사용자 입력·Agent 호출 | Agent 호출만(턴을 넘어 누적) | P 리셋에 Q 의 이월 알림을 더함 |
| 이월 알림 | 측정 먼저 | 직전 턴이 문턱을 넘고 위임 안 했으면 다음 프롬프트에 info 한 번 | 채택. "확인, 계속 진행" 으로 이어지는 누적을 오탐 거의 없이 잡는다 |
| 스킬 | 지금은 없음(설명 줄 상시 로드, 작은 일도 절차로 부풀림) | `q:implementer`(지시문, 모델, 도는 동안, 검증·병합, 후속) | 사용자 판단. 아래 |
| warn 승격 | 2주 운용 뒤 무시가 실측되면 | 처음부터 | P |

스킬: 이 세션에서 효과가 있던 절차(같은 트리를 메인이 동시에 고치지 않기, 겹치면 worktree, 후속은 SendMessage, 검증은 diff 읽기·테스트 재실행·fresh 리뷰어, 커밋은 메인)는 모델이 저절로 하지 않는 부분이다. 반면 P 의 우려(작은 일을 절차로 부풀림)도 맞다. 짧게(≈40줄) 만들고 훅 문구가 가리키게 하는 안과, 운용 뒤 실패 사례가 쌓이면 만드는 안이 있다.

## 문구 초안 (Subagents 절, 기존 두 줄 뒤)
```
- Implementation spanning 3+ code files, ~150+ new lines, or much reading of other code or docs: hand it to a background subagent, so the user can keep talking with you and a fresh context does not inherit your design assumptions. Model: sonnet when the work is fully specified, opus when design judgment remains. Tell the user in one line what, which model, and the expected size.
- Keep in main: small edits, applying a decision just made, docs and config, work that needs the user's answers midway (ask first, then hand off), or anything whose brief would be longer than the work. Before calling delegated work done, read its diff and rerun its tests yourself; main commits.
```

## 훅 초안
- 문턱: 한 턴(사용자 입력 사이)에 메인의 코드 쓰기 12회 또는 서로 다른 코드 파일 8개. Agent 호출이 있으면 0 으로. info, 턴당 한 번.
```
<harness-hook name="delegate-nudge" level="info">
Main has written code {n} times across {m} files this turn without a subagent. If what remains is mostly implementation, a background subagent (sonnet unless design judgment remains) frees you to talk with the user; stay if it is nearly done or needs the user midway.
</harness-hook>
```
- 이월: 직전 턴이 문턱을 넘고 Agent 호출이 없었으면 다음 UserPromptSubmit 에 info 한 번.
```
Last turn main wrote code {n} times in {m} files directly. If this prompt continues that work, brief a background subagent first.
```

## 동료 배포
- 두 쪽 모두: 위임마다 "무엇을, 어느 모델, 예상 규모" 한 줄. 금액은 매 응답이 아니라 원장 요약(턴·세션 끝)으로. 동료 기본 수행자는 sonnet.
- 갈림: Q 는 동료의 opus 수행자에 사용자 허락을 요구, P 는 사유를 밝히면 허용. 사용자 판단.
