# 6·7. 복제본 표류와 설정

## 목차
- [6. 복제본 표류](#6-복제본-표류)
  - [훅 중복](#훅-중복)
  - [위임 사본](#위임-사본)
- [7. 설정](#7-설정)
  - [도메인 팩](#도메인-팩)

## 6. 복제본 표류

같은 파일을 "복사 후 방치"하면 사본마다 다른 수정이 쌓인다.

| 코드 | 대상 | 정본 |
|---|---|---|
| `DRIFT-TYPEDEFS` | (툴킷 luau) `globalTypes*.d.luau` | luau-kb `typedefs/globalTypes.d.luau` — `toolkits/luau.md#typedefs-사본` |
| `DRIFT-HOOK` | `heavy-proc-guard.py` 사본 | `<doctor>/plugins/qwreey-proc-guard/hooks/heavy-proc-guard.py` |
| `DRIFT-HOOKDUP` | 사용자 레벨과 같은 훅을 프로젝트 settings가 또 등록 | 사용자 레벨 `settings.json` |
| `DRIFT-DELEGATE` | `agy-delegate.sh`, `skills/delegate-agy` 사본 | `<doctor>/plugins/qwreey-delegate/` (초안: `<doctor>/.claude/scopes/plugins/qwreey-delegate/research/drafts/delegate/`) |
| `DRIFT-UID` | 서로 다른 저장소가 같은 위임 uid를 쓴다. 저장소 안의 사본과 `harness.env`의 `HARNESS_DELEGATE_REGISTRY`(uid 표)를 함께 본다 | uid 표 |
| `DRIFT-SKILLCOPY` | 같은 이름 스킬이 다른 저장소나 사용자 레벨에 있는데 내용이 다르다 | 원본 쪽(사례마다 확인) |

같은 git 저장소의 다른 worktree(stl-luau ↔ stl-luau-doctor)는 사본으로 치지 않는다.

**모델이 볼 것**
- 언어 고유 사본(luau의 typedefs)은 툴킷 문서의 판정 기준을 따른다.
- 정본과 같은 사본은 지금 고칠 것이 없다. 참조로 바꾸는 일은 P5 범위다.

### 훅 중복

프로젝트 settings가 사용자 레벨과 같은 훅을 등록하면 훅이 두 번 돈다. 차단 메시지나 리마인더도 두 번 나온다.
- 사례: table-sim `.claude/settings.json`의 PreToolUse `heavy-proc-guard.py`
- **고치는 법**
  1. `tools/home-sync.sh status`로 사용자 레벨 훅이 실제 `~/.claude`에 반영됐는지 확인한다.
     - 반영 전이면 프로젝트 쪽을 걷지 않는다. 훅이 0개가 된다.
  2. 반영됐으면 프로젝트 `settings.json`에서 해당 hooks 항목을 걷는 안을 낸다. 설정 편집이라 승인이 필요하다.
  3. 남는 훅 파일(`.claude/hooks/heavy-proc-guard.py`)의 삭제는 HUMAN_TODO로 올린다.

### 위임 사본

agy 위임 도구는 4벌이다(quad, stl-luau, tbox, table-sim). 지금은 고치지 않는다.
- 통합안과 걷어내기 순서는 `<doctor>/.claude/scopes/plugins/qwreey-delegate/research/drafts/delegate/README.md`와 `migration.md`에 있다.
- uid 충돌(`DRIFT-UID`)은 격리 보장을 깨므로 보고에 꼭 넣는다. 사례: quad와 tbox가 모두 61000.
  - 고치는 일은 P4 통합 때 한다. 대상 저장소에 세션이 있으면 인계한다.
- `DRIFT-SKILLCOPY`는 어느 쪽이 정본인지부터 확인한다. CLAUDE.md의 "사본" 서술과 git log를 본다.
  - 사본 갱신은 사본을 가진 저장소의 일이다. 그 저장소에 세션이 있으면 인계한다.

## 7. 설정

| 코드 | 뜻 | 처리 |
|---|---|---|
| `SET-JSON` | settings 파일이 JSON으로 읽히지 않는다 | 오류. 고칠 안 |
| `SET-HOOKPATH` | 훅이 가리키는 스크립트가 없다(`$CLAUDE_PROJECT_DIR` 풀어서 확인) | 오류. 경로를 고치거나 훅 항목을 걷는다 |
| `SET-PUSHDENY` | `git push` deny가 있다 | 정보. 환경 정책(`HARNESS_AGENT_PUSH`)에 따라 다르다(아래) |
| `SET-BROADALLOW` | `Bash(sed/cp/mv/curl/python3/…:*)` allow가 있다 | 읽기 전용만 남기는 안 |
| `SET-LOCALIGNORE` | `settings.local.json`이나 `.claude/harness.local.env`(개인 harness 층)가 git에서 무시되지 않는다 | `.gitignore` 한 줄 |
| `SET-WTIGNORE` | 경고: `.claude/worktrees/`가 무시되지 않는다. 정보: `.git/info/exclude`(이 기기 전용)로만 무시한다 | `.gitignore`에 `/.claude/worktrees/` 한 줄 |
| `SET-UNTRACKED` | `.claude/`와 CLAUDE.md가 한 번도 커밋되지 않았다 | 사용자 결정 → HUMAN_TODO |
| `SET-DIRTY` | 에이전트 문서에 미추적이나 미커밋 변경이 있다 | 정보. 세션이 작업 중일 수 있다 |
| `SET-NOGIT` | 경고: git 저장소가 아니다. 정보: 다른 저장소 안의 하위 디렉터리다(반입 사본 `intake/<이름>/`이면 정상, git 기반 검사는 건너뜀) | 반입 사본이면 없음 |

**판단 근거**
- **push deny**: 정책은 환경마다 다르다. `harness.env`의 `HARNESS_AGENT_PUSH`를 본다.
  - `normal`(이 sandbox): git 계정이 에이전트 전용이라 에이전트 push가 정상 흐름이고, 사용자가 pull해서 업스트림에 올린다. push deny를 권하지 않고, 걷는 것도 사용자 판단이다. `<doctor>/HUMAN_TODO.md` "권한" 절에 이미 있는지만 확인한다.
  - `deny`: deny가 정책과 맞다. 고칠 것이 없다. 값이 없으면 사용자에게 묻는다.
- **`.gitignore` 보강**: 실행 중인 세션이 있는 저장소에서는 보류한다(claude-doctor `.claude/base/harness-principles.md`). 그런 저장소는 인계 문서에 넣는다.
- **미커밋 문서**: 에이전트가 대신 커밋하지 않는다. 사례: moonwave-luau의 `.claude/`가 한 번도 커밋되지 않았다.
- **넓은 allow**: `fewer-permission-prompts` 스킬처럼 실제로 쓰인 읽기 전용 명령만 남기는 안을 낸다.

**모델이 볼 것**
- `settings.local.json`에 공유할 설정(훅, deny)이 숨어 있지 않은지 본다.
- 훅의 matcher가 의도와 맞는지 본다. 예: `Bash` 대신 `*`를 쓰고 있지 않은지.
- 사용자 레벨로 올릴 만한 공통 설정이 있으면 `<doctor>/home/settings-migrations/` 에 새 마이그레이션을 추가하는 안을 낸다.
- 훅 명령의 경로는 `$HOME/.claude/hooks/…`나 `$CLAUDE_PROJECT_DIR/…`로 쓴다. 절대 경로(`/code/...`)는 다른 환경에서 깨진다. scan은 환경 변수를 풀어 `SET-HOOKPATH`를 본다.

### 도메인 팩

팩(`packs/`)은 기본 꺼짐 플러그인이다. 스위치는 저장소 `coderag.toml`의 `[[packs]]` 목록 하나다. coderag 플러그인이 이 목록대로 팩 rule을 주입하고, `coderag adapt --harness claude`가 이 목록에서 `.claude/settings.json` `enabledPlugins`(스킬 적재)를 만든다. 팩 표(팩 → 툴킷)는 `scripts/pack_checks.py`의 `PACKS`다.

| 코드 | 뜻 | 등급 |
|---|---|---|
| `PACK-MISSING` | 툴킷 표식이 있는데 팩이 `coderag.toml` 목록에도 없고 `enabledPlugins`에서 false로 꺼 두지도 않았다. 메시지에 더할 줄과 `coderag adapt --harness claude`가 있다 | 경고 |
| `PACK-DRIFT` | 목록에 있는데 `enabledPlugins`에 없거나 false다, 또는 켜져 있는데 목록에 없다 | 경고 |
| `PACK-UNUSED` | 팩이 켜져 있는데 그 툴킷 표식이 없다 | 정보 |
| `PACK-USER-LEVEL` | 팩이 사용자 레벨 `enabledPlugins`에서 켜져 있다 | 정보 |
| `PACK-NO-CODERAG` | 팩이 켜져 있는데 `HARNESS_CODERAG` 바이너리가 없다. 팩 rule이 주입되지 않는다 | 경고 |
| `PACK-UNREGISTERED` | 목록의 팩이 프로젝트 항목에도 사용자 coderag 설정에도 경로가 없다. coderag가 조용히 건너뛴다 | 경고 |
| `SET-CODERAG-BINARY` | 팩과 무관하게, coderag 플러그인이 켜져 있는데 바이너리가 없다. 기록 규약 rule이 실리지 않는다 | 경고 |

**고치는 법**
- `PACK-MISSING`, `PACK-DRIFT`는 고칠 안이다. 그 저장소 `coderag.toml`을 사용자 승인 뒤 고치고 adapt를 돌린다. 세션이 있으면 `인계`다.
- 팩을 사용자 레벨에서 켜자고 제안하지 않는다. 팩은 저장소마다 켠다.
