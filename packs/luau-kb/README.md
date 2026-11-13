# luau-kb

Luau·Roblox 저장소에서 켜는 지식 팩이다. 켜 두면 Claude 가 Luau 타입 시스템이 어디서 깨지는지, 검사 결과를 믿어도 되는지, 테스트·성능·코드 스타일, Roblox 엔진·네트워크·GUI·물리 동작을 짐작하지 않고 이 팩의 정리된 지식을 찾아 보고 답한다. 여러 Luau 저장소에서 각자 따로 알아낸 것을 한 곳에 모았고, "확인됨" 이라고 적힌 사실은 모두 실제로 돌려 본 작은 재현 파일과 짝이라 모델의 기억보다 믿을 만하다. 프로젝트 고유 설계(특정 라이브러리의 타입 이름, API)는 넣지 않고, 저장소마다 정책이 갈린 것은 한쪽을 고르지 않는다. 기본으로 꺼져 있어서 Luau 저장소가 켜기 전에는 아무것도 싣지 않는다.

## 무엇이 달라지나
- 타입 에러가 이해되지 않거나, 날 곳에서 안 나거나, 성능·테스트·Roblox API 질문을 하면 해당 스킬(12개 중 맞는 것)을 불러 근거 파일과 함께 답한다.
- `.luau` 파일을 처음 열면 공통 규칙(`--!strict`, 이름, 에러, require, 포맷 등 약 40줄)이 한 번 실리고, 저장소 자체 규칙이 있으면 그쪽을 따른다.
- luau-lsp 가 붙어 Claude 가 `.luau` 파일의 진단, 타입 정보, 정의 위치를 직접 본다. Rojo 프로젝트면 Roblox 정의 파일로 검사한다.
- Roblox 공식 문서를 내려받아 API 시그니처와 deprecated 여부를 찾아 인용할 수 있다.
- 다른 저장소에서는 켜지지 않는다.

## 비용
- 켠 저장소에서만: 스킬 설명 12개(영문 약 6,400자, 대략 1,600 토큰), `.luau` 를 처음 열 때 규칙 본문 한 번(약 1,800 토큰, compact 뒤 다시).
- 스킬 본문과 참고 문서는 부를 때만 읽는다. 훅은 없다.

## 요구 사항
- 규칙 주입은 coderag 플러그인(`coderag@coderag-market`)과 coderag 설정이 한다. 이 팩만 켜면 스킬과 LSP 만 쓰인다.
- LSP: `luau-lsp`(mise 로 `github:JohnnyMorganz/luau-lsp` 설치, 또는 `LUAU_LSP_BIN` 으로 경로 지정). Linux·macOS 셸 스크립트로 띄운다.

## 끄기
- 그 저장소의 `coderag.toml` 에서 `[[packs]] name = "luau-kb"` 를 지우고 `coderag adapt --harness claude` 를 다시 돌린다.

## 설치
```bash
claude plugin marketplace add <claude-doctor 폴더>   # 마켓을 처음 쓸 때 한 번
claude plugin marketplace add <coderag 폴더>
claude plugin install coderag@coderag-market
claude plugin install luau-kb@claude-doctor-market
```
기계마다 한 번 `~/.coderag/coderag.toml` 에 팩 위치를 등록하고, Luau 저장소의 `coderag.toml` 에 아래를 적은 뒤 `coderag adapt --harness claude` 를 돌린다.
```toml
[[packs]]
name = "luau-kb"
```
codex, agy 같은 다른 에이전트는 `AGENTS.md` 가 같은 내용을 평문 경로로 안내한다.

자세한 구조(스킬 목록, 폴더, 검증 방법, 기여 규칙, 원천, 옛 경로): [docs/how-it-works.md](docs/how-it-works.md)
