# D-06 기준 검사기 — 결정 (2026-11-10)

원문: `claude-doctor .claude/base/decisions/D-06-type-checker.md` 끝의 "사용자 결정" 절. 이 파일은 요약이다.

## 맥락
stl-luau·moonwave-luau 는 `luau-analyze`, quad 는 둘 다, rbvm·table-sim·devplorer·tbox 는 `luau-lsp` 를 게이트로 쓴다. `luau-analyze` 는 정의 파일을 읽지 못해 Roblox 전역을 쓰는 코드는 luau-lsp 로만 검사할 수 있다. 두 도구는 다른 Luau 빌드라 판정이 갈릴 수 있다.

## 결정
"Roblox 전역 유무" 하나로만 고르지 않는다.
- 정확성 게이트: 순수 Luau 는 `luau-analyze`, Roblox 전역을 쓰면 `luau-lsp` + 정의 파일.
- DX 확인: 공개 API 를 다루는 라이브러리는 순수 Luau 라도 luau-lsp 를 돌려 자동완성, hover, 공개 API 의 추론 타입 표시를 본다.

## 반영한 곳
- `skills/luau-verify/references/checkers.md` §5 (결정), §6 (DX 검사, `tools/lsp_probe.py`, Claude Code LSP 연동 `.lsp.json`)
- `skills/luau-roblox/references/typedefs.md`

## 되돌릴 조건
`luau-analyze` 가 정의 파일을 읽게 되거나, 두 도구의 Luau 빌드 차이로 한쪽 게이트가 반복해서 실제 버그를 놓치면 다시 본다.
