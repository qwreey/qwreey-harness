# web-security

웹·서버·인프라 파일(ts, tsx, js, jsx, mjs, cjs, astro, go, Caddyfile, nginx 설정, Dockerfile, compose, sh)의 보안 규칙을 파일을 열 때 모델에게 싣고, 상황별 체크리스트는 스킬로 필요할 때 불러온다. 툴킷 지식(웹·서버 코드용)이라 나중에 `web-kb` 로 옮겨질 수 있다.

| 구성 | 이름 | 하는 일 |
|---|---|---|
| rule | `rules/web-security.md` | `paths:` 가 맞는 파일에 대한 규칙 본문(닫힌 실패, 허용 목록, 주입, SSRF, 경로, 비밀, 상한, 헤더, 의존성 등 약 20줄) |
| 스킬 | `skills/hardening/` (`web-security:hardening`) | 엔드포인트·인증·프록시·exec·경로·외부 연결 추가나 보안 리뷰 때 불러오는 체크리스트. `references/` 에 영역별 파일(auth-gates, client-identity, browser-and-origin, paths, injection, outbound-connections, secrets, resource-limits, supply-chain, state-changes, privileges, verification)과 원칙 해설(principles) |
| 훅 | `hooks/rules_inject.py` | PostToolUse(Read, Edit, Write, MultiEdit, NotebookEdit). 맞는 파일을 열면 rule 본문을 `<rule plugin=... name=...>` 로 감싸 주입한다. 이 키로 처음인 Edit·Write 뒤에는 "방금 쓴 것을 대조하라" 한 문장을 더한다. 동작 전체는 qwreey-conventions README 의 같은 훅 항목과 같다 |
| 훅 | `hooks/compact_epoch.py` | PreCompact. 이 플러그인 자기 compact 회차를 올려 compact 뒤 rule 을 다시 싣는다 |

`hooks/rules_inject.py`, `hooks/conv_env.py`, `hooks/compact_epoch.py` 는 다른 플러그인의 정본에서 복사한 사본이다(플러그인은 서로 import 하지 않는다). 정본은 각 파일 머리 주석에 있고, 바이트 동일은 `tools/tests/test-vendored-copies.py` 가 검사한다. 고칠 때는 정본만 고치고 복사한다.

끄기: `HARNESS_CONVENTIONS_RULES=off`(환경 변수 또는 harness.env, qwreey-conventions 와 같은 스위치), 저장소 `.claude/conventions.json` 의 `rules_exclude: ["web-security"]`.

## 설치

```bash
claude plugin marketplace add /code/Projects/claude-doctor   # claude-doctor-market
claude plugin install web-security@claude-doctor-market
```

## 테스트
`timeout 120 python3 -I tests/test-web-security.py`
