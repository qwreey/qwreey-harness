# D-06. 타입 검사 기준 도구: `luau-analyze` 대 `luau-lsp analyze`

> 작성 2026-11-10. 실험은 D-05 와 같은 사본. 도구 `/code/.local/share/mise/installs/{luau/0.742/luau-analyze, github-johnny-morganz-luau-lsp/1.70.1/luau-lsp}`.

## 1. 각 프로젝트의 입장

| 프로젝트 | 게이트 기준 | 위치 | 코드가 Roblox 전역을 쓰나 |
|---|---|---|---|
| stl-luau | **luau-analyze**. lsp 는 "편집기 조건 재현"용, 게이트 아님 | `stl-luau/.claude/base/typing-limits.md:71-104`, `base/architecture.md:99-118` | 아니오 |
| moonwave-luau | **luau-analyze**(exit code 판정) | `moonwave-luau/scripts/check.sh:6,24,42` | 아니오 |
| quad | **둘 다**. 엔진 무관 그룹은 luau-analyze, 같은 그룹을 lsp 신 솔버로 한 번 더, Roblox 쪽은 lsp(+defs, 한도 플래그) | `quad/scripts/test.sh:32-51`, `.claude/conventions.md:356-360` | 일부(quad-roblox) |
| rbvm | **luau-lsp**(globalTypes + sourcemap 필수) | `rbvm/.claude/tools/check.sh:5-18` | 예 |
| table-sim, devplorer | **luau-lsp**(`--sourcemap`, 음성 대조군도 lsp) | `table-sim/<비공개>`, `devplorer/scripts/check.sh:40,58` | 예 |
| tbox | **luau-lsp**(`mise run analyze` → `scripts/analyze.luau`) | `tbox/mise.toml:45-48` | 일부(Roblox 데이터타입) |

## 2. 실제 근거

- **`luau-analyze` 에는 정의 파일 옵션이 없다.** 0.734 `--help` 에 `--defs` 가 없다. [실행] quad `test.sh:50-51` 에도 같은 실측이 있다.
  - 그래서 Roblox 전역(`Instance`, `game`, `Vector3`)을 쓰는 코드는 **luau-lsp 말고는 검사할 방법이 없다**.
  - 이것이 갈림의 진짜 원인이다. 취향이 아니라 코드가 Roblox 전역을 쓰는지에 따른 조건이다.
- **stl 의 "lsp 가 덜 본다"** [기록]: 옛 `arr.luau` 에서 analyze 72건, lsp 68건이었다. lsp 는 345행에서 `Code is too complex` 로 포기했고 analyze 만 실제 버그 줄(803-804)을 잡았다.
  - 감사 05 는 작은 파일에서 두 도구가 일치함을 보였다. 그러니 차이는 "한도/번들 버전" 에서 난다.
- **이번 측정** [실행], 같은 stl 코퍼스.
  - `luau-analyze` 0.742 는 0건이다.
  - lsp 1.70.1 은 TypeError 3건(spec.contracts, spec.arr 오버로드 유니온)과 LocalShadow 1건이다.
  - lsp 1.69.0 은 308건이다.
  - 즉 **방향이 늘 "lsp 가 덜 본다"는 아니다.** 번들 Luau 버전에 따라 lsp 가 더 내기도 한다.
  - 일반화하면 "두 도구는 다른 Luau 빌드다. 기준을 하나로 정하고 차이는 보고한다"이다.
- **한도 플래그는 lsp 쪽에만 먹는다**(`--flag:LuauTarjanChildLimit=160000` 등).
  - 빼면 큰 생성 타입에서 진단이 조용히 사라진다(quad `conventions.md:360`, `typing-limits.md` 8.28). [기록]
- **공통 함정 셋** [기록, 일부 실행]
  1. 진단은 stderr 로 나온다(stl `architecture.md:106-107`). 실행 결과에서도 확인했다.
  2. `.luaurc` 한 단어로 310건이 0건이 된다. 그러니 파일마다 `--!strict` 를 단다(stl `typing-limits.md:105-124`).
  3. 판정은 exit code 로 하고 출력 줄 수로 하지 않는다(quad `conventions.md:348-352` 사고, table-sim·devplorer·moonwave 동일 규칙).

## 3. 합의안

### 안 A. 조건부 규칙
- **Roblox 전역을 참조하지 않는 코드(순수 Luau 라이브러리·엔진 무관 로직)**: 기준은 핀 고정 `luau-analyze` 다. lsp 결과가 다르면 보고만 한다.
- **Roblox 전역을 참조하는 코드**: 기준은 `luau-lsp analyze` + `--definitions`(globalTypes) + `--sourcemap` + 신 솔버 플래그다. 큰 생성 타입이 있으면 한도 플래그를 저장소 게이트와 **똑같이** 쓴다.
- 공통으로 다음을 지킨다. 저장소 게이트 스크립트가 정본이고 판정은 exit code 다. stderr 를 버리지 않는다. 진단 0건이면 음성 대조군으로 확인한다.

| 프로젝트 | 변경량 |
|---|---|
| 전부 | 0. 지금 각자의 선택이 이 조건과 정확히 맞는다 |

### 안 B. 공통 기본값 `luau-analyze` + Roblox 저장소 override
- 기본은 analyze 다. rbvm·table-sim·devplorer·tbox 는 rules 에 "이 저장소는 lsp(+defs)"를 한 줄 둔다.
- 결과는 안 A 와 같지만 override 파일이 4개 생긴다.

## 4. 추천: 안 A

- 갈림의 원인이 `--defs` 의 유무라는 **도구 사실**이라서 조건문 하나로 일곱 저장소가 모두 설명된다. 변경도 0이다.
- 에이전트가 실제로 틀리는 지점은 도구 선택보다 공통 함정 셋이다. 그래서 공통 rules 에는 "저장소 게이트를 돌린다 / exit code / stderr" 를 둔다.
- 도구 선택의 근거는 스킬 reference(`luau-verify/analyze-vs-lsp.md`)로 보낸다.

## 5. 사용자 확인 질문

타입 검사 기준을 "Roblox 전역을 안 쓰는 코드는 `luau-analyze`, 쓰는 코드는 `luau-lsp`(+정의 파일·sourcemap), 어느 쪽이든 저장소 게이트 스크립트가 정본"이라는 조건 규칙으로 정리해도 될까요? quad 처럼 엔진 무관 코드를 두 도구로 모두 보는 이중 검사를 다른 라이브러리(stl, moonwave)에도 권할지도 알려 주세요.

## 사용자 결정 (2026-11-10)

**합의안 보완: 'Roblox 전역 유무' 만으로 고르지 않는다.**
- 자동완성, hover, 공개 API 의 추론 타입 표시 같은 **DX 를 검사할 때는 luau-lsp 를 돌려 보는 것이 유용하다.** Roblox 전역이 없는 순수 Luau 라이브러리도 마찬가지다.
- 정리하면 다음과 같다.
  - 정확성 게이트: 순수 Luau 는 analyze, Roblox 전역은 lsp+defs
  - DX 확인: 공개 API 를 다루는 라이브러리면 lsp 도 돌린다
- 옮길 곳: luau-verify `checkers.md` 에 'DX 검사' 절을 추가한다(lsp 로 무엇을 어떻게 확인하는지).
