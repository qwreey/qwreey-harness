---
format: 1
title: codex-plugin-cc 에서 무엇을 가져올까?
description: codex-plugin-cc 에서 무엇을 가져올까? 답 a) 1·2·3 모두
status: archived; answered a) 1·2·3 모두
id: Q21
urgency: later
blocks: delegate 템플릿 개선, 동료용 codex 안내
recommended: a
created: 2026-11-17T02:02:16.140Z
answered: 2026-11-17T02:06:58.151Z
answer: a
---

# Q21. codex-plugin-cc 에서 무엇을 가져올까?

## 맥락

**그 플러그인(OpenAI 공식, Apache-2.0):** Claude Code 안에서 Codex 를 "같은 저장소·같은 계정으로 일하는 두 번째 코더" 로 쓴다. 리뷰(네이티브와 공격형), 작업 위임(rescue, 기본으로 쓰기 허용), 세션 이어가기, Windows·macOS 지원. 결과는 원문 그대로 보여 주고 검증 단계는 없다. 기록: `.claude/scopes/plugins/qwreey-delegate/audit/1-codex-plugin-cc/summary.md`.

**우리 delegate 와 차이:** 우리는 권한 없는 사용자로 격리하고(저장소를 못 건드림) Claude 가 주장을 재현해 검증하며, Gemini(agy)도 쓴다. 대신 Linux root 가 필요해 Windows 동료는 못 쓴다.

**가져올 후보**
1. 리뷰 결과를 정해진 꼴(판정, 파일·줄 범위, 확신, 권고)로 받는 출력 계약 → delegate 버그 사냥 템플릿. 작음.
2. OpenAI 가 자기 모델용으로 다듬은 XML 블록 프롬프트와 "근거 없는 주장 금지" 규칙 → 같은 템플릿. 작음.
3. 회사 Windows 동료에게는 우리 delegate 대신 이 플러그인을 안내(Stop-gate 끔, rescue 쓰기 기본값 주의). README 와 HUMAN_TODO 몇 줄.
- 들이지 않을 것: Stop-gate(턴마다 Codex 를 돌려 비용), 세션 이어가기(우리 "좁은 질문 하나" 원칙과 부딪힘).

## 선택지

- a) 1·2·3 모두
  템플릿 개선과 동료 안내
- b) 3 만(동료 안내)
- c) 지금은 기록만

**권장 a) 1·2·3 모두**
1·2 는 작고 Codex 쪽 답의 검증을 쉽게 한다. 3 은 회사 배포에서 우리 delegate 가 못 메우는 자리를 바로 채운다.

## 답

a
