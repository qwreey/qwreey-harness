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

## 권한 (auto 모드 분류기가 막거나, 사용자 판단 사항)
- [ ] rbvm, table-sim 의 프로젝트 settings 에서 `git push` deny 를 뺄지 결정
  - 위치: `rbvm/.claude/settings.json:25`, `table-sim/.claude/settings.json:4`
  - 사용자 레벨 deny 는 이미 뺐다.
- [ ] luau-kb 의 LICENSE 결정
  - `claude plugin validate` 부가 검사가 LICENSE 와 아이콘이 없다고 알렸다.

- [ ] codex worktree 모드 사용 여부 결정
  - 이 호스트에서 codex 샌드박스가 bwrap 네임스페이스를 만들지 못해 셸 실행이 안 된다.
  - 열려면 `DELEGATE_CODEX_SANDBOX=danger-full-access` 를 써야 한다. 그대로 두면 empty 모드만 쓴다.
- [ ] stl-luau, tbox: `.claude/worktrees` 를 `.git/info/exclude` 로만 무시 중이다. `.gitignore` 로 옮길지 결정한다(각 세션 몫).
- [ ] 위임 시범의 임시 산출물 `/tmp/dtrial/` 과 `/code/Projects/table-sim-agy/runs/` 정리

## ~/.claude 반영 (정본 → 실제)
- [ ] `tools/home-sync.sh diff` 로 검토하고 `apply`
  - 현재 대기 중: luau-kb 스킬 링크 2개(luau-types, luau-verify), CLAUDE.md 갱신(리뷰 시점, 모델 사용 규칙)

## 다른 세션에 넘길 것
- [ ] stl-luau 세션에 `handoff/stl-luau.md` 전달
  - 내용: doctor/diet 를 그 세션이 직접 반영하고, todos 를 BI 기준으로 갱신한다.
- [ ] rbvm 세션(또는 다음 rbvm 작업 때): `const` 금지 규약을 해제한다.
  - 위치: `rbvm/.claude/conventions.md:28-37`
  - 근거: D-01 확정(금지 근거였던 pesde 0.7.3 은 이미 해소)
- [ ] 각 저장소의 낡은 서술 8건 정정
  - 목록: `decisions/README.md` 끝 "이번에 발견한 낡은 서술"
- [ ] moonwave-luau 의 `.claude/`, `CLAUDE.md` 가 한 번도 커밋되지 않았다. 커밋할지 결정한다.
