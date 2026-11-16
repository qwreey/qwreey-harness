---
name: luau-roblox
description: >-
  Roblox typing and test setup: luau-lsp definition files and sourcemap, typing GetService, Instance.new,
  FindFirstChild and IsA, luau CLI mocks vs Studio, Studio MCP. Use when Roblox API types fail or deciding mock vs
  Studio. Engine behavior is roblox-engine/net/world. 트리거: mock 으로 충분해?, Studio MCP, 정의 파일 설정.
---
# luau-roblox

"Roblox 위의 Luau 코드를 어떻게 타입 검사하고, 어떻게 믿을 만하게 시험하나"를 다룬다. 엔진이 **실제로 어떻게 동작하나**는 roblox-engine·roblox-net·roblox-world 가, 공식 문서 조회는 roblox-docs 가 맡는다. 출발점은 사용자 결정 D-03 이다(`decisions/`).

- **기본 러너는 `luau` CLI 다.** 엔진 의존 동작은 필요한 부분만 mock 으로 만든다. lune 은 쓰지 않는다.
- **Studio(MCP)는 두 경우에만 쓴다.** mock 이 엔진과 맞는지 확인할 때, mock 으로 재현할 수 없는 동작을 볼 때.
- **Roblox 타입은 `luau-lsp --platform=roblox` + 정의 파일에서만 나온다.** `luau-analyze` 는 `Instance` 를 모른다.

## 결정 트리
1. 질문이 "내 코드가 가정한 계약"인가, "엔진이 실제로 어떻게 하나"인가? 앞은 luau+mock 이다. 뒤는 roblox-* 주제 파일을 먼저 읽고, 답이 없으면 Studio 로 간다. → `references/env-dependence.md` §1–2
2. 테스트는 주입을 먼저 하고, 그다음 필요한 부분만 mock 한다. 그 mock 이 엔진과 갈리는 지점은 roblox-engine 주제 파일의 §8 표와 `mock 흉내:` 줄에 있다. → `references/mocks.md`
3. Studio 로 잴 때는 대상 Studio 를 고르고, 결과는 `return` 하고, Deferred 결과는 두 번째 호출에서 읽는다. → `references/studio-mcp.md`
4. 타입 에러면 먼저 정의 파일과 `--platform=roblox` 로 검사하는지 본다(`references/typedefs.md`). 그다음 API 별 타입 규칙(`references/api-types.md`). API 시그니처 자체는 추측하지 말고 roblox-docs 의 `api` 로 확인한다.

## 라우팅
| 상황 / 질문 | 읽을 곳 |
|---|---|
| 이 테스트에 Studio 가 필요한가, luau+mock 으로 되나 | `references/env-dependence.md` §2 |
| 판정 절차, task·신호·Instance 수명의 요약 | `references/env-dependence.md` §3–5 |
| mock 범위, mock 보다 주입, getfenv 전역 주입 | `references/mocks.md` §1–3 |
| 검증된 mock 모양, 엔진과의 차이 기록, 충실도 검증 | `references/mocks.md` §4–7 |
| Studio MCP 도구, 여러 Studio 고르기, studio-sync, 실측 관용구, 내장 skill | `references/studio-mcp.md` |
| `Instance.new`·`GetService`·`Clone` 의 타입 | `references/api-types.md` §2 |
| `FindFirstChild`·`WaitForChild` 의 nil, 자식 접근, sourcemap 자식 타입 | `references/api-types.md` §3–4 |
| `IsA`·`ClassName` 좁히기, 캐스트 | `references/api-types.md` §5 |
| `GetAttribute` 가 `unknown?`, `typeof` 대 `type`, Enum 타입 | `references/api-types.md` §6–8 |
| 이벤트·데이터 타입, 타입이 런타임보다 낙관적인 자리, 검사기가 못 잡는 엔진 호출 | `references/api-types.md` §9–11 |
| `game` 이 Unknown global, `Instance.new` 가 any, globalTypes·`--definitions` | `references/typedefs.md` §1–3 |
| Rojo sourcemap, LSP 세션(에디터·Claude Code·lsp_probe) | `references/typedefs.md` §4–5 |
| API 시그니처·보안·스레드 안전성·deprecated 의 문서 근거 | roblox-docs (`tools/roblox_docs.py api`) |
| 엔진 동작(신호, Instance, Tween, task, Actor, Studio require) | roblox-engine |
| 원격·복제·서비스 / GUI·물리·캐릭터 | roblox-net / roblox-world |
| 순수 Luau 타입, 검사기 옵션, 테스트 하네스 | luau-types, luau-verify, luau-testing |

## 자주 밟는 함정 (요약)
- `luau-analyze` 로는 Roblox 타입을 볼 수 없다. 정의 파일 없이 `--platform=roblox` 만 주면 `Unknown global 'Instance'` 다.
- `GetAttribute` 는 `unknown?` 이다. 쓰기 전에 `typeof` 로 좁힌다.
- 타입 검사기는 병렬 단계의 금지 API, SharedTable 값 제약, Tween 목표 표를 검사하지 않는다.
- mock 은 값 비교 없이 신호를 쏘거나(같은 값 대입에 `Changed` 1회), 동기로 배달해 Deferred 를 숨기기 쉽다. 차이를 목록으로 남긴다.
- Studio MCP 의 Deferred 결과는 같은 호출 안에서 읽으면 0 이다. 두 번째 호출에서 읽는다.
