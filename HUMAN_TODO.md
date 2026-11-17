# HUMAN_TODO — 사용자가 직접 처리할 일

에이전트가 하지 않기로 한 일만 모았다. 삭제, 권한, 다른 세션 소관이 여기 해당한다. 처리했으면 줄을 지운다.

## 삭제와 정리 (사용자 승인 사항, 에이전트는 하지 않음)
- [ ] 공개 전 git 기록 재작성(Q26 a): table-sim 내부 세부·동료 평가 문장·옛 `plugins/q-ui/node_modules` 를 모든 커밋에서 뺀다. 규칙은 저장소 밖 `~/.local/share/claude-doctor-history-cleanup/`(공개하면 안 되는 이름이 들어 있다). (1) 이 저장소의 Claude Code 세션을 모두 닫고 `git worktree list` 가 main 하나인지 본다 (2) 터미널에서 `tools/history-rewrite.sh` 로 한 번 더 검사(사본만 만들고 아무것도 안 바꿈; 남은 말이 있으면 멈추고 줄을 보여 준다) (3) `tools/history-rewrite.sh --apply`: 백업 `~/backup/claude-doctor-pre-rewrite-*.git`, 정리본을 같은 경로에 교체, 옛 저장소는 `claude-doctor.old-*` 로 남김, 옛 해시 -> 새 해시 표를 `.claude/history/` 에 커밋 (4) 새 세션에서 훅이 도는지 보고 main 만 push(옛 클론·백업은 공개 원격에 연결하지 않음) (5) 확인 뒤 `claude-doctor.old-*` 와 규칙 폴더를 지운다. table-sim 의 하네스 파일 경로(`.claude/conventions.md`, `todos.md`, `settings.json`, `mise.toml`)는 하네스 비교라 남겼다; 더 가리려면 규칙에 더한다
- [ ] quad 에 남은 옛 위임 worktree 기록과 브랜치 `agy/naming-1021e`(폴더 `/code/Projects/quad-agy` 는 지웠고 worktree 는 prunable)
  - quad 에 세션이 없을 때: `git -C /code/Projects/quad worktree prune` 뒤 `git -C /code/Projects/quad branch -D agy/naming-1021e`
- [ ] devplorer 에 남은 `worktree-agent-*` 브랜치 21개
  - worktree 는 정리했고 브랜치만 남았다. 병합 안 된 커밋이 있는 것은 3개다(a57ad6177, a7fc852ac, af9044628).
- [ ] 백업 `/code/backups/claude-doctor-2026-11-10/` (248MB)
  - 내용: 정리한 worktree 와 quad-changelog-check 의 tgz
  - 확인한 뒤 지운다. quad-changelog-check 의 미커밋 CHANGELOG 수정은 `quad-changelog-check.CHANGELOG.diff` 에 있다.
- [ ] `quad/.claude/worktrees/` 14GB
  - quad 세션이 쓰고 있었다(lock). 그 세션이 끝난 뒤 정리한다.
- [ ] `/code/Projects/stl-luau-doctor` worktree
  - stl-luau 세션이 `doctor/diet` 를 반영하고 나면 지운다: `git -C /code/Projects/stl-luau worktree remove ../stl-luau-doctor`
- [x] coderag 로 옮긴 기록의 claude-doctor 사본(2026-11-16 사용자 승인으로 지움)(coderag `.claude/audit/` 같은 번호, `.claude/research/coderag-format-and-levels.md`)
  - coderag 쪽 병합과 그 저장소의 `raw/`(gitignore) 를 확인한 뒤: `git rm -r .claude/audit/{37,42,43,44,45,46,47,49,53}-*/ .claude/research/coderag-format-and-levels.md`, 남는 미추적 `raw/` 폴더도 지운다
  - 함께 고칠 것: `.claude/audit/README.md` 의 해당 표·목록 줄과 "moved to coderag" 줄, `.claude/research/README.md` 의 그 줄(`coderag gen && coderag static-gen --dir .claude/audit --dir .claude/handoff`)

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
- [ ] qwreey-conventions 0.4.0 으로 갱신한 뒤 `~/.claude/rules/{comments,agent-docs,code-structure,memory,web-security}.md` 를 지운다(플러그인 `rules_inject` 가 같은 본문을 넣으므로 두 곳에서 로드되는 것을 막는다. 갱신 전에 지우면 그 사이 규칙이 없다). `tools/home-sync.sh status` 에 고아로 보인다
- [ ] luau-kb 는 claude-doctor 의 도메인 팩(`packs/luau-kb`, 기본 꺼짐)이 됐다. 순서: (1) `claude plugin marketplace update claude-doctor-market` (2) 각 Luau 저장소의 `coderag.toml` 에 `[[packs]]` `name = "luau-kb"` 를 적고 `coderag adapt --harness claude` 를 실행한다(저장소별 승인) (3) 켠 뒤 `~/.claude/rules/luau-core.md` symlink 와 `~/.claude/skills/luau-*` 링크를 지운다(옛 luau-kb 저장소를 가리키며 그 저장소는 없어질 예정이다. 켜기 전에 지우면 그 사이 규칙이 없고, 둘 다 있으면 규칙이 두 번 로드된다) (4) 옛 `luau-kb@luau-kb-market` 이 설치돼 있으면 `claude plugin uninstall` 로 지우고 `claude plugin marketplace remove luau-kb-market`. 이 sandbox 에서는 아직 설치·활성화돼 있지 않다

- [x] qwreey-operator 0.3.1(서브에이전트 마무리 규범 한 줄, 백그라운드 작업을 남긴 채 끝나려는 서브에이전트에게 한 번 알리는 SubagentStop 훅 `subagent-bg-tasks`, 끄기 `HARNESS_OPERATOR_SUBAGENT_BG=off`)과 qwreey-advisor 0.4.16(Stop 훅 통과 조건) 갱신: `claude plugin marketplace update claude-doctor-market` 뒤 `claude plugin update qwreey-operator@claude-doctor-market`, `claude plugin update qwreey-advisor@claude-doctor-market`, 그다음 `/reload-plugins` 나 새 세션. `home/.claude/HOOK-MESSAGES.md` 에 Stop 절과 subagent-bg-tasks 행이 더해졌으니 `tools/home-sync.sh diff` 뒤 `apply`
- [x] qwreey-sessions 0.2.0(큰 기록 통째 Read 사전 차단: `.claude/` 스냅숏 폴더·세션 기록을 offset·limit 없이 32KiB 이상 읽으면 deny 하고 부분 읽기 안내, 끄기 `SESSION_LOG_READ_GATE=off`, 크기 `SESSION_LOG_READ_GATE_KB`. 옛 `SESSION_LOG_READ_WARN_KB` 는 없어졌다) 갱신: `claude plugin marketplace update claude-doctor-market` 뒤 `claude plugin update qwreey-sessions@claude-doctor-market`, 그다음 `/reload-plugins` 나 새 세션. `home/.claude/HOOK-MESSAGES.md` 의 records-read 행이 바뀌었으니 `tools/home-sync.sh diff` 뒤 `apply`
- [x] qwreey-sessions 0.3.0(compact 뒤 SessionStart 에 방금 요약된 구간의 사용자 원문, 바뀐 파일, 커밋, 도구 오류, id 를 다시 넣음. 모델 호출 없음, 출력 8,000자 이하, 끄기 `SESSION_LOG_COMPACT_ANCHORS=off`, 크기 `SESSION_LOG_COMPACT_ANCHORS_CHARS`) 갱신: `claude plugin marketplace update claude-doctor-market` 뒤 `claude plugin update qwreey-sessions@claude-doctor-market`, 그다음 `/reload-plugins` 나 새 세션. `home/.claude/HOOK-MESSAGES.md` 에 session-log 닻 행이 더해졌으니 `tools/home-sync.sh diff` 뒤 `apply`

- [x] qwreey-desk 설치(패널 `/desk`): `claude plugin marketplace update claude-doctor-market` 뒤 `claude plugin install qwreey-desk@claude-doctor-market`. 이 세션은 `/code/.claude/dev-mods/394d4744-…/qwreey-desk` 링크(저장소 `plugins/qwreey-desk` 를 가리킴)로 싣고 있으니, 설치한 뒤 새 세션에서는 링크 없이 설치본만 쓴다(둘 다 실리면 도구와 패널이 겹친다). 설치본은 저장 위치가 달라 책상이 비어 시작할 수 있다: 이어 쓰려면 `/code/.claude/plugins/store/` 의 `qwreey-desk_inline-*.json` 을 설치본 이름의 파일로 복사한다(처음 /desk 를 연 뒤 생기는 파일 이름을 확인). 동료에게는 에이전트가 README 를 보고 이득을 설명한 뒤 고르게 한다

- [x] qwreey-conventions 0.10.0(Bash 로 쓴 파일도 추가 줄 검사와 rules 주입: 새 PostToolUse·PostToolUseFailure:Bash 훅 `bash_writes.py`, PreToolUse 의 bash-bypass-reminder 가 쓰기 신호가 있을 때만 스냅숏을 남긴다; comments rule 끝 줄을 어미, 문체, 알림 대응 세 줄로 바꿈; 주석 알림이 스킬 대신 고치는 법을 직접 준다; 주석의 변경 서술(Previously, used to, 예전에는 등)도 이력으로 알림; 모델이 부르던 comments 스킬을 없애고 기존 주석 정리는 사용자 명령 `/qwreey-conventions:comments-cleanup [경로]`, 사람용 참고는 `plugins/qwreey-conventions/docs/comments.md`) 갱신: `claude plugin marketplace update claude-doctor-market` 뒤 `claude plugin update qwreey-conventions@claude-doctor-market`, 그다음 `/reload-plugins` 나 새 세션. `home/.claude/HOOK-MESSAGES.md` 의 bash-bypass-reminder, rules-inject, qwreey-conventions 행이 바뀌었으니 `tools/home-sync.sh diff` 뒤 `apply`

- [x] qwreey-conventions 0.11.0(D11 4: 스킬에만 있던 요구를 훅으로. 사본 표시가 문서 주석·HTML 주석·JSON 처럼 읽히지 않는 자리에 있거나 형제 저장소 꼴이 섞이면 알림, `SKILL.md` description 꼴·모델용 문서의 한국어 줄·플러그인 밖 원장 경로 알림, 모델용 문서 알림이 스킬 대신 고치는 법을 줌; agent-docs rule 에 두 줄을 더하고 포인터 줄을 줄임) 갱신: 먼저 agent-docs rule 문구를 승인하고 병합한 뒤 `claude plugin marketplace update claude-doctor-market`, `claude plugin update qwreey-conventions@claude-doctor-market`, 그다음 `/reload-plugins` 나 새 세션. `home/.claude/HOOK-MESSAGES.md` 는 MANIFEST 밖이라 apply 할 것은 없다
- [x] qwreey-conventions 0.12.0(D13 a: 모델이 부르던 agent-docs 스킬을 없애고 agent-docs rule 끝의 스킬 포인터 줄을 "A repo's own rules win." 한 줄로, 사람용 참고는 `plugins/qwreey-conventions/docs/agent-docs.md`, 기존 모델용 문서 정리는 새 사용자 명령 `/qwreey-conventions:docs-cleanup [경로]`(`comments-cleanup` 은 이제 코드 주석만 본다); code-reuse 스킬 description 을 경계를 넘는 사본·영역·라이브러리 선택으로 좁히고 정책·불변식 표와 `reuse` 설정은 `docs/code-reuse.md` 로; 같은 목록 중복 알림이 스킬 대신 고치는 법을 줌) 갱신: 0.11.0 항목 뒤에 `claude plugin marketplace update claude-doctor-market`, `claude plugin update qwreey-conventions@claude-doctor-market`, 그다음 `/reload-plugins` 나 새 세션. `home/.claude/HOOK-MESSAGES.md` 의 qwreey-conventions reuse 행이 바뀌었지만 MANIFEST 밖이라 apply 할 것은 없다

- [x] luau-lsp 플러그인 설치(LSP 가 luau-kb 팩에서 나와 별도 플러그인 `plugins/luau-lsp` 0.1.0 이 됐다. luau-kb 0.7.0 은 LSP 를 싣지 않는다): `claude plugin marketplace update claude-doctor-market`, luau-kb 가 설치된 곳은 먼저 `claude plugin update luau-kb@claude-doctor-market`(옛 0.6.x 와 luau-lsp 가 함께 실리면 `.luau` 서버가 둘 뜬다), 그다음 `claude plugin install luau-lsp@claude-doctor-market` 와 새 세션. luau-lsp 바이너리는 지금처럼 mise 설치본을 찾아 쓴다. 확인: 프로젝트 폴더에서 `plugins/luau-lsp/launcher/luau-lsp --which`. 동료 배포는 README 의 "바이너리 얻기" 를 보고 고른다
- [x] qwreey-workspace 0.2.0(Q22 a: 규약 한 줄 "형제 저장소의 내부를 이 저장소 기록에 쓰기 전에 의존과 공개 정도를 확인, 모르면 묻기"와, `.claude/` 기록에 형제 저장소 안 경로를 쓰면 한 번 알리는 PostToolUse 훅 `sibling_notice.py`, 끄기 `HARNESS_WORKSPACE_SIBLING_NOTICE=off`) 갱신: `claude plugin marketplace update claude-doctor-market` 뒤 `claude plugin update qwreey-workspace@claude-doctor-market`, 그다음 `/reload-plugins` 나 새 세션. `home/.claude/HOOK-MESSAGES.md` 에 sibling-internals 행이 더해졌지만 MANIFEST 밖이라 apply 할 것은 없다
- [x] qwreey-license 0.1.0 설치(Q25 a: 라이선스 파일을 정본에서 받아 쓰고 대조하는 스킬 `qwreey-license:license`, 훅 없음): `claude plugin marketplace update claude-doctor-market` 뒤 `claude plugin install qwreey-license@claude-doctor-market`, 그다음 `/reload-plugins` 나 새 세션. 동료에게는 README 카드를 보고 고르게 한다
- [ ] Windows 동료 한 명에게 luau-lsp 플러그인 확인을 부탁한다(`plugins/luau-lsp/README.md` 의 Windows 절 1-4번). `.cmd` 런처는 실기기에서 돌려 본 적이 없다

## 읽기 좋은 코드 규약 켜기 (이 기기, 사용자 본인만)
- [ ] 자기 `~/.claude/harness.env` 에 `HARNESS_READABLE_CODE=on` 한 줄을 직접 더한다(플러그인은 2026-11-16 `/reload-plugins` 로 0.10.0 이 실려 있다. 정본 `home/.claude/harness.env` 에는 주석 처리한 예시만 있어 home-sync 로는 켜지지 않는다; 동료 배포에 퍼지지 않게 일부러 그렇게 뒀다). Luau 저장소에서 쓰면 luau-kb(0.6.4)도 켠다. 끄고 싶은 저장소는 `.claude/harness.env` 에 `HARNESS_READABLE_CODE=off`. 확인: `.luau` 나 `.py` 파일을 Read 하면 `<rule plugin="qwreey-conventions" name="readable-code">` 가 한 번 붙는다

## 팩 rule 주입을 coderag 로 옮긴 컷오버 (이 기기)
이 기기의 coderag 플러그인은 `~/.claude/plugins/cache/coderag-market/coderag/<버전>/` 캐시 사본으로 설치된다. 그래도 바이너리, rule 주입(`conventions/`), 프로바이더는 래퍼가 저장소 쪽을 찾아 쓰므로 바로 최신이다. 캐시에서 읽는 것은 스킬 본문, 에이전트 정의, `hooks.json` 뿐이라 이것들이 바뀐 버전에서만 update 가 필요하다.
- [ ] **먼저(vitrine 세션을 열기 전):** 설치된 web-security 가 0.2.0 이라 캐시에 옛 Python rule 훅이 남아 있다. vitrine 은 `coderag.toml` 에 web-security 가 있어 새 세션에서 rule 이 두 번 붙는다(실측). `claude plugin marketplace update claude-doctor-market`, `claude plugin update web-security@claude-doctor-market`(0.4.0, 훅 없음), Luau 저장소에 luau-kb 스킬이 필요하면 `claude plugin install luau-kb@claude-doctor-market`(0.6.3; 지금 미설치라 Luau 저장소의 enabledPlugins 키가 가리키는 플러그인이 없다). `claude plugin list` 로 확인한 뒤 새 세션. 그 전에 vitrine 을 열어야 하면 그 `coderag.toml` 을 잠시 치운다
- [x] coderag 0.23.0(기록 범위 `scopes/`·`records move`·`search --for`, `coderag get --body` 읽기를 compact 뒤 가리킴에 기록, 바이너리는 release 빌드 완료): `claude plugin marketplace update coderag-market`, `claude plugin update coderag@coderag-market`, `/reload-plugins`. 갱신 전에도 rule 주입은 되고, `get` 기록에 필요한 Bash matcher 와 새 스킬 글만 기다린다
- [ ] vitrine(web-security)·quad(luau-kb)는 에이전트가 `coderag.toml` 과 `.gitignore` 의 `.coderag/` 를 넣었다(커밋 안 함, 그 저장소에서 확인 뒤 커밋). 나머지(table-sim, rbvm, mrow, moonwave-luau, devplorer, nekolog)는 같은 방식으로 넣기 전까지 새 세션에 팩 rule 이 주입되지 않는다(doctor 항목 7 이 PACK-DRIFT 로 알린다). 넣는 법: `coderag.toml` 에 `[[packs]]` + `name = "luau-kb"`(또는 `web-security`), `coderag adapt --harness claude --dry-run`, 이상 없으면 `coderag adapt --harness claude`, `coderag gen`
- [ ] 그 저장소에서 새 세션을 열어 `.luau`(또는 `.ts`) 파일을 Read 해 rule 이 한 번만 붙는지 본다. `/q:doctor` 항목 7 에 `PACK-DRIFT`·`PACK-MISSING`·`PACK-NO-CODERAG`·`PACK-UNREGISTERED` 가 없어야 한다. `<rule plugin="web-security">` 가 두 개 보이면 옛 캐시 사본이 적재된 것이니 알려 달라
- [ ] 다른 기기에 배포할 때: coderag 마켓 추가와 `coderag@coderag-market` 설치, 사용자 coderag 설정(`~/.coderag/coderag.toml`)에 팩마다 `[[packs]]` `name`·`path` 등록(없으면 rule 이 조용히 빠진다), `claude plugin marketplace update claude-doctor-market`, web-security 0.4.0·luau-kb 0.6.0·q 0.8.9·qwreey-conventions 0.7.0 갱신, 새 세션. 기록 규약 rule 은 coderag 바이너리가 있어야 실린다(래퍼는 바이너리가 없으면 훅에서 조용히 0 으로 끝나고, doctor 가 `SET-CODERAG-BINARY` 로 알린다). qwreey-conventions 만 켠 기기에는 이제 기록 규약 rule 이 없고, `HARNESS_CONVENTIONS_RULES=off` 로 rule 을 끈 사람도 이 rule 은 받는다(`CODERAG_RULES=off` 가 따로 필요)
- [x] coderag 0.22.0: `coderag:agent-records` 스킬 본문이 바뀌었다(스냅샷도 description, 좋은 예·나쁜 예). 설치된 캐시 사본은 0.12.0 이라 스킬은 옛 글이다(rule·바이너리는 저장소에서 바로 읽어 이미 최신). `claude plugin marketplace update coderag-market`, `claude plugin update coderag@coderag-market`, `/reload-plugins`.

## 권한
- [ ] plugin.json 의 license 필드(session-log 는 MIT 로 적혀 있음)와 luau-kb·coderag LICENSE 를 함께 결정 (auto 모드 분류기가 막거나, 사용자 판단 사항)
- [x] rbvm, table-sim 의 프로젝트 settings 에서 `git push` deny 를 뺄지 결정 — **인계로 넘김**(2026-11-11, 사용자 추천대로): `.claude/handoff/rbvm.md`, `.claude/handoff/table-sim.md`
  - 위치: `rbvm/.claude/settings.json:25`, `table-sim/.claude/settings.json:4`
  - 사용자 레벨 deny 는 이미 뺐다.
- [ ] luau-kb 의 LICENSE 결정
  - `claude plugin validate` 부가 검사가 LICENSE 와 아이콘이 없다고 알렸다.

- [ ] .claude/audit/16 §7 의 승인 대기 실측 5건(security-guidance, frontend-design, context7, claude-security, LSP·session-report)
  - auto 분류기가 외부 코드 실행을 거부했다. 허용 규칙을 추가하거나 사용자가 직접 실행해야 한다.
- [ ] codex worktree 모드 사용 여부 결정
  - 이 호스트에서 codex 샌드박스가 bwrap 네임스페이스를 만들지 못해 셸 실행이 안 된다.
  - 열려면 `~/.claude/harness.env` 에 `HARNESS_DELEGATE_CODEX_SANDBOX=danger-full-access` 를 써야 한다. 그대로 두면 empty 모드만 쓴다.
- [ ] stl-luau, tbox: `.claude/worktrees` 를 `.git/info/exclude` 로만 무시 중이다. `.gitignore` 로 옮길지 결정한다(각 세션 몫).
- [ ] .claude/scopes/plugins/qwreey-conventions/audit/34 프로브가 남긴 `~/.claude/plugins/data/probe-inline/`(빈 폴더)와 `~/.claude/projects/-tmp-probe-conv-*` 정리
- [ ] 세션 기록 실측이 남긴 `~/.claude/projects/-tmp-sl-hookproj-omyV*` 디렉터리 2개 정리
- [ ] 훅 형식 실측이 남긴 `~/.claude/projects/-tmp-hookfmt`, `-tmp-cmp`, `-tmp-effect-*` (6개) 정리
- [ ] 실측용 임시 프로젝트 기록 `~/.claude/projects/-tmp-*` 정리 (2026-11-10 기준 307개; 이번 작업의 claude -p 실측분이 대부분. `ls -d ~/.claude/projects/-tmp-*` 로 확인 후 삭제)
- [ ] 위임 시범의 임시 산출물 `/tmp/dtrial/` 정리

## ~/.claude 반영 (정본 → 실제)
- 2026-11-11 17:58 기준 apply 를 마쳤다. `tools/home-sync.sh status` 가 모든 파일을 "같음", settings 를 "4/4 적용"(0001, 0002, 0004, 0005)으로 보인다. 고아도 없다. 켜 둔 플러그인은 q, qwreey-advisor, qwreey-conventions 이고 모두 설치돼 있다.
- [ ] apply 가 남긴 백업 `*.bak-<시각>` 정리(확인한 뒤 직접 지운다)
  - 목록: `ls ~/.claude/*.bak-* ~/.claude/{hooks,lib,rules}/*.bak-*`
  - 지우기: `rm ~/.claude/*.bak-* ~/.claude/{hooks,lib,rules}/*.bak-*`
  - 되돌릴 일이 없다고 확인한 뒤에만 지운다. 현재 19개 있다(2026-11-10 16:00 ~ 2026-11-11 17:58).
- [ ] q 나누기 반영(q 0.9.8 이상, 새 qwreey-sessions·qwreey-workspace·qwreey-operator·qwreey-delegate·qwreey-debate, coderag 0.22.4 이상). 순서:
  1. `claude plugin marketplace update claude-doctor-market` (coderag 마켓도 갱신)
  2. q 를 최신으로 갱신하고 켠다(꺼 두었다면). qwreey-sessions, qwreey-workspace, qwreey-operator, qwreey-debate 를 설치한다. qwreey-delegate 는 agy·codex 위임을 쓸 때만 설치한다
  3. `tools/home-sync.sh diff` 로 검토한 뒤 `apply` (0009 가 세 플러그인을 켠다. `HARNESS_DELEGATE_REGISTRY` 경로도 바뀐다)
  4. `/reload-plugins` 또는 새 세션. 확인: `/qwreey-sessions:checkpoint` 가 보이고, 다른 저장소 파일을 고치려 할 때 workspace 게이트가 뜬다
- [ ] qwreey-delegate 0.2.0(Python 드라이버로 전환: SKILL 이 `delegate.py` 를 부르고, 작업 폴더·결과가 `~/.local/state/qwreey-delegate` 로)과 qwreey-proc-guard 0.1.6(`delegate.py` 명령도 통과) 갱신. 갱신 전 세션은 옛 버전의 스킬 문구를 들고 있을 수 있다. 순서:
  1. `claude plugin marketplace update claude-doctor-market`
  2. qwreey-proc-guard 를 먼저, 그다음 qwreey-delegate 를 갱신한다(거꾸로 하면 그 사이 무거운 낱말이 든 `delegate.py` 명령을 옛 proc-guard 가 막을 수 있다)
  3. 돌고 있는 위임이 없을 때 `/reload-plugins` 또는 새 세션. 확인: `python3 -I <스킬>/scripts/delegate.py doctor --all` 에 FAIL 이 없다
  4. `tools/home-sync.sh diff` 로 harness.env 의 위임 주석 예시를 보고 `apply`(값은 바뀌지 않는다)
- [ ] harness_env 키 주인 나누기(q 0.9.10, qwreey-advisor 0.4.14, qwreey-conventions 0.8.7, qwreey-delegate 0.2.1, qwreey-operator 0.2.9, qwreey-proc-guard 0.1.7, qwreey-sessions 0.1.6, qwreey-workspace 0.1.10). 새 플러그인은 플러그인 하나만 읽는 키(`HARNESS_WORKSPACE_GATE`, `SESSION_LOG_CLAUDE` 등)를 자기 사본으로 막고, 옛 플러그인은 설치된 `~/.claude/lib/harness_env.py` 를 읽는다. 순서:
  1. 모든 기기에서 먼저 플러그인: `claude plugin marketplace update claude-doctor-market`, 위 플러그인을 모두 갱신
  2. 그 기기에서 돌고 있는 세션을 모두 다시 읽힌다(`/reload-plugins` 또는 새 세션). 하나라도 남으면 그 세션은 옛 플러그인으로 돈다
  3. 그다음 `tools/home-sync.sh diff` 로 `lib/harness_env.py`, `harness.env` 주석을 보고 `apply`
  - 새 lib 의 `LEGACY_USER_ONLY` 가 예전 lib 이 막던 키(위 두 키, `HARNESS_AGENT_PUSH`, `HARNESS_LUAU_KB`, `SESSION_LOG_HOME`, 위임의 실행 파일·인증·격리·상태 키)를 계속 막으므로, 순서가 뒤바뀌어(apply 먼저, 또는 옛 플러그인이 남은 기기) 옛 플러그인이 새 lib 를 읽어도 이 키들은 저장소 층이 바꾸지 못한다
- [ ] Windows 대응 반영(q 0.10.0, qwreey-sessions 0.4.0, qwreey-advisor 0.4.17, qwreey-conventions 0.12.2, qwreey-delegate 0.2.3, qwreey-operator 0.3.2, qwreey-proc-guard 0.2.1, qwreey-workspace 0.1.11, luau-kb 0.7.2). 이 기기: `claude plugin marketplace update claude-doctor-market` 뒤 위 플러그인 갱신, `/reload-plugins` 또는 새 세션, 그다음 `tools/home-sync.sh diff`(harness.env 가 `~/Projects` 꼴로 바뀌지만 푼 값은 같다, statusline 의 임시 폴더 줄)와 `apply`
- [ ] 플러그인 독립 패키지화 반영(Q28 a, Q29 a; q 0.11.0, qwreey-sessions 0.5.0, qwreey-workspace 0.3.0, qwreey-conventions 0.13.0, qwreey-advisor 0.5.0, qwreey-operator 0.4.0, qwreey-delegate 0.4.0, qwreey-proc-guard 0.2.2, luau-kb 0.7.3). 순서:
  1. `claude plugin marketplace update claude-doctor-market` 뒤 위 플러그인을 `claude plugin update <이름>@claude-doctor-market`, 그다음 `/reload-plugins` 나 새 세션
  2. 위임을 쓰면 먼저 `/plugin configure qwreey-delegate@claude-doctor-market` 에서 위임 uid 표 경로를 `/code/Projects/claude-doctor/plugins/qwreey-delegate/skills/delegate/registry.tsv` 로 둔다. 비워 두면 `register` 가 플러그인 안 사본에 쓰기를 거절한다(실행은 된다)
  3. `tools/home-sync.sh diff` 뒤 `apply`: harness.env 정본에서 `HARNESS_WORKSPACE`, `HARNESS_DOCTOR_ROOT`, `HARNESS_DELEGATE_REGISTRY` 줄이 빠지고 `HARNESS_CODERAG` 는 PATH 의 `coderag`(같은 래퍼로 풀림)
  4. 바뀌는 것: `/q:doctor` 정본 검사는 이 저장소 세션에서만; 세션을 한 번도 연 적 없는 저장소는 qwreey-workspace 옵션 `harness_workspace_extra` 에 `/code/Projects` 를 두면 모두 잡힌다
  5. 설정 우선순위: 코드 기본값 < `~/.claude/harness.env` < `/config` 옵션 < 저장소 `.claude/harness.env` < `harness.local.env` < 환경 변수
- [ ] 회사 Windows PC 첫 실행 확인(README "Windows" 절). 결과를 알려 주면 남은 위험을 고친다
  1. Git Bash 에서 `python3 -c "import sys; print(sys.executable)"` 가 진짜 파이썬을 찍는다(Store 안내 창이 뜨거나 9009 로 끝나면 README 의 python3 항목)
  2. `tools/home-sync.sh diff` 의 settings diff 에서 `claude-doctor-market` 마켓 경로가 클론 위치(`C:/Users/.../claude-doctor` 꼴)이고, `apply` 가 `settings.json JSON OK` 로 끝난다
  3. 새 세션 첫 화면에 `<plugin name="q">` 블록이 보이고 훅 오류 줄이 없다. `claude --debug` 로그에서 훅 명령이 Git Bash 로 돌고 한국어가 깨지지 않는지 본다
  4. 아무 파일 하나를 고친 뒤 qwreey-conventions 알림이 뜨고, 다른 형제 저장소 파일을 고치려 하면 workspace 게이트가 뜬다(경로 대소문자·구분자 판정)
  5. `/q:away` 뒤 `/q:back` 이 오류 없이 요약을 내고, 대화가 몇 번 오간 뒤 `session-log status` 에 기록이 쌓인다(분리 워커)
  6. `/q:doctor --user` 에 `WIN-PYTHON3`, `WIN-GITBASH` 가 없다
- 새 정본 변경(rules, settings 마이그레이션 등)이 생기면 다시 `tools/home-sync.sh diff` 로 검토하고 `apply` 한다. 이때도 같은 백업이 생긴다.

## 다른 세션에 넘길 것
- [ ] stl-luau 세션에 `.claude/handoff/stl-luau.md` 전달
  - 내용: doctor/diet 를 그 세션이 직접 반영하고, todos 를 BI 기준으로 갱신한다.
- [ ] vitrine 세션에 `.claude/handoff/vitrine.md` 전달 (웹 플러그인 4개 enabledPlugins 조각, env, CLAUDE.md 한 줄)
- [ ] rbvm 세션(또는 다음 rbvm 작업 때): `const` 금지 규약을 해제한다.
  - 위치: `rbvm/.claude/conventions.md:28-37`
  - 근거: D-01 확정(금지 근거였던 pesde 0.7.3 은 이미 해소)
- [ ] quad 세션에 `.claude/handoff/quad.md` 전달 (Relate.luau error level, runshim 정렬, 낡은 주석)
- [ ] table-sim 세션에 `.claude/handoff/table-sim.md` 전달 (서버 파일 구조 제안)
- [ ] 각 저장소의 낡은 서술 8건 정정
  - 목록: `.claude/base/decisions/README.md` 끝 "이번에 발견한 낡은 서술"
  - 2026-11-10: 아래 저장소별 정정 파일에 합쳤다. 그 파일들을 전달하면 이 항목도 끝난다.
- [ ] quad 세션에 `.claude/handoff/quad.md` 의 "luau-kb 증류에서 나온 정정" 절 전달 (36건: 행동 16, 표현 20. `-O2` 게이트·에러 위치·태깅 지점, type function 제약, alias, 엔진 동작)
- [ ] stl-luau 세션에 `.claude/handoff/stl-luau-corrections.md` 전달 (28건: 행동 6, 표현 22. perf-measurements 수치 정정 중심, `.claude/handoff/stl-luau.md` 와 별개)
- [ ] tbox 세션에 `.claude/handoff/tbox-corrections.md` 전달 (6건: 행동 2, 표현 4. stylua 오염 원인, analyze FFlag 확인 무효)
- [ ] devplorer 세션에 `.claude/handoff/devplorer-corrections.md` 전달 (5건: 행동 2, 표현 3. DataStore 예산, weak 표 Instance 수거)
- [ ] rbvm 세션에 `.claude/handoff/rbvm-corrections.md` 전달 (4건: 행동 2, 표현 2. 접두 없는 require, 시그널 userdata 신원. 위 `const` 항목 포함)
- [ ] table-sim 세션에 `.claude/handoff/table-sim-corrections.md` 전달 (2건: 표현 2)
- [ ] moonwave-luau 세션에 `.claude/handoff/moonwave-luau-corrections.md` 전달 (2건: 표현 2)
- [ ] 메인(claude-doctor)이 `.claude/handoff/claude-doctor-corrections.md` 반영 (8건: 행동 2, 표현 6. D-01 §2, .claude/scopes/packs/luau-kb/audit/09 M-05)
- [ ] moonwave-luau 의 `.claude/`, `CLAUDE.md` 가 한 번도 커밋되지 않았다. 커밋할지 결정한다.
- [ ] 비개발자·Windows 동료 배포 안내문에 qwreey-delegate README "Windows·비개발자 동료" 절(공식 codex-plugin-cc 설치, Stop-gate 끔, rescue 쓰기 주의)을 넣는다
