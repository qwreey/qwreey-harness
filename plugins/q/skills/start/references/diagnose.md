# 읽기 전용 진단 절차

이 단계에서는 **아무것도 쓰지 않는다.** Read, Glob, Grep 과 조회 명령만 쓴다.
비밀은 열지 않는다: `.env*`, `*credentials*`, `*.pem`, `*token*`, `~/.claude.json` 의 값, settings.json 의 `env` **값**(키 이름만 센다).

## 경로 메모
- `~` 는 macOS·Linux 에서 홈, Windows 에서 `%USERPROFILE%` 이다. 환경 변수 `CLAUDE_CONFIG_DIR` 이 있으면 `~/.claude` 대신 그 폴더다.
- **Read·Glob·Grep 을 먼저 쓴다.** 셸 명령은 Manual 모드에서 매번 허락 창을 띄우고(실측), Windows 에서는 셸이 다를 수 있다. 줄 수는 Read 결과의 마지막 줄 번호로 센다. 크기는 대략이면 된다.
- 셸 명령이 꼭 필요하면 한 번에 하나, 읽기만 하는 단순한 형태로 쓴다(여러 명령을 `;` 로 잇지 않는다).
- 지금 프로젝트 = 현재 작업 폴더. git 저장소면 저장소 루트.

## 살펴볼 것 (순서대로, 없는 항목은 "없음" 으로 적고 넘어간다)

| # | 항목 | 어디 | 기준 |
|---|---|---|---|
| 1 | 내 CLAUDE.md | `~/.claude/CLAUDE.md` | 줄 수. 200줄 넘으면 주의 |
| 2 | 프로젝트 CLAUDE.md | `./CLAUDE.md`, `./.claude/CLAUDE.md`, `./CLAUDE.local.md`, `./AGENTS.md` | 각각 줄 수. 200줄 넘으면 주의. `@` 로 불러오는 파일이 있으면 그것도 합산 |
| 3 | 회사 관리 CLAUDE.md | macOS `/Library/Application Support/ClaudeCode/CLAUDE.md`, Linux `/etc/claude-code/CLAUDE.md`, Windows `C:\Program Files\ClaudeCode\CLAUDE.md` | 있는지, 동의 원칙이 이미 들어 있는지. 읽을 수 없으면 "확인 못 함" |
| 4 | rules | `~/.claude/rules/*.md`, `./.claude/rules/*.md` | 개수, 각 파일 맨 위 `paths:` 유무. paths 없는 것은 늘 읽힌다 |
| 5 | auto memory | `~/.claude/projects/*/memory/MEMORY.md` 중 지금 프로젝트에 해당하는 것(폴더 이름 = 프로젝트 경로의 영숫자 아닌 글자를 `-` 로 바꾼 것) | 줄 수, 크기. 160줄 또는 20KB 넘으면 주의, 200줄 또는 25KB 넘으면 문제(뒤가 안 읽힘). 날짜가 지난 "이번 주", "마감" 같은 줄이 있는지 |
| 6 | 설정 | `~/.claude/settings.json`, `./.claude/settings.json`, `./.claude/settings.local.json` | `permissions.defaultMode` 값, allow 규칙 수, `hooks` 의 이벤트 이름과 개수, `enabledPlugins`, `env` 키 개수(값은 보지 않음). `bypassPermissions` 면 문제 |
| 7 | 플러그인 | settings.json 의 `enabledPlugins` 먼저. 더 필요하면 `claude plugin list` (조회 명령, 허락 창이 뜰 수 있음) | 설치·켜짐 목록. luau-kb, q(`q@qwreey-harness`) 유무 |
| 8 | 스킬 | `~/.claude/skills/*/SKILL.md`, `./.claude/skills/*/SKILL.md` | 개수. 30개 넘으면 주의(설명이 늘 읽힘) |
| 9 | subagent 정의 | `~/.claude/agents/*.md`, `./.claude/agents/*.md` | 개수, `model:` 값 |
| 10 | MCP | `./.mcp.json` 의 서버 이름 | 개수, `Roblox_Studio` 류 연결 유무. 다른 범위 설정은 `claude mcp list` (조회 명령) |
| 11 | 사내 하네스 | `~/.claude/harness.env`, `q` 플러그인의 `/q:doctor` 와 `~/.claude/lib/harness_env.py`, `~/.claude/HOOK-MESSAGES.md`, 또는 내 CLAUDE.md 나 맥락의 `<plugin name="q">` 규약이 "정본" 위치를 따로 밝힘 | 하나라도 있으면 `~/.claude` 를 다른 곳(qwreey-harness `home/` 등)에서 관리하는 환경이다 → 고칠 것은 정본 쪽 요청으로 바꾼다. 표의 상태 칸에도 그렇게 적는다 |
| 12 | 작업 폴더 | 현재 폴더 | git 저장소인지(`.git`), 홈·바탕화면·다운로드 같은 넓은 폴더인지 |

## 사용자에게 부탁할 것 (Claude 가 실행할 수 없는 명령)
- `/context` → "가장 큰 항목 세 개만 알려 주세요"
- `/usage` → "무엇이 사용량을 많이 쓰는지 표가 보이면 위 세 줄만"
- 선택: 사내 하네스가 있으면 `/q:doctor --user`

부탁은 한 번만 하고, 사용자가 건너뛰면 그대로 진행한다.

## 보고 형식

```
## 지금 환경 (읽기만 했어요)
| 항목 | 상태 | 지금 | 쉬운 말로 |
|---|---|---|---|
| 내 CLAUDE.md | 좋음 | 45줄 | 짧아서 부담 없어요 |
| 이 프로젝트 메모(MEMORY.md) | 주의 | 182줄 | 곧 200줄이 넘으면 뒷부분이 안 읽혀요 |
| 권한 모드 | 좋음 | auto | 위험한 행동은 검사 모델이 막아요 |
...
가장 먼저 손볼 만한 것: <한 줄>
```

- 상태는 `좋음 / 주의 / 문제 / 확인 못 함` 넷만 쓴다.
- 역할이 비프로그래머면 "지금" 열에 경로 대신 이름만 쓴다.
- 확인 수준을 구분한다. 직접 읽은 것은 그대로, 추정은 "(추정)" 을 붙인다.
- 진단 결과 자체를 파일로 저장하지 않는다(저장하자고 하면 그것도 동의 항목).
