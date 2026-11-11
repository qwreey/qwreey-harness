# HUMAN_TODO — 사용자가 직접 처리할 일

에이전트가 하지 않기로 한 일만 모았다. 삭제, 권한, 다른 세션 소관이 여기 해당한다. 처리했으면 줄을 지운다.

## 삭제와 정리 (사용자 승인 사항, 에이전트는 하지 않음)
- [ ] 옛 agy 대화 기록 `.home` 4개, 약 640MB
  - 위치: `/code/Projects/{quad,stl-luau,table-sim,tbox}-agy/.home`
  - 크기: 117M, 260M, 228M, 31M
  - 근거: `drafts/delegate/migration.md`
- [ ] quad-agy 의 옛 worktree `naming-1021e` 와 브랜치 `agy/naming-1021e`
  - quad 에 세션이 없을 때 처리한다: `git -C /code/Projects/quad worktree remove ...`
- [ ] devplorer 에 남은 `worktree-agent-*` 브랜치 21개
  - worktree 는 정리했고 브랜치만 남았다. 병합 안 된 커밋이 있는 것은 3개다(a57ad6177, a7fc852ac, af9044628).
- [ ] 백업 `/code/backups/claude-doctor-2026-11-10/` (248MB)
  - 내용: 정리한 worktree 와 quad-changelog-check 의 tgz
  - 확인한 뒤 지운다. quad-changelog-check 의 미커밋 CHANGELOG 수정은 `quad-changelog-check.CHANGELOG.diff` 에 있다.
- [ ] `quad/.claude/worktrees/` 14GB
  - quad 세션이 쓰고 있었다(lock). 그 세션이 끝난 뒤 정리한다.
- [ ] `/code/Projects/stl-luau-doctor` worktree
  - stl-luau 세션이 `doctor/diet` 를 반영하고 나면 지운다: `git -C /code/Projects/stl-luau worktree remove ../stl-luau-doctor`

- [ ] 훅을 플러그인으로 옮긴 뒤 `~/.claude` 에 남는 옛 파일(home-sync 는 MANIFEST 에서 빠진 파일을 지우지 않고 status 가 고아로 보고만 한다). apply 와 마이그레이션 0006 뒤에 지운다
  - `~/.claude/hooks/{heavy-proc-guard,bash-bypass-reminder,structure-reminder,memory-placement,subagent-slots,rearm-on-compact}.py`
  - `~/.claude/lib/{compact_epoch,memory_signals,subagent_ledger}.py` (`lib/harness_env.py` 는 남긴다)
  - 옛 훅이 settings 에 남아 있는 채로 파일만 지우면 훅 오류가 나므로 마이그레이션 0006 을 먼저 적용한다
  - **순서**(갱신 전에 apply 하면 그 사이 훅이 없고, 갱신 뒤 apply 전에는 훅이 두 번 돈다):
    1. `claude plugin marketplace update claude-doctor-market`
    2. q, qwreey-advisor, qwreey-conventions 를 갱신하고 qwreey-proc-guard 를 설치한다
    3. `tools/home-sync.sh diff` 로 검토한 뒤 `apply`(0006 이 옛 훅 등록을 걷고 qwreey-proc-guard 를 켠다)
    4. 위 고아 파일을 지운다
    5. 새 세션을 시작한다

## 권한
- [ ] plugin.json 의 license 필드(session-log 는 MIT 로 적혀 있음)와 luau-kb·coderag LICENSE 를 함께 결정 (auto 모드 분류기가 막거나, 사용자 판단 사항)
- [x] rbvm, table-sim 의 프로젝트 settings 에서 `git push` deny 를 뺄지 결정 — **인계로 넘김**(2026-11-11, 사용자 추천대로): `handoff/rbvm.md`, `handoff/table-sim.md`
  - 위치: `rbvm/.claude/settings.json:25`, `table-sim/.claude/settings.json:4`
  - 사용자 레벨 deny 는 이미 뺐다.
- [ ] luau-kb 의 LICENSE 결정
  - `claude plugin validate` 부가 검사가 LICENSE 와 아이콘이 없다고 알렸다.

- [ ] audit/16 §7 의 승인 대기 실측 5건(security-guidance, frontend-design, context7, claude-security, LSP·session-report)
  - auto 분류기가 외부 코드 실행을 거부했다. 허용 규칙을 추가하거나 사용자가 직접 실행해야 한다.
- [ ] codex worktree 모드 사용 여부 결정
  - 이 호스트에서 codex 샌드박스가 bwrap 네임스페이스를 만들지 못해 셸 실행이 안 된다.
  - 열려면 `DELEGATE_CODEX_SANDBOX=danger-full-access` 를 써야 한다. 그대로 두면 empty 모드만 쓴다.
- [ ] stl-luau, tbox: `.claude/worktrees` 를 `.git/info/exclude` 로만 무시 중이다. `.gitignore` 로 옮길지 결정한다(각 세션 몫).
- [ ] 세션 기록 실측이 남긴 `~/.claude/projects/-tmp-sl-hookproj-omyV*` 디렉터리 2개 정리
- [ ] 훅 형식 실측이 남긴 `~/.claude/projects/-tmp-hookfmt`, `-tmp-cmp`, `-tmp-effect-*` (6개) 정리
- [ ] 실측용 임시 프로젝트 기록 `~/.claude/projects/-tmp-*` 정리 (2026-11-10 기준 307개; 이번 작업의 claude -p 실측분이 대부분. `ls -d ~/.claude/projects/-tmp-*` 로 확인 후 삭제)
- [ ] 위임 시범의 임시 산출물 `/tmp/dtrial/` 과 `/code/Projects/table-sim-agy/runs/` 정리

## ~/.claude 반영 (정본 → 실제)
- 2026-11-11 17:58 기준 apply 를 마쳤다. `tools/home-sync.sh status` 가 모든 파일을 "같음", settings 를 "4/4 적용"(0001, 0002, 0004, 0005)으로 보인다. 고아도 없다. 켜 둔 플러그인은 q, qwreey-advisor, qwreey-conventions 이고 모두 설치돼 있다.
- [ ] apply 가 남긴 백업 `*.bak-<시각>` 정리(확인한 뒤 직접 지운다)
  - 목록: `ls ~/.claude/*.bak-* ~/.claude/{hooks,lib,rules}/*.bak-*`
  - 지우기: `rm ~/.claude/*.bak-* ~/.claude/{hooks,lib,rules}/*.bak-*`
  - 되돌릴 일이 없다고 확인한 뒤에만 지운다. 현재 19개 있다(2026-11-10 16:00 ~ 2026-11-11 17:58).
- 새 정본 변경(CLAUDE.md, rules, hooks)이 생기면 다시 `tools/home-sync.sh diff` 로 검토하고 `apply` 한다. 이때도 같은 백업이 생긴다.

## 다른 세션에 넘길 것
- [ ] stl-luau 세션에 `handoff/stl-luau.md` 전달
  - 내용: doctor/diet 를 그 세션이 직접 반영하고, todos 를 BI 기준으로 갱신한다.
- [ ] vitrine 세션에 `handoff/vitrine.md` 전달 (웹 플러그인 4개 enabledPlugins 조각, env, CLAUDE.md 한 줄)
- [ ] rbvm 세션(또는 다음 rbvm 작업 때): `const` 금지 규약을 해제한다.
  - 위치: `rbvm/.claude/conventions.md:28-37`
  - 근거: D-01 확정(금지 근거였던 pesde 0.7.3 은 이미 해소)
- [ ] quad 세션에 `handoff/quad.md` 전달 (Relate.luau error level, runshim 정렬, 낡은 주석)
- [ ] table-sim 세션에 `handoff/table-sim.md` 전달 (서버 파일 구조 제안)
- [ ] 각 저장소의 낡은 서술 8건 정정
  - 목록: `decisions/README.md` 끝 "이번에 발견한 낡은 서술"
  - 2026-11-10: 아래 저장소별 정정 파일에 합쳤다. 그 파일들을 전달하면 이 항목도 끝난다.
- [ ] quad 세션에 `handoff/quad.md` 의 "luau-kb 증류에서 나온 정정" 절 전달 (36건: 행동 16, 표현 20. `-O2` 게이트·에러 위치·태깅 지점, type function 제약, alias, 엔진 동작)
- [ ] stl-luau 세션에 `handoff/stl-luau-corrections.md` 전달 (28건: 행동 6, 표현 22. perf-measurements 수치 정정 중심, `handoff/stl-luau.md` 와 별개)
- [ ] tbox 세션에 `handoff/tbox-corrections.md` 전달 (6건: 행동 2, 표현 4. stylua 오염 원인, analyze FFlag 확인 무효)
- [ ] devplorer 세션에 `handoff/devplorer-corrections.md` 전달 (5건: 행동 2, 표현 3. DataStore 예산, weak 표 Instance 수거)
- [ ] rbvm 세션에 `handoff/rbvm-corrections.md` 전달 (4건: 행동 2, 표현 2. 접두 없는 require, 시그널 userdata 신원. 위 `const` 항목 포함)
- [ ] table-sim 세션에 `handoff/table-sim-corrections.md` 전달 (2건: 표현 2)
- [ ] moonwave-luau 세션에 `handoff/moonwave-luau-corrections.md` 전달 (2건: 표현 2)
- [ ] 메인(claude-doctor)이 `handoff/claude-doctor-corrections.md` 반영 (8건: 행동 2, 표현 6. D-01 §2, audit/09 M-05)
- [ ] moonwave-luau 의 `.claude/`, `CLAUDE.md` 가 한 번도 커밋되지 않았다. 커밋할지 결정한다.
