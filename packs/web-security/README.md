# web-security

웹·서버 코드(ts, tsx, js, jsx, mjs, cjs, astro)의 보안 규칙을 파일을 열 때 모델에게 싣는다. 툴킷 지식(웹·서버 코드용)이라 나중에 `web-kb` 로 옮겨질 수 있다.

| 구성 | 이름 | 하는 일 |
|---|---|---|
| rule | `rules/web-security.md` | `paths:` 가 맞는 파일에 대한 규칙 본문(입력 검증, 비밀, SSRF, 헤더, 의존성 등) |
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
