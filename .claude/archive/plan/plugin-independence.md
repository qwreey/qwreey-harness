---
format: 1
title: 플러그인 독립 패키지화 (Q28 a, Q29 a)
description: 플러그인은 설치본만으로 동작, 설정은 각자 userConfig(settings.json pluginConfigs 층), HARNESS_WORKSPACE·DOCTOR_ROOT 제거, 저장소 찾기는 lib/known_repos.py 자동 수집
status: landed in .claude/base/harness-principles.md
---

# 플러그인 독립 패키지화

결정: `.claude/archive/plan/decisions/` 의 Q28 a(독립 패키지), Q29 a(자동 수집 + userConfig 로 더하기·빼기). Q27 a(저장소 이름 `qwreey-harness`)는 이 작업 뒤 따로 한다.

사용자 말(2026-11-17):
- "원하는것만 골라서 깔 수 있어요 가 완전 깨지고 하나만 깔더라도 무관한 키들도 포함하는 베이스를 까는것도 뭔가 애매하네"
- "딱 하나의 plugins/*/readme.md 를 보고 필요한걸 까는 구조"
- "doctor root 도 이상한것 같고 harness workspace 도 좀 그래. 윈도우면 문서함에 프로젝트가 있기도, desktop 에 프로젝트가 있기도 다 다르고"
- "플러그인도 지금처럼 임시 설치가 아니라 pack된게 진짜 깔리는 구조가 되는게 맞겠는데"
- userConfig 를 두고 harness.env 를 쓰는 것이 "공개하기에 애매한 단계처럼 보이기도"

## 원칙

- 플러그인은 자기 폴더(`CLAUDE_PLUGIN_ROOT`, 또는 스크립트 위치에서 찾은 플러그인 루트), `CLAUDE_PLUGIN_DATA`, `CLAUDE_PROJECT_DIR`, Claude Code 자신의 파일(`~/.claude/settings.json`, `plugins/*.json`, `projects/`)만 본다. 이 저장소의 클론 위치, 작업공간 폴더, 다른 플러그인 설치 여부에 기대지 않는다.
- 다른 플러그인이 있으면 쓰는 것(예: luau-kb 팩 스킬 안내)은 있을 때만 하고, 없으면 조용히 생략한다.
- 사람이 고르는 값은 그 플러그인의 `userConfig` 에 둔다. 묶음 플러그인, 기반 플러그인은 두지 않는다.
- harness.env 는 남되 고급용 선택 파일이다: 저장소 층(`.claude/harness.env`, `harness.local.env`)과 튜닝 값. 없어도 모든 플러그인이 기본값으로 돈다.
- 저자 개발은 지금처럼 로컬 폴더 마켓(저장소에서 바로 실림)으로 한다. 동료는 GitHub 마켓에서 설치본(cache 사본)을 받는다. 그래서 출시 전에 설치본과 같은 조건(저장소 밖 사본)에서 훅을 돌려 본다.

## 설정 층 (harness_env.py)

정본 `home/.claude/lib/harness_env.py`, 사본은 `tools/sync-copies.py --apply`.

실측(2026-11-17, Claude Code 2.1.316, 격리 `CLAUDE_CONFIG_DIR`): `claude plugin configure uc@ucmkt --values-stdin` 뒤 `settings.json` 은
`{"pluginConfigs": {"uc@ucmkt": {"options": {"reply_language": "한국어", "enabled": false, "mode": "warn", "extra_repos": "a,b"}}}}`.
boolean 은 JSON boolean 으로 저장된다. 설정하지 않은 옵션은 저장되지 않는다(기본값은 plugin.json 에만 있다). `--values-stdin` 은 문자열 값만 받고 `multiple` 에도 문자열이 그대로 들어갔다.

층(낮은 것부터, 키마다 높은 층이 이긴다):
1. 코드 기본값(`DEFAULTS` + 호출자 `defaults`)
2. 사용자 `~/.claude/harness.env`(또는 `$HARNESS_ENV`)
3. 플러그인 옵션(새 층): `<config_dir>/settings.json` 의 `pluginConfigs["<플러그인 이름>@<아무 마켓>"].options`. 여러 마켓에 같은 이름이 있으면 `enabledPlugins` 에서 true 인 것. `/config` 에서 고친 값이 사용자 harness.env 보다 이긴다.
4. 저장소 층 `.claude/harness.env` < `.claude/harness.local.env` (USER_ONLY 키는 건너뜀, 지금과 같음)
5. 프로세스 환경 변수

규칙:
- 옵션 키 = 읽는 환경 변수 이름의 소문자(`harness_reply_language` -> `HARNESS_REPLY_LANGUAGE`). 표가 필요 없고, 테스트가 맞춤을 본다.
- 값 변환: boolean true/false -> `on`/`off`, 숫자 -> 문자열, 목록 -> `;` 로 잇기. 여러 경로를 받는 옵션은 `type: string` 에 `;` 구분(Windows 경로의 `:` 와 겹치지 않음). `multiple` 은 `/config` 줄에 안 나와 쓰지 않는다.
- 플러그인 이름: 사본 파일 위치에서 위로 올라가 처음 만나는 `.claude-plugin/plugin.json` 의 `name`(최대 5단계). 못 찾으면(예: `~/.claude/lib` 설치본, statusline) 이 층이 없다.
- plugin.json 의 `userConfig` 에 선언된 키만 읽는다(남은 찌꺼기 무시).
- `CLAUDE_PLUGIN_OPTION_*` 환경 변수는 쓰지 않는다: Bash 로 부르는 스크립트에는 들어가지 않고, 기본값이 섞여 들어오는지 확인되지 않았다. settings.json 하나로 훅과 스크립트가 같은 값을 본다.
- 관리 설정(managed settings)의 pluginConfigs 는 읽지 않는다(이 하네스 대상이 아님). 머리 주석에 한 줄.
- userConfig 의 `default` 는 코드 기본값과 같아야 한다(테스트).

`DEFAULTS`·`USER_ONLY` 에서 `HARNESS_WORKSPACE`, `HARNESS_DOCTOR_ROOT` 를 뺀다. `HARNESS_WORKSPACE` 는 known_repos 의 추가 출처로만 읽는다(아래). `HARNESS_DOCTOR_ROOT` 는 저자 도구가 환경 변수로만 받는다.

## 저장소 찾기 (lib/known_repos.py, Q29)

새 정본 `lib/known_repos.py`(파일째 사본). qwreey-workspace 와 qwreey-conventions 가 쓴다.

출처(합집합, 그다음 제외):
1. `<config_dir>/projects/*/*.jsonl` 의 `cwd`: 프로젝트 폴더마다 가장 최근 파일 하나의 앞부분(수십 줄)만 읽는다. cwd 에서 위로 올라가 `.git`(폴더 또는 파일)이 있는 곳을 저장소 루트로. worktree(`.git` 이 파일이고 `gitdir:` 가 다른 저장소의 `.git/worktrees/` 를 가리킴)는 본 저장소로 합친다. 없어진 경로는 뺀다.
2. 옵션 `harness_workspace_extra`(qwreey-workspace userConfig, `;` 구분): 저장소 경로 또는 그 아래 한 단계 자식 저장소를 모두 넣을 폴더.
3. 사용자 harness.env 의 `HARNESS_WORKSPACE`(있으면): 그 아래 한 단계 자식 저장소. 옛 설정 호환이며 문서에는 고급용으로만.
4. 제외 `harness_workspace_exclude`(`;` 구분 경로 또는 glob).

캐시: 결과를 `$CLAUDE_PLUGIN_DATA/known_repos.json`(없으면 캐시 없음)에 두고 `projects/` 폴더들의 mtime 과 옵션 값이 같으면 다시 쓴다. 매 Edit/Read/Bash 마다 도는 훅이 쓰므로 캐시 적중 때 수 ms, 첫 수집도 수백 ms 안이어야 한다(측정해서 보고).

쓰는 곳:
- 쓰기 게이트(`workspace_gate.py`): 목록 없이 판정한다. 대상 경로가 `CLAUDE_PROJECT_DIR`(와 그 저장소의 worktree) 밖이고, 위로 올라가 `.git` 을 만나면 "다른 저장소". 지금의 게이트 동작(스킬을 싣기 전 쓰기 거부 등)은 그대로.
- 지도(`map.py`), stale worktree 알림, sibling_notice, conventions reuse-check 의 `<저장소>:<경로>` 풀기: known_repos 목록. reuse-check 는 이름이 겹치면 현재 프로젝트의 부모 폴더 안 것을 먼저, 없으면 known_repos.

## 작업 나누기

순서: L 먼저, 병합한 뒤 A·B·C·D 병렬(각자 worktree), 그다음 main 이 병합·스냅숏·문서.

**L. 공유 기반** (opus 1)
- harness_env 플러그인 옵션 층, DEFAULTS·USER_ONLY 정리, `lib/known_repos.py`, 사본 목록(`tools/tests/test-vendored-copies.py` 의 EXPECTED), `sync-copies --apply`.
- 테스트: `tools/tests/test-harness-env.py`(층 순서, 변환, 이름 찾기, 선언 안 된 키 무시), 새 `tools/tests/test-known-repos.py`(가짜 projects/ 트리, worktree 합치기, extra/exclude, 캐시), 새 `tools/tests/test-plugin-userconfig.py`(모든 plugin.json 의 userConfig: 키 소문자 = 그 플러그인이 읽는 키, default = 코드 기본값, 필수 필드, `claude plugin validate` 가 PATH 에 있으면 각 플러그인 통과).
- 설치본 조건 시험: `tools/tests/hook_sandbox.py` 에 `HOOK_SANDBOX_PLUGIN_COPY=1` 이면 `plugins/` 를 임시 폴더(저장소 밖)로 복사하고 `CLAUDE_PLUGIN_ROOT` 를 사본으로 둬서 `test-hook-replay.py` 를 돌리는 모드. 지금 실패하는 사례를 목록으로 보고(A·B·C·D 가 고칠 대상).

**A. qwreey-workspace** (opus 1): known_repos 로 바꾸기, 게이트 판정 규칙, userConfig(`harness_workspace_extra`, `harness_workspace_exclude`, 게이트·알림 스위치), SKILL.md·ambient·README·docs 의 HARNESS_WORKSPACE 안내 고치기.

**B. q, home, 저자 도구** (opus 1): `/q:doctor` 정본 검사(설치 어긋남, home 대조, web 툴킷의 CANON_HOME)는 `CLAUDE_PROJECT_DIR` 이 하네스 저장소(`home/MANIFEST` 와 `.claude-plugin/marketplace.json`)일 때나 환경 변수 `HARNESS_DOCTOR_ROOT` 가 있을 때만; 스크립트 위치로 저장소를 짐작하지 않는다. `HARNESS_CODERAG` 기본은 PATH 의 `coderag`. q 의 userConfig. `home/.claude/harness.env` 를 고급용 선택 파일로 줄이고(WORKSPACE·DOCTOR_ROOT·DELEGATE_REGISTRY 줄 빼기, 머리에 "보통은 /config" 안내), `home/MANIFEST`, `tools/home-sync.sh`, `tools/settings-migrate.py` 는 자기 위치로 저장소를 안다. statusline 은 `~/.claude/lib` 설치본을 계속 쓴다.

**C. qwreey-conventions, luau-kb 도구** (opus 1): reuse-check 의 `<저장소>:` 풀기를 known_repos 로, structure-reminder 의 luau-kb 위치는 설치된 luau-kb 플러그인(`installed_plugins.json` / 마켓 위치, bash-bypass-reminder 의 `_market_dir` 와 같은 방식)이나 `HARNESS_LUAU_KB` 로만, 둘 다 없으면 생략. conventions userConfig. `packs/luau-kb/tools/upstream_check.py` 의 HARNESS_WORKSPACE 기본값 빼기.

**D. 나머지 플러그인 userConfig** (opus 1): qwreey-sessions, qwreey-advisor, qwreey-operator, qwreey-delegate, qwreey-proc-guard, qwreey-desk, luau-lsp(훅·설정이 있는 것만). delegate 의 `HARNESS_DELEGATE_REGISTRY` 기본은 플러그인 안 사본(읽기용), 바꾸려면 userConfig(경로). `HARNESS_TOOL_INSTALLS` 는 harness.env 고급 키로 남긴다.

userConfig 에 올리는 키의 기준(A~D 공통):
- 올림: 사람이 고르는 값. 켜기·끄기 스위치, 답 언어, 표시 형식, 모델·실행 파일 선택, 사용자가 가진 외부 도구 경로.
- 안 올림: 튜닝 숫자(시간, 크기, 횟수 문턱), 내부 경로, 옛 호환 키. harness.env 고급 키로 남는다.
- 플러그인마다 대개 1~5개. 고르기 애매한 키는 넣지 말고 보고에 적는다.
- `title`, `description` 은 한국어(동료가 보는 대화상자). on/off 두 상태는 `boolean`, 셋 이상은 `string` + `options`.

A~D 공통:
- 각 플러그인 README 카드의 설정 절: `/plugin configure <이름>@<마켓>` 또는 `/config`, 옵션 목록. harness.env 는 "고급" 한 줄로만.
- 바꾼 플러그인은 plugin.json 버전을 올린다(마이너).
- 모델이 보는 글(rule, context/*.md, SKILL.md, 훅 메시지)을 바꿨으면 `python3 -I tools/regen-prompt-surface.py --check` 결과만 보고하고 스냅숏은 커밋하지 않는다(main 이 병합 뒤 한 번 다시 만든다).
- `home/.claude/HOOK-MESSAGES.md` 의 행을 바꿔야 하면 바꾼다(겹치면 main 이 병합에서 푼다).

## 완료 기준

- `git grep -n -E "HARNESS_(WORKSPACE|DOCTOR_ROOT)" -- plugins packs` 가 known_repos 의 옛 설정 호환 한 곳과 문서의 고급 안내만 남는다.
- `HOOK_SANDBOX_PLUGIN_COPY=1 python3 -I tools/tests/test-hook-replay.py` 와 평소 모드 둘 다 통과, `tools/tests/` 와 각 플러그인 `tests/` 전부 통과.
- `test-plugin-userconfig.py` 통과, `claude plugin validate` 가 모든 플러그인에서 통과.
- 실제 설치본 한 번(main): 저장소 클론을 git 마켓으로 격리 `CLAUDE_CONFIG_DIR` 에 더해 설치하고, cache 사본의 훅 하나와 `/plugin configure` 값이 훅에 닿는지 확인.
- 문서(main): `.claude/base/harness-principles.md` 의 툴킷 무관 줄, harness.env 층 줄, "플러그인은 작게 나눈다" 근처에 독립 원칙; `.claude/base/overview.md`; 루트 README 설치 절(GitHub 마켓, 설정은 /config); HUMAN_TODO 갱신 단계.

## 하지 않는 것

- 저장소 이름 바꾸기(Q27)와 마켓 이름 바꾸기: 이 작업 뒤.
- 형제 저장소(coderag 등) 변경.
- 옛 harness.env 키를 읽는 코드를 한꺼번에 지우기: 이 sandbox 가 계속 돌아야 한다. 옛 키는 고급 키로 남는다.
