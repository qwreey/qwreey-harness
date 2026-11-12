# D-03 러너 — 결정 (2026-11-10)

원문: `/code/Projects/claude-doctor/decisions/D-03-runner.md` 끝의 "사용자 결정" 절. 이 파일은 요약이다.

## 맥락
stl-luau·moonwave-luau·quad 는 `luau` CLI 만, tbox 는 `luau` + `lute` 이중 실행, table-sim·devplorer 는 lune 을 넣지 않았다. lune 0.10.5 는 `const` 를 파싱하지 못한다(실측).

## 결정
- 기본 러너는 `luau` CLI 다. lune 은 쓰지 않는다.
- Roblox 서비스·환경에 기대는 동작(`task`, 이벤트 등)은 필요한 부분만 mock 을 만들어 `luau` 로 돌린다. 항상 Studio 를 부르면 기계적 테스트가 어렵다.
- Roblox Studio MCP 는 mock 이 실제와 맞는지 확인할 때, mock 으로 재현할 수 없는 동작을 볼 때 쓴다.

## 반영한 곳
- `skills/luau-verify/references/tooling.md` §2
- `skills/luau-roblox/` (판정 표, mock 패턴, Studio MCP 사용법)

## 되돌릴 조건
lune 이 `const` 를 파싱하고 Luau 판을 따라잡거나, Studio 를 기계적으로 부를 수 있는 헤드리스 실행기가 생기면 다시 본다.
