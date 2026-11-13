# web-security 동작 상세

구성: 경로 한정 규칙 하나(`rules/web-security.md`), 스킬 하나(`skills/hardening/`), coderag 팩 매니페스트(`coderag.toml`). 훅은 없다. 도메인 팩 공통 구조는 저장소의 `packs/README.md`.

## 켜는 길
- 플러그인은 `"defaultEnabled": false` 라 어디서도 저절로 켜지지 않는다.
- 저장소 `coderag.toml` 에 `[[packs]] name = "web-security"` 를 적고 `coderag adapt --harness claude` 를 돌리면 `.claude/settings.json` 의 `enabledPlugins` 에 `"web-security@claude-doctor-market": true` 가 생긴다(명시한 `false` 는 덮어쓰지 않는다). 이것으로 스킬이 실린다.
- coderag 는 팩 이름을 사용자 설정(`~/.coderag/coderag.toml`, 또는 `$CODERAG_HOME`)의 `[[packs]] name = "web-security"`, `path = "<이 폴더>"` 로 찾는다. 등록되지 않은 이름은 조용히 건너뛰므로 `/q:doctor` 가 알린다.

## 규칙 주입
- coderag 플러그인의 PostToolUse(`coderag hook post-tool`)가, 프로젝트가 이 팩을 나열했을 때만 맞는 파일의 Read·Edit·Write 뒤에 `<rule plugin="web-security" ...>` 로 감싸 한 번 싣고 compact 뒤 다시 싣는다.
- 대상(`paths:`): `*.ts`, `*.tsx`, `*.js`, `*.jsx`, `*.mjs`, `*.cjs`, `*.astro`, `*.go`, `Caddyfile`, `*.caddy`, `nginx*.conf`, `*.nginx`, `Dockerfile`, `*.Dockerfile`, `compose*.y*ml`, `docker-compose*.y*ml`, `*.sh`.
- 본문: 영어 약 20줄, 각 줄이 체크리스트 references 를 가리킨다.
- 팩에 `hooks/` 를 두지 않는다. 두면 같은 규칙이 두 번 실린다.
- 끄기: 환경 변수 `CODERAG_RULES=off` 는 모든 팩의 규칙 주입을 끈다. 이 팩만 끄려면 저장소 `coderag.toml` 의 `[[packs]]` 줄을 지운다.

## hardening 스킬
`skills/hardening/SKILL.md` 가 상황별 라우팅을 하고, `references/` 에 영역별 체크리스트가 있다: auth-gates, client-identity, browser-and-origin, paths, injection, outbound-connections, secrets, resource-limits, supply-chain, state-changes, privileges, verification, 그리고 원칙 해설 principles. coderag 는 `coderag.toml` 의 `[[contexts.knowledge]]` 로 이 스킬을 지식 모듈로 색인한다.

## 테스트
```bash
timeout 120 python3 -I packs/web-security/tests/test-web-security.py </dev/null
```
대상 파일에 이 팩의 규칙만 세션당 한 번 실리는지, 첫 편집 뒤 대조 문장, 다른 경로와 Luau 파일·건너뛰는 폴더에서는 조용한지, `CODERAG_RULES=off`, 팩에 `hooks/hooks.json` 이 없는지, 체크리스트 파일과 매니페스트를 본다. 주입 시험은 coderag 바이너리가 있어야 돌고, 없으면 건너뛴다. 상태는 임시 `CODERAG_HOME`·`CODERAG_CACHE` 로 격리한다.
