---
format: 1
title: codex 위임에 worktree 모드를 열까?
description: codex 위임에 worktree 모드를 열까? 답 a) 그대로 둔다
status: archived; answered a) 그대로 둔다
id: Q66
urgency: later
blocks: 없음
recommended: a
created: 2026-11-27T04:24:38.650Z
answered: 2026-11-27T04:29:18.481Z
answer: a
---

# Q66. codex 위임에 worktree 모드를 열까?

## 맥락

HUMAN_TODO 에서 옮겨 온 질문이에요.

- 이 호스트에서는 codex 의 자체 샌드박스(bwrap)가 안 떠서, 지금은 빈 폴더(empty) 모드만 써요
- 열려면 `~/.claude/harness.env` 에 `HARNESS_DELEGATE_CODEX_SANDBOX=danger-full-access` 한 줄이 필요해요
- 열어도 위임은 따로 떼어 둔 uid 와 worktree 안에서 돌아요. 빠지는 것은 codex 자체 샌드박스 한 겹이에요

## 선택지

- a) 그대로 둔다
  빈 폴더 모드로 좁은 질문은 충분히 맡길 수 있다
- b) 연다
  codex 가 저장소 코드를 직접 돌려 보며 답한다

**권장 a) 그대로 둔다**
지금까지 막힌 위임이 없었다. 필요한 일이 생기면 그때 열어도 된다

## 답

a
