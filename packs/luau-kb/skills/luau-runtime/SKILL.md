---
name: luau-runtime
description: >-
  Luau semantics without the Roblox engine: weak tables and GC leaks, swallowed coroutine errors, require-by-string
  in the luau CLI (init.luau, @self, aliases). Use when weak entries persist, a coroutine error vanishes, or require
  cannot resolve. In-engine behavior is roblox-engine. 트리거: weak table 안 사라짐, 코루틴 에러 삼킴, require 안 풀림.
---
# luau-runtime

"Roblox 엔진이 없어도 성립하는가"가 이 스킬의 기준이다. 여기 있는 주장은 luau CLI 로 재현할 수 있고, Roblox VM 도 같은 의미론을 따른다. 엔진이 얽히면(Instance, `task`, Studio require, Roblox 안 GC 관찰) roblox-engine 으로 간다. 두 쪽은 절마다 서로 링크한다.

## 결정 트리
1. 질문에 Instance·`task`·Studio·`script.Parent` 가 들어 있나? 들어 있으면 roblox-engine 이 먼저다(`gc-in-roblox.md`, `require-in-roblox.md`, `tasks-and-threads.md`). 아니면 아래.
2. **약한 표·누수**: 의미론(무엇이 남나)은 `references/gc-and-weak-tables.md` §2–3, 판정(어떻게 믿나)은 §5. 비용은 luau-perf `gc-and-memory.md`, 시험 하네스는 luau-testing `gc-and-time.md`.
3. **코루틴 에러가 사라짐 / 기다릴 수 없는 자리**: `references/coroutines.md`.
4. **require 가 안 풀리거나 엉뚱한 모듈을 실음**: `references/require-by-string.md` §1–4. 검사기가 잡는지는 luau-verify `checkers.md` §7, 경로를 어떻게 쓸지는 luau-style `modules.md`.
5. 주장마다 `status` 를 본다. `verified` 는 `snippets/` 의 스니펫이 0.734·0.742 에서 재현한 것이고, `described` 는 원천 서술이다.

## 라우팅
| 상황 / 질문 | 읽을 곳 |
|---|---|
| weak-key 표 값이 키를 잡으면 수거되나, ephemeron 인가 | `references/gc-and-weak-tables.md` §2 |
| `__mode = "v"` 의 키, `__mod` 오타, 약한 배열의 구멍, 멈춘 코루틴이 잡는 키 | `references/gc-and-weak-tables.md` §3 |
| weak 항목이 간헐적으로 사라진다, 메모리가 안 줄어든다 | `references/gc-and-weak-tables.md` §4 |
| 누수 판정 절차, 프로브가 스스로 결론을 바꾸는 함정 | `references/gc-and-weak-tables.md` §5 (하네스 정본: luau-testing `gc-and-time.md`) |
| 함수 키 레지스트리, 옵저버 그래프, 두 weak 표를 잇는 설계 | `references/gc-and-weak-tables.md` §7 |
| `coroutine.resume`·`wrap` 의 에러가 사라진다, 죽은·실행 중 코루틴 | `references/coroutines.md` §1 |
| `attempt to yield across C-call boundary`, CLI 최상위 yield 크래시, `C stack overflow` | `references/coroutines.md` §2 |
| thread-local·문맥 전파, 암묵 문맥이 다른 코루틴에 샌다 | `references/coroutines.md` §3 |
| `init.luau` 안의 `./` 와 `@self`, `X.luau` 를 `X/init.luau` 로 바꿀 때, 테스트 엔트리 이름 | `references/require-by-string.md` §1 |
| `could not resolve child component … (ambiguous)`, `could not reset to requiring context` | `references/require-by-string.md` §2 |
| `.luaurc` alias 가 에디터에선 되는데 실행은 `could not jump to alias` | `references/require-by-string.md` §3 |
| symlink 로 건 패키지가 안 풀린다, `cp -rL` | `references/require-by-string.md` §4 |
| require 오타인데 진단 0건 | `references/require-by-string.md` §5 → luau-verify `checkers.md` §7 |
| 같은 패키지 사본 둘, 타입만 쓰려는 require 도 실행된다 | `references/require-by-string.md` §8 |
| require 경로 표기 정책(D-12, 확정) | `references/require-by-string.md` §9 |
| Roblox 안 GC 관찰, Instance 를 weak 키로 쓴 표 | roblox-engine `gc-in-roblox.md`, `instance-lifecycle.md` §4 |
| Studio 문자열 require, ModuleScript 캐시, `@game` | roblox-engine `require-in-roblox.md` |
| `task.spawn`·`defer` 순서, RemoteFunction 경쟁 | roblox-engine `tasks-and-threads.md` |

## 자주 밟는 함정 (요약)
- Luau weak-key 표는 ephemeron 이 아니다. 값이 키를 잡으면(필드·업밸류·두 표 순환) 영구 잔존이다. 프로브에서 포획 변수를 nil 로 지우면 결론이 뒤집힌다.
- `__mode = "v"` 의 키는 강하다. `{ __mod = "k" }` 는 경고 없이 강한 표다. 약한 값 배열은 구멍이 생겨 `ipairs`·`#` 가 틀린다.
- GC 는 할당이 있어야 진행한다. "안 줄어든다"만으로는 누수가 아니다. 객체 수로 판정한다.
- `coroutine.resume` 은 던지지 않고 `(false, err)` 를 돌려준다. 결과를 버리면 에러가 사라진다.
- `init.luau` 의 `./` 는 폴더의 형제다(안은 `@self/`). 테스트 엔트리를 `tests/init.luau` 로 지으면 `./` 가 저장소 루트가 된다.
- `.luaurc` alias 값은 `./` 로 시작해야 CLI 런타임·analyze 에서 풀린다. luau-lsp 는 `./` 없는 alias 와 symlink 도 풀어 에디터만 깨끗해 보인다.
- strict 의 luau-analyze 는 풀리지 않는 require 를 잡지만, 있는 다른 모듈로 풀리는 오타는 못 잡는다. 실제로 require 하는 테스트를 둔다.
