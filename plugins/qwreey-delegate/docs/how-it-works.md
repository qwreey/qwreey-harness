# qwreey-delegate 동작 상세

구성은 스킬 `qwreey-delegate:delegate` 하나와 그 스크립트 `skills/delegate/scripts/delegate.sh` 뿐이다. 훅과 규약 주입은 없다. 모델이 따르는 전체 절차는 `skills/delegate/SKILL.md` 에 있고, 여기서는 사람이 알아야 할 구조를 정리한다.

## 언제 쓰나
- 쓴다: 여러 발견이 공유할 수 있는 근본 원인, 지금 틀 밖의 시선, 같은 메커니즘의 발견 묶기, 이름의 객관성 확인(세 계열 비교), 한 메커니즘으로 범위를 정한 버그 사냥.
- 쓰지 않는다: 리뷰 라운드, 전체 감사, 전수 비교표(사용자가 이름을 들어 외부 감사를 요청한 경우는 예외), 결정, 메인 저장소에 그대로 반영할 결과, 결정 이력을 알아야 하는 판단.
- 모델 성향: Gemini(agy)는 틀 밖 근본 원인으로 잘 뛰지만 추론 오류·지어낸 진술·끼워 넣은 조작이 훨씬 잦고 단정적이며, 수정안이 성능을 무시한다. codex 는 맥락을 프롬프트에 모두 담은 객관 판단(이름)에 싸고 빠르다.

## 실행 흐름
1. 지시문: `templates/tasks.md` 골격으로 스크래치에 쓴다. 스크립트가 앞에 공통 머리말을 붙인다(worktree 밖 쓰기 금지, 변경하는 git 명령 금지, `ulimit` 과 종료 코드 판정, 실측과 추정 구분, 기준 커밋을 모델이 직접 확인, 제안은 결정이 아님). 앞선 리뷰의 분류표는 넘기지 않는다(모델이 그 틀에 갇힌다).
2. 실행: `delegate.sh run <agy|codex> <name> <prompt> [--repo …] [--mode worktree|empty] [--ref <commit>] [--model M] [--effort …] [--timeout 초]`. worktree 는 커밋된 `--ref`(기본 HEAD)에서 자르므로 보여 줄 것은 먼저 커밋한다. Bash `run_in_background` 로 돌리고 완료 알림을 기다린다. 기본 시간 제한 3600초.
   - 모드: agy 기본 `worktree`, codex 기본 `empty`(맥락 전부를 프롬프트에, 코드는 `nl -ba` 로 줄 번호).
   - codex `worktree` 는 거절한다. codex 의 bubblewrap 샌드박스가 비특권 uid 아래에서 네임스페이스를 만들지 못해 셸이 돌지 않는다. `DELEGATE_CODEX_SANDBOX=danger-full-access` 로 끄면 uid 만 남으므로 사용자가 정한다.
   - agy `empty` 는 검증되지 않아 경고를 낸다.
3. 읽기: 보고서(agy worktree: `<workspace>/<name>/REPORT.md`, 그 밖에 `.delegate/report.md`), `.delegate/guard.txt`(종료 코드, 메인 저장소 변경 여부, worktree HEAD, 바뀐 파일), 필요하면 `.delegate/stdout.txt`.
4. 검증(아래).
5. 보관과 제거: `collect` 가 `<workspace>/runs/<date>-<name>/` 에 지시문·보고·guard·stdout·diff.patch 를 남기고, `remove` 가 worktree 와 작업 HOME 을 지운다(collect 전에는 거절, `--discard` 로 버림). 인용할 보고는 프로젝트 `.claude/audit/<backend>/<date>-<name>.md` 로 옮기고 메인의 검증을 위에 붙여 커밋한다. `runs/` 는 저장소 밖이라 근거로 인용하지 않는다.
6. 정리: `list --all`, `gc --all`(미리보기), `gc --all --apply`. 살아 있는 프로세스가 있는 작업 폴더는 건너뛴다.

## 검증 규칙
- 모든 주장을 메인이 확인한다. 실제로 틀렸던 예: 입력 문서에서 베낀 기준 커밋, 거꾸로 인용한 실측, 반대 방향을 가리킨 인용, 돌리지 않은 테스트를 "실측" 으로 표시, 닫힌 질문을 열린 것으로 셈, 들여쓰기가 바뀐 코드 인용.
- 결함 주장은 재현 테스트를 먼저 쓰고 고친다. 재현되지 않으면 "외부 주장, 메인 재현 안 됨" 으로만 남긴다.
- 수정안은 성능을 다시 잰다(뜨거운 경로).
- 새 필드·이름·메커니즘·규약은 사용자 질문이다. 증상만 확실하면 "증상 확인, 해법 미정".
- `diff.patch` 는 참고용이고 그대로 적용하지 않는다.

## 격리
`agy --sandbox` 와 codex `-s read-only` 는 cwd 밖 접근을 막지 못하고 `unshare -m` 은 이 환경에서 허용되지 않아 다음으로 막는다.
1. `setpriv` 로 저장소별 비특권 uid(61000 부터, 저장소끼리 공유하지 않음). 그 uid 소유는 worktree, `.git/worktrees/<id>`, 작업 HOME 뿐이라 메인 작업 트리와 `.git/objects` 에 쓸 수 없고 커밋·푸시도 못 한다. pre-push 훅이 한 번 더 거절한다. worktree 는 detached 라 브랜치를 만들지 않는다.
2. 빈 환경(`env -i`). PATH 는 저장소 `mise.toml` 에 고정된 도구와 `/usr/bin:/bin`(`/usr/local/bin` 제외).
3. `choom -n 1000`: 메모리가 모자라면 이 작업이 Claude 보다 먼저 죽는다. agy 자체의 Bash 는 Claude 의 PreToolUse 훅에 보이지 않아 이것이 유일한 손잡이다.
4. 메인 저장소의 HEAD 와 상태를 실행 전후로 비교해 `guard.txt` 에 남긴다. CHANGED 면 그사이 메인이나 사용자가 바꿨는지 확인한다.
5. 작업마다 HOME 을 따로(`<workspace>/.homes/<name>`), 인증 정보 사본만 넣는다. `doctor` 가 그 uid 로 `~/.claude/.credentials.json`·`.git-credentials`·`.ssh` 를 읽을 수 없는지 확인한다.
6. 스크립트는 임시 사본에서 다시 실행된다. 실행 중에 `delegate.sh` 를 고쳐도 돌던 작업이 깨지지 않는다.

이 격리는 Linux root 에 기대고, 지금 스크립트는 empty 모드도 같은 uid 로 돌려서 모드와 상관없이 root 가 필요하다. OS 격리가 없는 곳에서는 empty 모드(읽기 전용 의견)만 쓴다. agy 는 ACP 에서도 워크스페이스 밖 파일 읽기·쓰기를 묻지 않고 settings `permissions` 규칙도 듣지 않아서(OS 샌드박스 없는 Linux 실측) 에이전트 쪽 설정으로는 막을 수 없다. root 없이 도는 크로스플랫폼 드라이버와 그 기본 정책: `.claude/research/drafts/delegate/portable-isolation.md`.

## 설정
- uid 표 `registry.tsv`(열: key, root, uid, setup, note). 찾는 순서: `DELEGATE_REGISTRY`, `HARNESS_DELEGATE_REGISTRY`(환경 변수 또는 `~/.claude/harness.env`), 스킬 옆 사본. 고쳐 쓰는 파일이라 플러그인 캐시의 사본은 버전마다 낡으므로 claude-doctor 클론의 것을 가리킨다. 새 저장소는 `delegate.sh register <path> [key]` 가 다음 빈 uid 를 준다(`/etc/passwd` 와 겹치지 않게).
- 저장소마다 루트에 `AGENTS.md`(골격 `templates/AGENTS.md.template`): 정본 경로, 확인 명령, 저장소 전용 주의를 담은 6KB 이하의 지도. 두 모델이 모두 읽는다. `GEMINI.md` 는 지운다(agy 가 둘 다 읽어 겹친다).
- `delegate.sh doctor --all`: uid, 비밀 파일 접근, `AGENTS.md` 를 점검한다.
- 환경 변수:
  - `DELEGATE_MAX_CONCURRENT`(기본 1): 백엔드마다, 모든 저장소 합계. 토큰 한도가 사용자 단위라서. 사용자가 여유가 있다고 할 때만 늘린다.
  - `DELEGATE_CODEX_SANDBOX`(기본 `read-only`), `DELEGATE_KEEP_ENV=1`(빈 환경 대신 현재 환경 유지), `DELEGATE_AGY_FULL_HOME=1`(agy 인증이 안 될 때 HOME 전체 사용).
  - 실행 파일·인증 위치: `DELEGATE_AGY_BIN`, `DELEGATE_CODEX_BIN`(기본은 `HARNESS_TOOL_INSTALLS` 아래), `DELEGATE_GEMINI_SRC`, `DELEGATE_CODEX_AUTH`.
- 모델: agy 는 `gemini-3.8-flash-high` 만(pro 는 없는 것으로 본다), codex 는 `gpt-6-luna`, `--effort medium`.

## 작업 폴더
저장소 옆 형제 폴더를 쓴다. `<repo>-agy`, `<repo>-codex` 는 스크립트 소유(worktree `<name>/`, `.homes/<name>/`, `.hooks/`, `runs/`)라 손으로 만들거나 고치지 않는다. `<repo>-scratch` 는 버려도 되는 실험, `<repo>-proto/<slug>` 는 프로토타입 브랜치의 worktree. 형제 폴더는 클론에 없으므로 근거로 인용하지 않는다.

## 확인되지 않은 부분
- agy `empty` 모드, agy HOME 을 인증 정보만으로 줄인 구성은 실제 실행으로 검증되지 않았다(SKILL.md 기재).
