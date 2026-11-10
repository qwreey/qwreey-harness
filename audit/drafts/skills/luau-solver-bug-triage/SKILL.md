---
name: luau-solver-bug-triage
description: 신 솔버/타입 검사기의 의심 결함을 최소 재현으로 줄이고 old/new, 0.734/0.742/최신으로 대조해 solver-bugs.tsv 와 업스트림 이슈 초안을 만든다. 게시는 하지 않는다.
disable-model-invocation: true
---
1. 재현을 15줄 .luau 로 줄이고 통제 줄(같은 실수의 다른 모양, 잡혀야 함)을 둔다.
2. `luau-analyze` 와 `--solver=old`, 핀 버전 둘 이상, `luau-lsp analyze --flag:LuauSolverV2=true` 로 건수 행렬을 만든다.
3. snippets/ 에 `-- bug-present` 표식으로 저장하고 solver-bugs.tsv 에 행 추가.
4. 업스트림 중복 이슈 검색(체크리스트: stl-luau/.claude/audit/luau-solver-issues/DRAFTS.md). 영문 초안은 drafts 에만 두고 **게시하지 않는다**.
