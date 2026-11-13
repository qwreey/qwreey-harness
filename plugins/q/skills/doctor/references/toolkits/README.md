# 툴킷 — 언어·툴체인별 검사 자리

harness-doctor는 **코어**(언어와 무관: CLAUDE.md 계층과 크기, rules paths, 스킬 형식, 훅·설정, 낡음과 모순, 사본 표류, worktree·세션, 정본 싱크)와
**툴킷**(언어·툴체인: 핀, 포매터, 공유 지식 저장소, 언어 고유 사본)으로 나뉜다.
coderag의 지식 계층(global / pack / project, `coderag/.claude/base/layers-and-packs.md` §13)과 짝을 맞춘다.

| harness-doctor | coderag | 예 |
|---|---|---|
| 코어 + 사용자 레벨(`--user`) | global | 하네스 규약, `.claude/base/decisions/` 중 언어 무관 결정(D-07) |
| 툴킷(`toolkits/<이름>`) + 그 공유 지식 저장소(`<이름>-kb`) | pack | luau + luau-kb |
| 대상 저장소 | project | quad, vitrine, `intake/<이름>` |

## 목차
- [있는 툴킷](#있는-툴킷)
- [동작](#동작)

## 있는 툴킷

| 이름 | 상태 | 감지 표식 요지 | 문서 |
|---|---|---|---|
| luau | 검사 있음(TOOL-·KB-·DRIFT-TYPEDEFS) | `*.luau`, mise의 luau·stylua 등, `default.project.json`, `.luaurc` | `luau.md` |
| web | **골격** — 감지만 | `package.json`의 astro·react·vite 등, `*.astro`·`*.tsx` | `web.md` |

## 동작

- scan은 저장소마다 모든 툴킷의 `detect()`를 부르고, 표식이 하나라도 나온 툴킷만 `check()`한다. 한 저장소에 여럿이 켜질 수 있다(quad = luau + web).
- 감지 결과는 보고 머리 `툴킷:` 줄과 `--json`의 `toolkits`에 나온다. 결과(finding)로는 내지 않는다.
- `--toolkits luau,web`은 감지와 무관하게 켠다. `--toolkits none`은 모두 끈다. `harness.env`의 `HARNESS_TOOLKITS`는 쓸 수 있는 툴킷 목록 자체를 줄인다.
- 툴킷 결과는 코어 항목 번호를 빌려 쓴다: 5 공유 지식, 6 사본 표류, 8 툴체인. `--only 8`이면 툴킷의 8번 검사만 돈다.

툴킷을 만들거나 고치는 법(모듈 인터페이스, 새 툴킷 추가)은 q 플러그인 `docs/doctor-toolkits.md`에 있다. 진단에는 필요 없다.
