# D-03. 실행기(러너): `luau` / `lune` / `lute`

> 작성 2026-11-10. 실험 `/tmp/cd-exp/syn/c1,c3.luau`. lute 는 이 컨테이너에 설치돼 있지 않아 실행하지 못했다.

## 1. 각 프로젝트의 입장

| 프로젝트 | 입장 | 위치 |
|---|---|---|
| stl-luau | **`luau` CLI 만. lune 금지.** 갈아탄다면 lute | `stl-luau/.claude/base/architecture.md:15-22`, `.claude/conventions.md:153`, `mise.toml:7-8` |
| quad | 순수 `luau` CLI + mock 으로 테스트 | `quad/.claude/base/architecture.md:813-815` |
| moonwave-luau | 순수 `luau`. lune 없음(`const`). `io` 대신 `stage.sh` 가 입력을 모듈로 굽는다 | `moonwave-luau/mise.toml:8-12`, `.claude/conventions.md:78-80,104` |
| tbox | **`luau` + `lute` 두 번 실행.** `fs`/`process` 가 필요한 스크립트는 lute | `tbox/mise.toml:16-17,23-26`, `CLAUDE.md:134-140` |
| table-sim, devplorer | lune 을 넣지 않는다(`const`). 엔진 무관 로직은 `luau` CLI 스펙 | `table-sim/mise.toml:8`, `devplorer/mise.toml:4`, `table-sim/.claude/conventions.md:96` |
| (모순) moonwave `.vscode` | `@lune/` 별칭 설정이 남아 있음 | 감사 04 §2.3 #2 |
| (낡은 포크) quad-changelog-check | "`luau` 또는 `lune`" | 감사 05 §3(c) — 근거에서 제외 |

## 2. 실제 근거

- **lune 0.10.5 는 `const` 를 파싱하지 못한다.** `const x = 1` 에서 `Incomplete statement: expected assignment or a function call` 이 난다. [실행]
  - 다섯 저장소가 이것을 같은 이유로 적는다.
  - 이 사실 하나로 `const` 를 쓰는 저장소에서 lune 은 실행기가 될 수 없다.
- **`pesde run` 은 스크립트를 lune 류 엔진으로 실행한다.** 그래서 `[scripts]` 를 비운다.
  - stl `architecture.md:30-32`, tbox `CLAUDE.md:134-137`
  - tbox 는 PATH 문제(`failed to replace process`)까지 겪었다. [기록]
- stl 의 원 근거는 사용자 발언이다. "luau 로 안 하면 타입이 못 따라가서 문제", "lune 이 반쯤 abandoned"(`architecture.md:18-21`). 앞쪽은 lune 의 Luau 버전이 뒤처진다는 관찰이고 뒤쪽은 판단이다. [서술]
- **`luau` CLI 의 대가**: `io`/`fs`/`warn` 이 없다(stl `architecture.md:26-29`). [기록]
  - 파일 입력이 필요하면 moonwave 처럼 굽거나 tbox 처럼 lute 를 쓴다.
- **lute 1.0.0 은 `const` 를 파싱한다**(tbox `CLAUDE.md:138`). 전역 `loadstring` 은 없다(`@lute/luau` 로 대체). [기록, 로컬 재현 불가]
- 테스트 엔트리를 `init.luau` 로 지으면 ambiguous require 에러가 난다(tbox `CLAUDE.md:141-144`, moonwave `conventions.md:71`). 러너와 무관하게 공통인 사실이다. [기록]

## 3. 합의안

### 안 A. 조건부 규칙
- 기본 실행기는 `luau` CLI 다(테스트·스파이크·벤치).
- `fs`/`process` 가 필요한 **도구 스크립트**는 lute 로 쓴다.
- **lune 은 `const` 를 쓰는 저장소에서 금지**다. `const` 를 안 쓰는 저장소(지금 rbvm, quad 게시 소스)에서도 새로 도입하지 않는다.
- 런타임 호환을 넓게 보증하려는 라이브러리(tbox)는 같은 테스트를 lute 로도 돌린다. 이것은 선택이다.

| 프로젝트 | 변경량 |
|---|---|
| stl, quad, table-sim, devplorer, tbox | 0 |
| moonwave | `.vscode/settings.json` 의 `@lune/` 별칭 삭제 1건(모순 해소) |

### 안 B. 공통 기본값 `luau` + lute 를 표준 2차 러너로
- 모든 저장소가 `luau` + `lute` 이중 실행을 목표로 한다.
- 각 저장소 mise.toml 에 lute 핀을 더하고 `loadstring` 류 차이를 흡수하는 헬퍼가 필요하다(tbox `Helper.loadChunk` 참고).
- 이득은 "두 번째 런타임에서 깨지는 코드"의 조기 발견이다. 다만 지금 로컬에 lute 바이너리가 없고 실익을 잰 기록도 없다.

## 4. 추천: 안 A

- 모든 저장소의 실제 동작과 이미 일치한다(변경 0, moonwave 별칭 1건만).
- 금지 이유가 "취향"이 아니라 **재현되는 파싱 실패**라서 규칙으로 두기에 안정적이다.
- lune 이 `const` 를 지원하게 되면 금지 근거가 사라진다. 그래서 규칙 문장에 "`const` 를 파싱 못 하므로"를 함께 적어, 근거가 바뀌면 규칙도 바뀌게 한다.

## 5. 사용자 확인 질문

실행기는 "`luau` CLI 기본, 파일·프로세스가 필요한 도구만 lute, lune 은 쓰지 않음"으로 공통 규칙에 넣을까요? tbox 의 `luau`+`lute` 이중 실행은 tbox 고유로 둘지, 다른 라이브러리(stl, quad)에도 권할지 정해 주세요.

## 사용자 결정 (2026-11-10)

**확정, 보완 포함: `luau` CLI 가 기본이다.** 단 Roblox 프로젝트에서 Roblox 서비스나 환경에 의존하는 동작(`task`, 이벤트 등)은 Roblox Studio MCP 로 확인할 수도 있어야 한다.
- 항상 Studio 를 부르면 기계적 테스트가 어려워진다. 그래서 필요한 부분만 **mock** 을 만들어 `luau` 로 돌리는 것이 기본이다.
- Studio 는 mock 이 실제와 맞는지 확인하거나, mock 으로 재현할 수 없는 동작을 볼 때 쓴다.
- lune 은 쓰지 않는다(`const` 파싱 실패).
- 옮길 곳: roblox-luau 스킬(Studio MCP 사용 시점, mock 작성 패턴. rbvm 이 mock 환경의 실례).
