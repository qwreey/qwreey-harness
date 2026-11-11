# 툴킷 web (JS/TS 웹) — 골격

> **실제 프로젝트를 가져온 뒤 채움.** 지금은 감지와 플러그인 도입 추천(`WEB-PLUGINS`, `WEB-RULE`, 정보)만 한다. 나머지 검사는 아직 없다.
> 대상 예정: 블로그(react/astro, 아직 옮겨 오지 않음), vitrine(go + react/vite), quad·devplorer의 astro 문서 사이트.

검사 모듈: `scripts/toolkits/web.py`. 공유 지식 저장소: 아직 없음(`web-kb`가 생기면 `--kb` 기본 경로 `<작업공간>/web-kb`).

## 감지 표식

하나라도 있으면 켠다.
- 아무 깊이의 `package.json`(node_modules 제외)의 dependencies·devDependencies에 astro, react, vite, next, vue, svelte, `@sveltejs/kit`, solid-js, preact, nuxt, `@remix-run/react` 중 하나
- `*.astro`, `*.tsx`, `*.jsx`, `*.vue`, `*.svelte` 파일

확인(2026-11-10, 읽기 전용): vitrine → `web/package.json: react, vite` + tsx 7개로 감지된다.
같은 실행에서 quad(`docs/site/package.json: astro`)와 devplorer(`docs/package.json: astro`)도 web으로 함께 감지됐다(luau + web 두 툴킷).

## 검사

| 코드 | 등급 | 내용 |
|---|---|---|
| `WEB-PLUGINS` | 정보 | security-guidance, frontend-design, context7, claude-security 가 project·local·user `enabledPlugins` 어디에도 없으면 하나씩 추천한다. 설정 안내는 메시지에 있다. 근거: [audit/16 §8](../../../../../../audit/16-marketplace.md) |
| `WEB-RULE` | 정보 | `qwreey-conventions` 플러그인이 켜져 있지 않다(web-security rule 은 그 플러그인의 `rules/` 에서 훅이 주입한다) |

판정: 추천일 뿐이다. 공유 worktree 저장소는 security-guidance 에 `ENABLE_STOP_REVIEW=0` 을 더한다. 이미 다른 방식(로컬 마켓 등)으로 켜져 있으면 무시한다.

## 후보 (실측 후 도입)

- typescript-lsp, gopls-lsp(vitrine Go), rust-analyzer-lsp(Rust 저장소): 바이너리 설치 후 audit/16 §7-5 실측을 거쳐 `WEB-PLUGINS` 목록에 더한다.
- modern-web-guidance, axe-accessibility: 참고. web-kb 후보.

## 이후 채울 검사 후보

코드 이름은 예약만 했다(`web.py`의 `CANDIDATES`). 실제 프로젝트를 감사하며 오탐·기준을 정한 뒤 하나씩 검사로 옮긴다.

| 예약 코드 | 볼 것 | 정할 것 |
|---|---|---|
| `WEB-LOCK` | 패키지 매니저 lock이 하나인가(package-lock / pnpm-lock / yarn.lock / bun.lockb 혼재), `packageManager` 필드와 맞는가 | 워크스페이스(monorepo)에서 하위 lock을 어떻게 볼지 |
| `WEB-TSSTRICT` | tsconfig의 `strict`(와 `noUncheckedIndexedAccess` 등). `extends` 사슬을 따라간다 | 등급(경고/정보), astro 기본 tsconfig 프리셋 해석 |
| `WEB-LINT` | 린터·포매터 설정(eslint / biome / prettier)이 있는가, 둘이 겹치는가 | 포매터 미설정을 D-02(stylua)처럼 사고로 볼 근거가 있는가 |
| `WEB-CMDS` | 빌드·테스트·타입검사 명령(`package.json` scripts)이 CLAUDE.md에 적혀 있는가, 적힌 명령이 scripts에 있는가 | 하위 디렉터리 package.json(vitrine `web/`)의 명령을 어떻게 적게 할지 |
| `WEB-NODEPIN` | node·패키지 매니저 버전 핀(mise.toml, `.nvmrc`, `engines`)이 형제 저장소와 어긋나는가 | luau의 D-05처럼 목표값 없이 불일치만 알린다(코어 도우미 `pin_mismatch` 재사용) |
| `WEB-GENERATED` | 생성물(`dist/`, `.astro/`, `schema.d.ts`)이 커밋되거나 rules `paths`에 걸리는가 | 생성물 목록 |

그 밖의 후보(검사보다는 모델 판정): `SKILL-SIDEFX` 낱말(`npm publish`, `wrangler deploy`, `vercel --prod`), 공유 지식 후보 신호(브라우저·번들러 버전 의존 서술), 무거운 실행(`vitest bench`, lighthouse — heavy-proc-guard의 web 실행기는 이미 있다).

## 채우는 순서

1. 프로젝트를 `intake/<이름>/`로 반입한다(`<doctor>/intake/README.md`).
2. `scan.py intake/<이름>`으로 감지와 코어 결과를 본다.
3. 위 후보를 그 프로젝트에 손으로 적용해 보고, 참 발견과 오탐을 `audit/intake/<이름>-<날짜>.md`에 적는다.
4. 참 발견이 있던 후보부터 `web.py`의 `check()`에 옮기고, 이 문서의 표를 "검사" 표로 바꾼다(형식은 `luau.md`의 툴체인 표).
5. 재구성 전후 비교처럼, 옮긴 뒤 반입 사본과 vitrine에 다시 돌려 결과를 확인한다.
