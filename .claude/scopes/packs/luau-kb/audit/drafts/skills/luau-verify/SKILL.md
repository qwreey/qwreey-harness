---
name: luau-verify
description: >-
  Luau 코드를 실제로 검증할 때(luau-analyze, luau-lsp analyze, luau CLI, lune, stylua, .luaurc, mise 핀) 사용.
  "진단 0건"이 믿을 만한지 확인하는 음성 대조군, 스파이크/재현 파일 작성, 기대 진단 표, 돌연변이 검사,
  툴체인 버전 고정과 업그레이드 시 회귀 확인. 타입 규칙 자체가 아니라 '어떻게 확인하나'가 질문일 때.
---
핵심 절차(초안): 핀된 버전 확인 -> 검사 실행(진단은 stderr, 종료코드 0/1/그 외) -> 음성 대조군이 정확한 건수로 잡히는지 -> 변이 하나로 게이트가 떨어지는지 -> 결과에 버전·솔버 명시.
기준 도구는 luau-analyze(핀 고정), 사용자 재현은 luau-lsp(--definitions, --sourcemap 필요). 스니펫 CI 는 .claude/scopes/packs/luau-kb/audit/drafts/snippet-harness 참고.
