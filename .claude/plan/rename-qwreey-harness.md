---
format: 1
title: 저장소 이름 바꾸기 claude-doctor -> qwreey-harness (S12, Q27 a)
description: 폴더와 마켓 이름을 qwreey-harness 로(Q27 a, Q34 a): 준비는 브랜치에서, 전환은 세션을 모두 닫고 tools/rename-cutover.sh 한 번(폴더, 프로젝트 기록, 데이터 폴더, 설정 키, 마켓), 그다음 확인
status: active
---

# 저장소 이름 바꾸기 (S12)

결정: Q27 a(원격 저장소 이름 `qwreey-harness`, 원격은 이미 `origin` git.qwreey.moe 와 `upstream` GitHub 에 있음). 이 계획은 로컬 폴더 `/code/Projects/claude-doctor` 를 `/code/Projects/qwreey-harness` 로 바꾸는 일이다. 마켓 이름도 `claude-doctor-market` 에서 `qwreey-harness` 로 바꾼다(Q34 a, 사용자: 같이 바꿈).

## 마켓 이름까지 바꾸면 더 붙는 것
- 플러그인 id 가 `<이름>@qwreey-harness` 로 바뀐다: 사용자 `settings.json` 의 `extraKnownMarketplaces`, `enabledPlugins`, `pluginConfigs` 키를 옮기는 새 마이그레이션(값은 그대로).
- 데이터 폴더 `~/.claude/plugins/data/<이름>-claude-doctor-market` 11개를 `<이름>-qwreey-harness` 로 옮긴다(세션별 상태, 캐시). 옛 마켓을 지우기 전에 옮긴다: 지우면서 옛 id 의 데이터 폴더가 지워질 수 있다.
- 옛 마켓 등록 지우기: `claude plugin marketplace remove claude-doctor-market`.
- 형제 저장소 8곳의 `.claude/settings.json` 의 `@claude-doctor-market` 키: 각 저장소 세션에서 `coderag adapt --harness claude` 를 다시 돌린다(이 저장소에서는 읽기 전용).
- 저장소 안 `claude-doctor-market` 43곳(README 설치 줄, 테스트, 문서).

## 준비는 브랜치에서
marketplace.json 의 이름이 바뀐 채로 살아 있는 세션이 `/reload-plugins` 하면 등록과 어긋난다. 그래서 준비는 브랜치 `rename-qwreey-harness` 에서 하고, 전환 때 병합한다.

## 왜 세션을 모두 닫아야 하나
- 마켓이 로컬 폴더 마켓이라 모든 세션의 훅이 `/code/Projects/claude-doctor/plugins/...` 를 직접 부른다. 폴더가 옮겨지면 살아 있는 세션의 훅이 전부 깨진다.
- Claude Code 는 프로젝트 기록과 auto memory 를 경로 이름 폴더(`~/.claude/projects/-code-Projects-claude-doctor/`, 489M)에 둔다. 옮기지 않으면 새 폴더에서 memory 가 비어 시작한다. session-log 저장소(`~/.local/share/session-log/-code-Projects-claude-doctor/`)도 같다.

## 1. 준비 (에이전트, 브랜치 `rename-qwreey-harness`, 세션이 살아 있어도 됨)
1. 저장소 이름 글과 마켓 id 바꾸기(README, CLAUDE.md, `.claude/base/*`, 플러그인·팩 문서, 도구 도움말, 테스트, `marketplace.json`). 스냅숏, `archive/`, research 초안, `plan/decisions`, 기록된 마이그레이션 0001-0009 는 그대로. 이미 있는 옛 이름(`claude-doctor.old-*`, `claude-doctor-history-cleanup`, `-code-Projects-claude-doctor` 데이터 폴더 이름, 백업 폴더, handoff 파일 이름)도 그대로.
2. 문서의 절대 경로 `/code/Projects/claude-doctor` 는 `<qwreey-harness 클론>` 자리표시나 상대 경로로.
3. settings 마이그레이션 `0010-qwreey-harness-market`: 옛 마켓 선언을 지우고 `extraKnownMarketplaces.qwreey-harness` 를 `${HARNESS_DOCTOR_ROOT}` 디렉터리 마켓으로, `enabledPlugins`·`pluginConfigs` 의 `<p>@claude-doctor-market` 키를 값 그대로 `<p>@qwreey-harness` 로(새 op `rename-keys`). 0010 은 home-sync apply 를 돌리는 어느 기계에나 적용된다: 옛 마켓 설치본이 없는 기계(새로 설치)에서는 해가 없고, 옛 설치본이 있는 기계는 전환 스크립트를 쓴다(아직 동료 기계에는 설치되지 않았다).
4. 전환 스크립트 `tools/rename-cutover.sh` 와 테스트, 실제 설정 사본과 가짜 폴더로 리허설.
5. 테스트 전부. 브랜치는 전환 때만 main 에 병합한다(push 도 그 뒤).

## 2. 전환 (사용자, 모든 Claude Code 세션을 닫은 뒤): `tools/rename-cutover.sh`
스크립트는 아직 브랜치에만 있으므로 꺼내서 돌린다. 기본은 무엇을 할지만 보이고 바꾸지 않는다. 막는 조건(실행 중인 `claude` 프로세스, PATH 에 `claude` 없음, 더러운 트리, main 밖 worktree, 옮길 곳에 이미 폴더가 있음)이 있으면 `--apply` 는 아무것도 하지 않고 멈춘다. 중간에 멈춰도 다시 돌리면 끝난 단계를 건너뛴다. 다시 돌릴 때 쓰는 상태(b 도중 표시, g 의 설치 목록과 설정 스냅숏)는 설정 폴더 `~/.claude/.rename-cutover-*` 에 두고 끝나면 지운다. 명령 순서는 HUMAN_TODO 의 "S12 전환".

`/tmp` 에서 무엇을 지워도 되나: 스크립트가 끝난 뒤에는 모두 지워도 된다(스크립트가 쓰는 임시 폴더는 끝날 때 스스로 지우고, 다시 돌리기용 상태는 `/tmp` 밖이다). 다만 스크립트를 `/tmp` 에 꺼내 두었으면 돌기 전이나 도는 중, 다시 돌리기 전에 `/tmp` 를 비우지 않는다. 그래서 `~/rename-cutover.sh` 로 꺼내고 확인이 끝나면 지운다. `/tmp/claude-*`, `/tmp/cc-daemon-*` 는 살아 있는 세션의 것이라 모든 세션을 닫은 지금만 지운다.

스크립트가 하는 일(순서대로):
- a. 브랜치를 main 에 병합(fast-forward, main 이 움직였으면 merge, 충돌이면 멈춤).
- b. `plugins/qwreey-conventions/hooks/reply_language.py` 껍데기를 `git rm`, 그 HUMAN_TODO 줄과 함께 커밋. 커밋까지 못 가면(예: pre-commit 훅) `git reset --hard HEAD` 로 되돌리고 멈춘다(사전 검사가 깨끗한 트리를 봤으므로 잃는 것은 b 의 변경뿐). 도중에 끊겨 b 의 파일만 바뀐 채 남으면 다음 실행이 그것을 받아 되돌린 뒤 다시 한다.
- c. `~/.claude/plugins/data/<p>-claude-doctor-market` 를 `<p>-qwreey-harness` 로(옛 마켓 remove 가 옛 id 의 데이터를 지우기 전에).
- d. `mv /code/Projects/claude-doctor /code/Projects/qwreey-harness`.
- e. `~/.claude/projects/-code-Projects-claude-doctor`(기록, auto memory)와 session-log 저장소 `-code-Projects-claude-doctor` 를 `-code-Projects-qwreey-harness` 로, session-log `project.json` 도 새 경로로.
- f. 새 위치에서 `tools/home-sync.sh diff`, `apply`(0010 적용).
- g. 첫 실행에서 `settings.json`, `plugins/installed_plugins.json`, `plugins/known_marketplaces.json` 을 `*.bak-<시각>` 으로 백업하고 `enabledPlugins`·`pluginConfigs` 의 `@qwreey-harness` 항목(0010 뒤 값)을 스냅숏으로 남김. `claude plugin marketplace remove claude-doctor-market`, `claude plugin marketplace add /code/Projects/qwreey-harness`, 옛 마켓에 설치돼 있던 플러그인을 `<p>@qwreey-harness` 로 install, 바뀐 `@qwreey-harness` 항목을 스냅숏 값으로 되돌림(꺼 둔 플러그인이 켜지지 않고 없던 팩 키가 생기지 않게), `claude plugin marketplace list`. install 하나가 실패해도 나머지와 되돌리기까지 하고 멈추며, 다시 돌리면 같은 스냅숏을 기준으로 쓴다.
  - 실측(2.1.316, 버리는 설정 폴더): `marketplace remove` 는 그 마켓의 설치본을 uninstall 하며 `<p>@<마켓>` 의 `enabledPlugins`·`pluginConfigs` 키, `extraKnownMarketplaces` 항목, `plugins/data/<p>-<마켓>` 을 지운다(캐시는 남김, 다른 마켓 것은 그대로). `marketplace add` 는 선언을 같은 값으로 쓴다. `install` 은 `enabledPlugins` 를 덮고(기본 꺼짐 팩은 false, 아니면 true, 사용자가 끈 값도) `pluginConfigs` 와 데이터 폴더는 두며, 어느 명령도 claude 프로세스를 남기지 않았다.
- h. `~/.coderag/coderag.toml` 의 팩 `path` 줄을 백업 뒤 새 경로로. 지울 것(`claude-doctor.old-*`, `~/.local/share/claude-doctor-history-cleanup`, `~/.claude/plugins/cache/claude-doctor-market`, 선택으로 `/tmp/claude-*`), 옛 경로를 가리키는 `~/.claude/dev-mods/*/qwreey-desk` 링크(지난 세션 것, 지워도 됨), `~/.claude.json` 의 `projects["/code/Projects/claude-doctor"]`(새 폴더에서 신뢰 대화가 한 번 뜬다), 플러그인 데이터 캐시에 남은 옛 경로(workspace `known_repos.json` 은 스스로 다시 모은다), 형제 저장소의 `coderag adapt --harness claude`, settings.json 에 남은 옛 경로 글(autoMode 설명)은 보이기만 한다.

## 3. 확인 (새 폴더에서 새 세션)
- `/reload-plugins` 출력이 `re-read from its folder: plugins/...` 이고 훅 오류가 없다. `claude plugin list` 의 id 가 `@qwreey-harness` 이고 `tools/home-sync.sh status` 가 settings 를 모두 적용(0010 포함)으로 보인다.
- auto memory(MEMORY.md 목록)가 실린다. session-log 의 인계 알림이 뜬다.
- `python3 -I tools/tests/` 전부, `HOOK_SANDBOX_PLUGIN_COPY=1 python3 -I tools/tests/test-hook-replay.py`.
- `git remote -v` 가 그대로, `git status` 깨끗.
- 위임: 저장소 키가 폴더 이름에서 오므로 새 키로 시작한다. 옛 키의 결과는 `gc` 가 14일 뒤 지운다.

## 하지 않는 것
- 형제 저장소(quad, vitrine 등)의 문서·기록에 남은 `claude-doctor` 경로: 읽기 전용이라 그대로 둔다. 그 저장소들의 설정 키는 각 세션에서 `coderag adapt`(HUMAN_TODO).
