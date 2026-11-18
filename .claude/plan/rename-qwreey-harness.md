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

## 1. 준비 (에이전트, 세션이 살아 있어도 됨, 경로는 아직 그대로)
1. 저장소 이름을 가리키는 글 바꾸기: README, CLAUDE.md, `.claude/base/*`, 플러그인 README·docs·SKILL.md 의 "claude-doctor"(저장소 이름일 때만; 마켓 id `claude-doctor-market` 은 Q34 를 따른다). 지금 `.claude/` 밖 165개 파일, 380곳. 스냅숏(`.claude/audit`, `handoff`, `sessions`)은 고치지 않는다.
2. 절대 경로 `/code/Projects/claude-doctor` 를 상대 경로나 설명으로: `packs/*/coderag.toml`, `packs/luau-kb` 의 참고 문서 10여 곳, `plugins/qwreey-workspace/tests/test_workspace_gate.py`.
3. 새 settings 마이그레이션: `extraKnownMarketplaces.claude-doctor-market.source.path` 를 `${HARNESS_DOCTOR_ROOT}`(home-sync 가 자기 클론 위치로 채움)로 다시 set. 0001 은 이미 적용돼 다시 돌지 않으므로 새 번호가 필요하다.
4. HUMAN_TODO 와 이 저장소 문서의 `/code/Projects/claude-doctor/...` 명령 경로를 새 경로로(사용자가 따라 칠 줄이므로).
5. 테스트 전부, 커밋, origin push.

## 2. 전환 (사용자, 모든 Claude Code 세션을 닫은 뒤)
아래를 `tools/rename-cutover.sh`(기본은 무엇을 할지만 보임, `--apply` 로 실행) 한 번으로 한다. 준비 단계에서 격리된 설정 폴더 사본으로 미리 돌려 본다.
1. 확인: 실행 중인 세션 없음, `git -C /code/Projects/claude-doctor worktree list` 가 main 하나, 실행 중인 위임 없음.
2. 정리(이때만 안전): `/code/Projects/claude-doctor.old-20261117-120431` 과 `~/.local/share/claude-doctor-history-cleanup` 삭제(기록 재작성 5단계), `plugins/qwreey-conventions/hooks/reply_language.py` 껍데기 `git rm` 후 커밋.
3. `mv /code/Projects/claude-doctor /code/Projects/qwreey-harness`
4. `mv ~/.claude/projects/-code-Projects-claude-doctor ~/.claude/projects/-code-Projects-qwreey-harness`
   `mv ~/.local/share/session-log/-code-Projects-claude-doctor ~/.local/share/session-log/-code-Projects-qwreey-harness`
5. 마켓 경로: `cd /code/Projects/qwreey-harness && tools/home-sync.sh diff` 로 새 마이그레이션이 경로만 바꾸는지 보고 `apply`. 그다음 `claude plugin marketplace list` 에서 claude-doctor-market 이 새 경로인지 확인(설정의 출처가 바뀌면 Claude Code 가 다시 읽는다).
6. `~/.coderag/coderag.toml` 의 팩 `path` 두 줄을 새 경로로.
7. (선택) `/tmp` 비우기: 세션이 모두 닫힌 이때만. 살아 있는 세션은 `/tmp/claude-0`(백그라운드 작업 출력), `/tmp/claude-*`(훅의 세션별 상태)를 쓴다.

## 3. 확인 (새 폴더에서 새 세션)
- `/reload-plugins` 출력이 `re-read from its folder: plugins/...` 이고 훅 오류가 없다.
- auto memory(MEMORY.md 목록)가 실린다. session-log 의 인계 알림이 뜬다.
- `python3 -I tools/tests/` 전부, `HOOK_SANDBOX_PLUGIN_COPY=1 python3 -I tools/tests/test-hook-replay.py`.
- `git remote -v` 가 그대로, `git status` 깨끗.
- 위임: 저장소 키가 폴더 이름에서 오므로 새 키로 시작한다. 옛 키의 결과는 `gc` 가 14일 뒤 지운다.

## 하지 않는 것
- 형제 저장소(quad, vitrine 등)의 문서·기록에 남은 `claude-doctor` 경로: 읽기 전용이라 그대로 둔다. 그 저장소들의 설정 키는 각 세션에서 `coderag adapt`(HUMAN_TODO).
