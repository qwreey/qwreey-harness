# web-security

웹·서버·인프라 파일(ts, tsx, js, jsx, mjs, cjs, astro, go, Caddyfile, nginx 설정, Dockerfile, compose, sh)의 보안 규칙을 파일을 열 때 coderag 가 모델에게 싣고, 상황별 체크리스트는 스킬로 필요할 때 불러온다. 툴킷 지식(웹·서버 코드용)이라 나중에 `web-kb` 로 옮겨질 수 있다.

| 구성 | 이름 | 하는 일 |
|---|---|---|
| rule | `rules/web-security.md` | `paths:` 가 맞는 파일에 대한 규칙 본문(닫힌 실패, 허용 목록, 주입, SSRF, 경로, 비밀, 상한, 헤더, 의존성 등 약 20줄) |
| 스킬 | `skills/hardening/` (`web-security:hardening`) | 엔드포인트·인증·프록시·exec·경로·외부 연결 추가나 보안 리뷰 때 불러오는 체크리스트. `references/` 에 영역별 파일(auth-gates, client-identity, browser-and-origin, paths, injection, outbound-connections, secrets, resource-limits, supply-chain, state-changes, privileges, verification)과 원칙 해설(principles) |

rule 은 이 팩이 아니라 coderag 플러그인이 넣는다: 프로젝트 `coderag.toml` 의 `[[packs]] name = "web-security"` 목록에 있을 때, 맞는 파일을 Read·Edit·Write 하면 `<rule plugin="web-security" ...>` 로 감싸 한 번 싣고 compact 뒤 다시 싣는다. 팩에는 훅이 없다(`hooks/` 를 두면 같은 rule 이 두 번 실린다).

끄기: `CODERAG_RULES=off`(환경 변수), 프로젝트 `coderag.toml` 에서 `[[packs]]` 줄 삭제.

## 설치

```bash
claude plugin marketplace add /code/Projects/claude-doctor   # claude-doctor-market
claude plugin marketplace add /code/Projects/coderag         # coderag-market
claude plugin install coderag@coderag-market                 # rule 주입
claude plugin install web-security@claude-doctor-market      # 스킬. 보통 아래 adapt 가 enabledPlugins 로 켠다
```

웹 저장소의 `coderag.toml` 에 아래를 적고 `coderag adapt --harness claude` 를 실행한다.

```toml
[[packs]]
name = "web-security"
```

## 테스트
`timeout 120 python3 -I tests/test-web-security.py </dev/null` (rule 주입 시험은 coderag 바이너리가 있어야 돈다)
