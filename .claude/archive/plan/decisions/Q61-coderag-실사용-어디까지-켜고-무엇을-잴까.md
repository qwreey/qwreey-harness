---
format: 1
title: "coderag 실사용: 어디까지 켜고 무엇을 잴까?"
description: "coderag 실사용: 어디까지 켜고 무엇을 잴까? 답 a) 1 과 2 를 CLI 로, MCP 는 주간 뒤에"
status: archived; answered a) 1 과 2 를 CLI 로, MCP 는 주간 뒤에
id: Q61
urgency: soon
blocks: coderag 실사용 준비(색인, 가리킴 한 줄)
recommended: a
created: 2026-11-23T02:02:20.971Z
answered: 2026-11-23T02:03:38.132Z
answer: a
---

# Q61. coderag 실사용: 어디까지 켜고 무엇을 잴까?

## 맥락

지금 상태(이 기기 transcript 에서 셈):
- coderag 플러그인의 **훅**은 모든 세션에서 돈다(팩 rule 과 agent-records rule 주입, 기록 읽기 안내, Bash 앞뒤).
- **찾기 기능은 거의 안 쓰였다**: 셸에서 `coderag search|get|list|stale|records` 를 부른 것이 이 저장소 20 세션에 9번, quad·stl-luau·tbox·table-sim 에서 0번. `coderag:doc-locator` 에이전트는 0번, `coderag:agent-records` 스킬은 15번.
- `coderag.toml` 은 quad, tbox, vitrine 에만 있다(팩 목록). 코드 심볼 색인을 만든 저장소는 없다(`.coderag` 가 8 KB, 이 저장소만 기록 색인 3 MB).
- MCP 서버(`coderag mcp`, search·get 도구)는 있지만 플러그인에 등록하지 않았다. 등록하면 모델이 Bash 대신 도구로 부르기 쉬워지는 대신, 도구 설명이 늘 맥락에 실린다.

실사용 주간에 해 볼 수 있는 것:
1. 기록 찾기: 이 저장소와 quad 에서 "전에 왜 그렇게 정했지" 류를 grep 대신 `coderag search`·doc-locator 로. CLAUDE.md 가리킴 한 줄로 유도.
2. 코드 심볼 찾기: Luau 저장소(quad 나 stl-luau)에서 luau 프로바이더로 색인을 만들고 실제 작업에 `coderag search/get` 을 grep 과 견준다.
3. MCP 등록: 위를 도구로.

어느 쪽이든 usage-report 로 호출 수, 찾은 것의 쓸모(이어서 연 파일), 토큰을 잰다.

## 선택지

- a) 1 과 2 를 CLI 로, MCP 는 주간 뒤에
  상시 글을 늘리지 않고 실제 쓸모부터 잰다. 쓰이지 않는 이유(유도 부족 대 기능 부족)를 가를 수 있다
- b) 1, 2 에 MCP 등록까지
  도구가 있으면 더 쓰일 것. 대신 도구 설명이 늘 실리고 무엇이 쓰임을 늘렸는지 가르기 어렵다
- c) 1 만(기록 찾기)
  가장 가볍다. 코드 심볼 쪽은 나중

**권장 a) 1 과 2 를 CLI 로, MCP 는 주간 뒤에**
지금 찾기 기능이 안 쓰이는 이유부터 가려야 하고, MCP 는 그 뒤에 효과를 견줄 수 있다

## 코멘트

- 2026-11-23T02:03:34.099Z user: 다만 quad쪽엔 시범적으로 coderag에 쓰기 좋게 .claude 폴더의 문서들을 다듬어보고자 함. 다른곳도 그럴 수도 있고
- 2026-11-23T02:03:47.226Z agent: 좋아요. 그러면 1번(기록 찾기)이 quad 에서 제대로 시험돼요. 문서를 다듬기 전과 뒤를 견줄 수 있게 이렇게 하려고 해요.
  - 다듬기 전에: quad 의 실제 질문 10~15개(예: "왜 X 로 정했지", "Y 는 어디 적혀 있지")를 세션 기록에서 뽑고, `coderag search` 로 찾은 첫 결과가 맞는지 기준선을 잰다.
  - 다듬은 뒤: 같은 질문으로 다시 잰다. 그리고 주간 동안 quad 세션에서 search·get·doc-locator 가 몇 번 불렸는지 센다.
  quad 는 다른 저장소라 저는 읽기만 해요. 다만 기준선을 재려면 `coderag gen` 이 quad 의 `.coderag/` 색인을 쓴다(캐시 폴더). 그건 해도 되는지 알려 주세요. 문서 다듬기는 quad 세션에서 하시는 거죠?

## 답

a
