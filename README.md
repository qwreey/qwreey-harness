# claude-doctor

Claude Code 하네스(사용자 레벨 `~/.claude` 정본, `/harness-doctor` 진단, 감사 에이전트 초안, 규약 합의안)를 관리하는 저장소다.
특정 언어나 sandbox 에 묶이지 않게 짰다. 언어별 검사는 **툴킷**(지금 luau, web 골격), 환경 고유값은 **`home/.claude/harness.env`** 한 곳에 둔다.

| 위치 | 무엇 |
|---|---|
| `home/.claude/` | `~/.claude` 관리 파일의 정본(CLAUDE.md, settings.json, harness.env, hooks/, lib/, skills/harness-doctor). 목록 `home/MANIFEST` |
| `tools/home-sync.sh` | 정본 ↔ 실제 `~/.claude` 동기화(status / diff / apply / pull / env) |
| `home/.claude/skills/harness-doctor/` | 하네스 진단 스킬. 코어 검사 + `scripts/toolkits/<이름>.py` |
| `decisions/` | 저장소 사이 갈린 규약의 합의안(D-xx)과 사용자 결정 현황 |
| `drafts/` | 설치 전 초안(감사 에이전트, 위임, 스타일, 훅) |
| `intake/` | 외부 프로젝트 반입 자리(사본은 git 에서 제외). 절차 `intake/README.md` |
| `audit/` | 조사·감사 보고서. 반입 프로젝트 감사는 `audit/intake/` |
| `PLAN.md`, `HUMAN_TODO.md`, `handoff/` | 작업 계획, 사람이 할 일, 다른 세션 인계 |

## 다른 sandbox 에 설치하기

전제: `git`, `python3`(3.11 이상, `tomllib`), `bash` 4 이상, `jq`. `choom`(util-linux)은 있으면 쓴다.

1. **클론**한다. 작업공간 루트 아래에 두면 기본값이 맞는다.
   ```bash
   cd <작업공간>            # 예: ~/Projects
   git clone <claude-doctor 저장소 URL> claude-doctor
   git clone <luau-kb 저장소 URL> luau-kb   # luau 툴킷을 쓸 때만
   ```
2. **환경 설정**: `home/.claude/harness.env` 를 이 sandbox 값으로 고친다. 키 설명과 기본값은 `home/.claude/lib/harness_env.py` 의 `DEFAULTS`.
   - `HARNESS_WORKSPACE`: 형제 저장소 루트(지우면 claude-doctor 의 부모)
   - `HARNESS_TOOL_INSTALLS`: 툴체인 설치 경로(mise 기본은 `~/.local/share/mise/installs`)
   - `HARNESS_HEAVY_WRAP`: 무거운 실행 래퍼. 메모리를 다른 세션과 공유하지 않으면 빈 값으로 둔다(훅이 아무것도 막지 않는다). 키를 지우면 choom 이 있을 때만 쓴다
   - `HARNESS_DELEGATE_REGISTRY`: 위임 uid 표(위임을 안 쓰면 비움). `HARNESS_AGENT_PUSH`: 에이전트 push 정책(normal / deny)
   - 파일을 커밋하고 싶지 않으면 다른 곳에 두고 `HARNESS_ENV=<경로>` 를 셸 환경에 둔다. 같은 이름의 환경 변수는 파일보다 우선한다.
   - `home/.claude/CLAUDE.md` 의 "이 환경" 절과 형제 저장소 지도도 그 sandbox 에 맞게 고친다(상시 로드 문서라 harness.env 를 읽지 못한다).
3. **확인**: `tools/home-sync.sh env` 로 푼 값을, `tools/home-sync.sh status` 로 링크 대상(`${HARNESS_WORKSPACE}/luau-kb/...`)이 있는지 본다.
   `~/.claude` 대신 다른 곳에 먼저 시험하려면 `CLAUDE_HOME=/tmp/test-home tools/home-sync.sh apply`.
4. **반영**: `tools/home-sync.sh diff` 로 검토한 뒤 `tools/home-sync.sh apply`. 기존 파일은 `*.bak-<시각>` 으로 남는다.
   - 훅 명령은 `$HOME/.claude/hooks/...` 를 쓴다. `CLAUDE_CONFIG_DIR` 로 설정 디렉터리를 옮겼다면 `settings.json` 의 훅 경로를 그에 맞게 고친다.
5. **플러그인 마켓**(luau 툴킷): `claude plugin marketplace add <작업공간>/luau-kb` 후 `claude plugin install luau-kb@luau-kb-market`.
   - 지금 이 sandbox 는 MANIFEST 의 `link skills/luau-*` 심볼릭 링크로 소비한다. 플러그인으로 옮기면 그 링크 줄을 지운다(둘 다 두면 스킬이 겹친다).
6. **진단**: Claude Code 에서 `/harness-doctor --user`, 그다음 `/harness-doctor <저장소>`.
   스크립트만 돌리려면 `python3 -I ~/.claude/skills/harness-doctor/scripts/scan.py --env` 와 `... scan.py <저장소>`.

## 새 언어·툴체인

`home/.claude/skills/harness-doctor/references/toolkits/README.md` 의 "새 툴킷 추가하기"를 따른다.
coderag 의 지식 계층과 같은 구도다: 코어 = global, 툴킷 + `<툴킷>-kb` = pack, 대상 저장소 = project.
