# claude-doctor

Claude Code 하네스(사용자 레벨 `~/.claude` 정본, `/q:doctor` 진단, 감사 에이전트 초안, 규약 합의안)를 관리하는 저장소다.
특정 언어나 sandbox 에 묶이지 않게 짰다. 언어별 검사는 **툴킷**(지금 luau, web 골격), 환경 고유값은 **`home/.claude/harness.env`** 한 곳에 둔다.

| 위치 | 무엇 |
|---|---|
| `home/.claude/` | `~/.claude` 관리 파일의 정본(CLAUDE.md, settings.json, harness.env, lib/harness_env.py, rules/, statusline/. 훅은 플러그인으로 옮겼다. 사용자 호출 스킬은 `q` 플러그인으로 옮겼다). 목록 `home/MANIFEST` |
| `tools/home-sync.sh` | 정본 ↔ 실제 `~/.claude` 동기화(status / diff / apply / pull / new-migration / env). settings.json 은 복사가 아니라 `home/settings-migrations/` 마이그레이션(`tools/settings-migrate.py`) |
| `plugins/q/` | 사람이 치는 명령 플러그인 `q`(`/q:` 만 치면 전부 나온다): `/q:start` 온보딩, `/q:doctor` 진단(코어 검사 + `skills/doctor/scripts/toolkits/<이름>.py`), `/q:away`·`/q:back` 자리 비움, `/q:checkpoint`·`/q:import` 세션 기록. session-log 훅과 서브에이전트 고지·슬롯 훅(원장 `scripts/subagent_ledger.py`) 포함. 이름은 사용자명 qwreey 에서 왔다. 설명 `plugins/q/docs/` 상시 규약(훅 메시지, workspace 불변식)은 q 의 SessionStart·SubagentStart·UserPromptSubmit(보충) 주입(`plugins/q/context/ambient.md`, `<plugin name="q">`)이 싣는다. 사용자 CLAUDE.md 에는 없고 q 를 끄면 같이 빠진다(끄기 `HARNESS_Q_AMBIENT=off`). |
| `plugins/qwreey-advisor/` | 모델이 부르는 독립 검토(별도 플러그인). luau 지식은 `luau-kb` 플러그인 |
| `plugins/qwreey-conventions/` | 코드 주석·모델용 문서 관례(스킬 `comments`, `agent-docs`)와 추가한 줄을 한 줄로 알리는 훅, 구조 한도(`structure-reminder`)·셸 우회 쓰기(`bash-bypass-reminder`)·auto memory 배치(`memory-placement`) 알림 훅. 옛 user-level 훅들을 대체 |
| `plugins/qwreey-proc-guard/` | Linux 전용: 무거운 실행(벤치·퍼저)이 choom 없이 나가면 거절하는 PreToolUse 훅(`heavy-proc-guard`). Windows·macOS 에서는 끈다 |
| `decisions/` | 저장소 사이 갈린 규약의 합의안(D-xx)과 사용자 결정 현황 |
| `drafts/` | 설치 전 초안(감사 에이전트, 위임, 스타일). 끝난 초안은 각 README 첫 줄 `status: landed in ...; not maintained` 로 표시한다 |
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
   - **settings.json 은 덮어쓰지 않는다.** 정본은 `home/settings-migrations/NNNN-<slug>.json`(연산: set/add/remove/delete/hook-upsert/hook-remove, 모두 멱등)이고,
     apply 는 아직 적용 안 한 것만 순서대로 **한 번씩** 적용해 id 를 `~/.claude/.home-sync-migrations` 에 기록한다. 마이그레이션에 없는 값(내가 `/plugin`·`/config` 로 만든 것)은 건드리지 않고,
     적용 뒤 내가 끈 값은 되돌리지 않는다. 실패하면 그 마이그레이션만 되돌린다. `diff` 는 연산별 변경/no-op 과 결과 diff, `new-migration <slug>` 는 빈 파일을 만든다.
     **적용된 마이그레이션은 고치지 않는다.** 한 번이라도 apply 한 id 는 다시 돌지 않으므로, 바꿀 것은 새 번호(0002, 0003 …)로 추가한다. 0001 은 첫 apply 전까지만 고칠 수 있다.
   - **플러그인:** 마이그레이션은 `extraKnownMarketplaces`·`enabledPlugins` 로 "무엇을 켤지" 만 선언한다(공식 배포 방식과 같음). 실제 설치는 Claude Code 가 세션을 시작할 때 한다(사용자 레벨 settings 에서도 확인, 2026-11-11: apply 뒤 새 세션에서 q·qwreey-advisor 이 손으로 설치하지 않았는데 설치되고 쓰였다). `status`/`apply` 끝에 설치 안 된 것과 설치 명령을 보여 준다. 바로 설치하려면 `HOME_SYNC_INSTALL_PLUGINS=1 tools/home-sync.sh apply`.
   - 훅은 플러그인(`q`, `qwreey-advisor`, `qwreey-conventions`, `qwreey-proc-guard`)이 등록하므로 settings.json 에 훅 명령이 없다(옛 user-level 훅 등록은 마이그레이션 0006 이 걷는다). 남는 것은 statusLine 의 `$HOME/.claude/statusline/harness-status.py` 뿐이라 `CLAUDE_CONFIG_DIR` 로 설정 디렉터리를 옮겼다면 그 경로만 고친다. 훅은 사용자 설정을 `$CLAUDE_CONFIG_DIR`(기본 `~/.claude`)에서 읽는다.
5. **플러그인 마켓**(luau 툴킷): `claude plugin marketplace add <작업공간>/luau-kb` 후 `claude plugin install luau-kb@luau-kb-market`.
   - 지금 이 sandbox 는 MANIFEST 의 `link skills/luau-*` 심볼릭 링크로 소비한다. 플러그인으로 옮기면 그 링크 줄을 지운다(둘 다 두면 스킬이 겹친다).
6. **q 플러그인**: `claude plugin marketplace add <claude-doctor 폴더>` 후 `claude plugin install q@claude-doctor-market`(마이그레이션 0002 가 켠다). 옛 `~/.claude/skills/{away,back,harness-doctor}` 는 apply 가 지우지 않는다: `tools/home-sync.sh status` 의 고아 보고를 보고 직접 정리한다.
7. **진단**: Claude Code 에서 `/q:doctor --user`, 그다음 `/q:doctor <저장소>`.
   스크립트만 돌리려면 `python3 -I <claude-doctor>/plugins/q/skills/doctor/scripts/scan.py --env` 와 `... scan.py <저장소>`. 플러그인 캐시에서 돌 때는 `HARNESS_DOCTOR_ROOT`(harness.env)로 이 폴더를 알려야 정본 검사가 켜진다.

## 새 언어·툴체인

`plugins/q/skills/doctor/references/toolkits/README.md` 의 "새 툴킷 추가하기"를 따른다.
coderag 의 지식 계층과 같은 구도다: 코어 = global, 툴킷 + `<툴킷>-kb` = pack, 대상 저장소 = project.
