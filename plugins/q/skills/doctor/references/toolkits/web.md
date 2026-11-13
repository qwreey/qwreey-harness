# 툴킷 web (JS/TS 웹) — 골격

지금은 감지와 플러그인 도입 추천(`WEB-PLUGINS`, 정보)만 한다. 나머지 검사는 아직 없다(채우는 법: q 플러그인 `docs/doctor-toolkits.md`).

검사 모듈: `scripts/toolkits/web.py`. 공유 지식 저장소: 아직 없음(`web-kb`가 생기면 `--kb` 기본 경로 `<작업공간>/web-kb`).

## 감지 표식

하나라도 있으면 켠다.
- 아무 깊이의 `package.json`(node_modules 제외)의 dependencies·devDependencies에 astro, react, vite, next, vue, svelte, `@sveltejs/kit`, solid-js, preact, nuxt, `@remix-run/react` 중 하나
- `*.astro`, `*.tsx`, `*.jsx`, `*.vue`, `*.svelte` 파일

예: vitrine → `web/package.json: react, vite` + tsx 7개로 감지된다.
같은 실행에서 quad(`docs/site/package.json: astro`)와 devplorer(`docs/package.json: astro`)도 web으로 함께 감지됐다(luau + web 두 툴킷).

## 검사

| 코드 | 등급 | 내용 |
|---|---|---|
| `WEB-PLUGINS` | 정보 | security-guidance, frontend-design, context7, claude-security 가 project·local·user `enabledPlugins` 어디에도 없으면 하나씩 추천한다. 설정 안내는 메시지에 있다. |

`web-security` 는 기본 꺼짐 팩이라 `PACK-MISSING`(항목 7, `scripts/pack_checks.py`)이 맡는다.

판정: 추천일 뿐이다. 공유 worktree 저장소는 security-guidance 에 `ENABLE_STOP_REVIEW=0` 을 더한다. 이미 다른 방식(로컬 마켓 등)으로 켜져 있으면 무시한다.
