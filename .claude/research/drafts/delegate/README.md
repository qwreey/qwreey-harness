# (B) agy/Codex 위임 통합 설계

2026-11-10 초안. 근거:
- `quad`, `stl-luau`, `tbox`, `table-sim`의 `.claude/tools/agy-delegate.sh`와 `skills/delegate-agy/SKILL.md`(4벌, diff로 대조)
- `quad-codex/*`와 quad 메모리 `reference-codex-delegation.md`
- stl-luau 메모리 `agy-budget-generous.md`, `agy-is-second-opinion.md`
- `audit/03` §3·§5, `audit/04` §1·§3.2·§9
- agy 내장 문서 `agy-customizations/docs/rules.md`

| 파일 | 내용 |
|---|---|
| `skills/delegate/SKILL.md` | 통합 스킬(agy/codex 백엔드, 언제·비용·실행·검증 후 반영·격리) |
| `skills/delegate/scripts/delegate.sh` | `run / collect / remove / list / gc / doctor / register` |
| `skills/delegate/registry.tsv` | uid 중앙 표 |
| `skills/delegate/templates/preamble-{worktree,empty}.md` | 스크립트가 붙이는 머리말. 프로젝트 고유 내용 없음 |
| `skills/delegate/templates/tasks.md` | 과제 틀 넷(근본 원인, 버그 사냥, 이름 세 계열 대조, 설계 바깥 의견) |
| `skills/delegate/templates/AGENTS.md.template` | 프로젝트 외부 모델 진입점 틀 |
| `conventions.md` | `-agy / -codex / -scratch / -proto` 명명 규약, GEMINI.md·AGENTS.md 배치 |
| `migration.md` | 4벌 걷어내기 순서와 시점 |

## 1. 핵심 결정

1. **스크립트 하나, 백엔드 둘, 설정은 중앙 표 하나.**
   - `delegate.sh run <agy|codex> …`가 저장소를 찾는 순서: `git rev-parse --git-common-dir`(Claude worktree 안에서도 메인 저장소로) → `registry.tsv` → ROOT, uid, setup.
   - BASE는 규약으로 정한다(`<dirname(ROOT)>/<key>-<backend>`). 따로 받지 않는다.
   - 표에 없는 저장소는 **거부**하고 `register`로만 들인다. 이렇게 해서 uid 배정을 한 곳에서만 한다.
   - tbox는 61000 → **61003**으로 옮겨 quad와의 충돌을 푼다.
2. **수명 주기에 정리를 넣는다.**
   - `run → collect → remove`. `remove`는 collect 전이면 거부한다.
   - `gc`는 미리보기가 기본이다. 지우는 것: collect된 작업공간, 주인 없는 HOME, 옛 공유 `.home`.
   - 지금 쌓인 양(2026-11-10 실측): quad-agy `.home` 117M, stl-luau-agy `.home` 260M, tbox-agy `.home` 228M, quad-codex `.home` 31M, quad-agy 옛 worktree 83M. **대부분이 공유 HOME에 쌓인 agy 대화·brain 기록이다.** 과제마다 HOME을 두고 remove가 지우면 다시 쌓이지 않는다.
3. **기록은 저장소 밖 `runs/`에, 근거는 저장소 안에.**
   - collect가 `<작업공간>/runs/<날짜>-<이름>/{prompt,report,guard,stdout,meta,diff.patch}`를 남긴다. quad-codex의 prompt/answer/stdout 3종을 일반화한 것이다.
   - 근거로 인용할 보고서는 메인이 검증 머리를 붙여 프로젝트 `.claude/audit/<backend>/`로 옮긴다. 저장소 밖 경로를 근거로 인용하지 않는다(`audit/04` §1, stl-luau가 `-scratch`를 인용한 문제).
4. **프로젝트 고유 내용은 머리말에서 빼서 각 프로젝트 `AGENTS.md`로 보낸다.**
   - 4벌이 갈라진 주된 이유는 머리말 안의 검사 명령, vendor 예외, Studio 금지 같은 프로젝트 사실이었다.
   - 이제 머리말은 공통 규칙만 담고 "검사는 `AGENTS.md`의 '검사' 절"이라고 가리킨다.
   - agy와 codex 모두 `AGENTS.md`를 자동으로 싣는다. GEMINI.md는 없앤다(`conventions.md` §2).
5. **위임은 좁은 질문 전용, 기본은 백엔드당 하나.**
   - 리뷰 라운드와 전수 감사는 `/audit`(Claude 감사자)의 몫이다.
   - 동시 실행 상한은 백엔드마다 모든 저장소 합계 1이다(`DELEGATE_MAX_CONCURRENT`). 토큰 한도가 사용자 단위이기 때문이다.
   - 결과는 발견이지 결정이 아니고, 메인이 재현한 것만 반영한다.

## 2. 4벌 차이와 흡수

`diff quad …/agy-delegate.sh {stl-luau,tbox,table-sim}/…`로 확인했다. stl-luau-doctor의 사본은 stl-luau와 md5가 같다.

| 개선 | 있던 곳 | 통합판 |
|---|---|---|
| setpriv 무권한 uid, worktree와 admin dir만 chown | 4벌 모두 | 유지 |
| pre-push 거부 훅(`GIT_CONFIG_*`로 `core.hooksPath`) | 4벌 모두 | 유지 |
| 실행 전후 HEAD와 status 해시 비교 → guard.txt | 4벌 모두 | 유지. worktree HEAD가 움직였는지도 더함 |
| `choom -n 1000` | quad, tbox, table-sim (**stl-luau에는 없음**) | 유지(모든 백엔드) |
| 과제마다 HOME(`.homes/<이름>`), remove가 지움 | stl-luau, table-sim, tbox(`.home/<이름>`) | 유지. 이름은 `.homes/` |
| `--ref <커밋>` | stl-luau | 유지 |
| 도구 PATH(`TOOL_PATH`) | stl-luau, tbox, table-sim(손으로 적음, "mise.toml과 맞출 것") | **mise.toml에서 자동 산출**(`mise ls --current --json` → `mise bin-paths`). 손으로 맞출 일이 없음 |
| PATH에서 `/usr/local/bin` 제외(Studio 도구) | table-sim | 유지(모든 저장소) |
| detached worktree(브랜치 없음 → 브랜치 삭제 불필요) | table-sim | 채택. 옛 브랜치 worktree는 remove가 브랜치를 남기고 알림(`--delete-branch`는 사용자 확인 뒤) |
| worktree 생성 뒤 `pesde install` | quad | 표의 `setup` 열로 일반화 |
| 머리말: 기준 커밋 직접 확인, GEMINI.md 진입점 | stl-luau | 유지. 진입점은 AGENTS.md로 |
| 머리말: 코드 인용은 파일 그대로 | table-sim | 유지 |
| 머리말: Studio, MCP, 네트워크, sync 금지, vendor 읽기 예외 | table-sim | 공통 금지는 머리말에, vendor 예외는 table-sim `AGENTS.md`로 |
| 머리말: 원본 경로는 읽지 말 것 | tbox(quad는 "읽기만") | tbox판 채택("worktree 안의 같은 파일을 읽어라", 예외는 AGENTS.md) |
| uid 실측(저장소, .git, credentials 쓰기·읽기 거부) | table-sim 주석 | `doctor`가 매번 검사 |
| "돌고 있는 동안 스크립트를 고치지 말 것" | stl-luau 스킬 | **자기 사본으로 다시 실행**해서 문제 자체를 없앰 |
| 동시 실행 경고("한 번에 하나") | stl-luau 스킬, 메모리 | `flock` + 살아 있는 pid 수로 강제(기본 1) |
| `remove`가 브랜치 삭제 | quad, stl-luau, tbox | 채택하지 않음(detached라 불필요) |
| 결과 원문 보존(`.claude/audit/agy/<날짜>-<이름>.md`에 검증 머리) | stl-luau 스킬 | SKILL 5단계 + collect의 `runs/` |
| codex 실행 꼴(uid, 격리 CODEX_HOME, 실행마다 auth.json, `-s read-only`, `-o answer`) | quad 메모리(스크립트 없음, 수동) | `run codex --mode empty`로 스크립트화 |

### 통합판에서 새로 생긴 것 (검증 상태)

- 가짜 agy/codex로 한 자체 시험(2026-11-10, `drafts/delegate/.selftest`, 끝난 뒤 지움)
  - 확인한 것: run → guard(메인 unchanged, worktree 변경 목록) → collect(diff.patch에 새 파일 포함) → remove(collect 전 거부) → gc(미리보기/적용, 옛 브랜치 worktree 보존) → doctor → register, 그리고 동시 실행 거부
  - 실제 agy·codex 호출은 하지 않았다
- 실제 저장소 넷에 `doctor --all`과 `gc --all`(미리보기)을 읽기 전용으로 돌렸다. uid 넷 모두 메인 트리에 쓰지 못하고 비밀을 읽지 못함, 도구 PATH 산출 정상.
- 첫 실제 실행(2026-11-10 table-sim, `trial-2026-11-10.md`): `env -i` 정상, codex worktree 모드는 이 호스트에서 쓸 수 없어 거부하게 고침, agy empty 모드는 아직 실행 전. 버그 다섯을 고쳤다(그중 agy HOME 축소와 agy empty 보고서는 미검증).
- 모델별 특성은 `model-traits.md`, 모델 간 토론 스킬 초안은 `skills/debate/`.

## 3. 설치 위치

- 스킬: `~/.claude/skills/delegate/`. 심볼릭 링크로 걸든 luau-kb 플러그인으로 넣든 된다. PLAN §4-1 결정에 따른다.
  - 스크립트는 `${CLAUDE_SKILL_DIR}/scripts/delegate.sh`로 부른다.
- **중앙 표는 고쳐 쓰는 파일이라 플러그인 캐시에 두면 안 된다.** 플러그인 캐시는 버전마다 사본이 생긴다.
  - 플러그인으로 갈 경우 `registry.tsv`는 git 정본 저장소에 두고, `~/.claude/settings.json`의 `env.DELEGATE_REGISTRY`로 가리킨다.
  - 심볼릭 링크 설치면 기본 경로(스킬 디렉터리 옆) 그대로 정본이다.
- 이 스킬은 Luau 전용이 아니다. 정본 저장소 이름이 luau-kb이면 거기 두되, 스킬 이름은 `delegate`로 둔다.
