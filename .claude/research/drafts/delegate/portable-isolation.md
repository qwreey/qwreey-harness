---
format: 1
title: delegate 를 root 없이 macOS·Windows·Linux 에서 돌리는 방안
description: codex 는 exec+권한 프로필·작업별 CODEX_HOME 으로 root 없이 가능(OS 샌드박스 있을 때). agy ACP 는 파일 도구를 묻지 않고 settings permissions·plan 모드도 무시하지만, print 모드 --settings deny 는 파일 도구를 막음(실측). 격리 없으면 agy 는 기본 꺼짐
status: active
---
# delegate 이식성 조사

사용자: "여기처럼 sandbox 환경 아니면 사실 root 가 없기도 하고, windows macos 가 안 된다는건 사실상 쓰지 말라는 것에 가깝긴 해서. agy 쪽엔 acp 도 있고, codex 에는 많은 command line arguments 들도 있고". 표시: [실행] help·실행으로 확인, [문서] 공식 문서·changelog, [추정].

## 지금 상태의 함정
- 이 호스트는 `kernel.unprivileged_userns_clone = 0` 이라 `codex sandbox` 가 bwrap namespace 생성에 실패한다[실행]. "codex `-s read-only`·`agy --sandbox` 가 cwd 밖을 못 막는다"는 이 호스트 한정이다.
- agy 는 샌드박스를 못 쓰면 `--sandbox` 를 조용히 무시한다[문서, changelog].
- 스크립트의 agy `--dangerously-skip-permissions` 는 워크스페이스 밖 읽기·쓰기를 묻지 않는다. 지금은 uid 격리가 메운다.

## codex (0.166.0)
- `codex exec`: `-s read-only|workspace-write|danger-full-access`, `-C`, `--add-dir`, `--ephemeral`, `--ignore-user-config`, `--ignore-rules`, `-p`, `--disable`, `--json`, `-o/--output-last-message`, `--output-schema`. 승인은 `-c approval_policy="never"`[실행].
- 권한 프로필(beta)[문서]: `default_permissions="deleg"`, `[permissions.deleg] extends=":workspace"`, filesystem `":root"="deny"`, `":minimal"="read"`, `"~/.ssh"="deny"`, `network.enabled=false`. `:workspace` 는 `.git`·`.codex`·`.agents`·`.aws` 를 읽기 전용으로. `--sandbox` 를 주면 프로필 대신 옛 방식. https://learn.chatgpt.com/codex/permissions , https://learn.chatgpt.com/docs/config-file/config-reference
- OS[문서]: macOS Seatbelt, Linux bwrap+seccomp(비특권 userns 필요, Ubuntu 는 AppArmor 프로필), Windows MXC(관리자 불필요, Win11 24H2 26100.9278+; `unelevated` 는 읽기 차단 없음, 네트워크 격리 약함). https://learn.chatgpt.com/docs/sandboxing
- worktree 의 gitdir 는 메인 `.git/worktrees/<id>` 라 워크스페이스 밖: 커밋 불가, 네트워크 끔으로 push 불가[추정].
- `codex app-server` 에 `CommandExecutionRequestApproval`·`FileChangeRequestApproval` 스키마[실행]. exec+샌드박스로 충분.

## agy (1.5.7)
- `agy acp`: stdio JSON-RPC. `initialize` 응답에 `loadSession`, `sessionCapabilities{resume,close,load,list,additionalDirectories}`, `_meta.antigravity.systemPrompt.append`[실행, 모델 호출 없음]. 바이너리에 `session/request_permission`·`session/set_mode`·`allow_once`·`reject_once` 는 있고 `fs/write_text_file`·`terminal/*` 는 없다: 입출력은 agy 가 직접 하고 클라이언트는 권한 요청에만 답한다[추정].
- 설정[문서]: `enableTerminalSandbox`, `toolPermission`(request-review/strict/proceed-in-sandbox/always-proceed), `agentMode`(default/accept-edits/auto/plan), `permissions.allow/deny/ask`(`read_file()`, `write_file()`, `command()`, `read_url()`, `mcp()`, Deny > Ask > Allow). 워크스페이스 밖 접근은 기본 승인 요구, 샌드박스 명령은 네트워크 없음·`~/.ssh`·`.env` 차단. `-p --settings` 1회용 JSON, `acp` 는 `--gemini-dir`·`--app-data-dir`. https://antigravity.google/docs/sandbox.md , https://antigravity.google/docs/permissions.md
- OS[문서]: Linux namespace(userns), macOS Seatbelt, Windows AppContainer(Win11 24H2 2026-08 업데이트+).

## 권장 설계(root 불필요)
- codex: 작업별 `CODEX_HOME`(auth.json 사본 + 위 프로필), 워크스페이스 = worktree, 메인 `.git` 읽기만, 네트워크 끔, `--disable apps,browser_use,computer_use,plugins`(기본 켜짐[실행]), `exec -o … --json`.
- agy: ACP 클라이언트로. accept-edits, `toolPermission: proceed-in-sandbox`, deny `write_file`(메인 저장소)·`read_file(~)`·`read_url(*)`(실측: ACP 에서는 이 규칙이 듣지 않는다, 아래). 권한 요청은 worktree 안 편집만 허가. OS 샌드박스가 없으면 명령 요청을 전부 거절하는 셸 없는 모드(codex `empty` 에 해당).
- 잃는 것: 에이전트 프로세스는 사용자 권한이라 HOME 비밀·대화 기록·Keychain 은 정책 코드로만 막힌다. 저장소별 uid 분리와 `choom` 은 Linux 선택 강화층(root 있을 때 `setpriv`·`choom` 덧씌움)으로.
- 유지: pre-push 거부 훅(`GIT_CONFIG_*`), 실행 전후 HEAD 비교.
- 드라이버: `delegate.sh` 를 Python 하나로(`run/collect/remove/list/gc/doctor`, 상태 `.delegate/state.json`, `O_EXCL` 잠금, timeout, agy 는 ACP 루프). `doctor` 는 모델 호출 없이 `codex sandbox -P deleg -C <wt> -- cat ~/.ssh/...`·밖 쓰기·`git push` 실패와 agy OS·userns 를 검사.

## 남은 위험
- agy Keychain 인증과 `--gemini-dir` 분리, codex `apply_patch` 가 샌드박스로 강제되는지 정책 검사뿐인지, 권한 프로필 beta, Windows `unelevated` 읽기 차단 없음, 작업 사본에서 토큰 갱신 시 원본 refresh token 무효 가능, agy 워크스페이스 밖 거부는 프로세스 안 정책뿐.

## 다음에 잴 것(사용자 동의 뒤 실제 실행)
1. macOS·Win11 에서 `codex sandbox` 프로필 검사(이 호스트는 bwrap 불가).
2. agy ACP `session/new` 뒤 `request_permission` 내용(kind, locations).
3. 그 상태에서 worktree `.git` 접근.
4. `--gemini-dir` 분리 상태의 인증.

## 실측: agy 1.5.7 ACP (이 호스트, OS 샌드박스 없음)
- 줄 단위 JSON(NDJSON), 응답 id 는 문자열. 메서드: `initialize`, `session/new`(modes·configOptions·models), `session/set_model`, `session/prompt`, `session/update`, `session/request_permission`.
- `request_permission` 은 셸(`run_command`, kind `execute`, locations 없음)에만 온다. 옵션 `allow`(allow_once)·`deny`(reject_once). 거절한 셸 명령은 실행되지 않았다.
- 파일 도구(`read_file`, `write_file`)는 default 모드에서도 권한 요청 없이 돈다. 워크스페이스 밖 `../outside/secret.txt` 읽기와 줄 추가가 요청 없이 성공했다(`--add-dir wt` 를 줘도, 서버 로그 `workspaceDirs=[]`).
- `session/new` 의 `cwd` 는 무시되고 프로세스 cwd 가 쓰인다(드라이버는 Popen cwd 를 worktree 로).
- 시작 로그에 `Terminal sandbox unavailable: unprivileged user namespaces are disabled` 를 찍고 경고 없이 계속한다.
- 인증: 빈 `--gemini-dir` 는 `Authentication required`. `<gemini-dir>/antigravity-cli/antigravity-oauth-token` 하나만 복사하면 된다(D-Bus 없음, 파일 저장소). `--app-data-dir` 는 상대 이름만. `--gemini-dir` 를 따로 줘도 `$HOME/.config/antigravity/plugin-secrets.json` 은 읽는다.
- 비용: flash-low 6턴, 턴당 6-17초, 합계 약 14.5만 토큰.
- 결론: OS 격리(uid 분리, 컨테이너, OS 샌드박스)가 없으면 agy 는 ACP 만으로 격리되지 않는다. 위 "권장 설계"의 agy 항목(worktree 안 편집만 허가)은 이 호스트에서 성립하지 않는다. OS 샌드박스가 있는 macOS·Windows·userns 켜진 Linux 에서 파일 도구도 막히는지는 아직 모른다.
- 클라이언트와 로그: `/tmp/acpprobe-1/client/acp_client.py`, `/tmp/acpprobe-1/log.jsonl`.

### settings `permissions` 규칙 (agy 1.5.8, ACP)
- 배치: `--gemini-dir <d>` 의 `<d>/antigravity-cli/settings.json`(문서상 CLI 전역 위치, CLI 에는 저장소 단위 settings.json 이 없다). 규칙은 문서 문법대로 `ask: ["read_file(/tmp/acpprobe-2/outside)"]`, `deny: ["write_file(/tmp/acpprobe-2/outside)"]`(절대 경로, 디렉터리는 하위 전체). Popen cwd = worktree, flash-low 1턴, 파일 도구로 `outside/secret.txt` 읽기와 줄 추가를 지시.
- 서버는 이 파일을 읽는다: 깨진 JSON 이면 `Failed to load CLI settings, using defaults: malformed settings json`, `enableTerminalSandbox: "zz"` 면 타입 오류를 찍는다(모델 호출 없이 확인). 그런데 `"permissions": "x"` 는 아무 오류 없이 넘어간다. ACP 의 `cliSettings` 는 `permissions` 를 읽지 않는 것으로 보인다[추정].
- 결과: `session/request_permission` 0건. `read`(locations `/tmp/acpprobe-2/outside/secret.txt`)와 `edit`(`Append: true`)가 요청 없이 `completed`, 파일 sha256 이 `fe28b616…` 에서 `5a11658f…` 로 바뀌고 `probe` 줄이 붙었다. 모델 답: "Neither tool was denied". 도구가 보낸 경로가 규칙 접두와 정확히 같으므로 경로 표기 차이로 설명되지 않는다.
- 세션은 프로젝트 `default-cli-project` 를 쓰고 `<d>/config/projects/default-cli-project.json` 을 찾는다(없으면 오류 로그). 문서의 Project 범위 규칙이 여기 있을 수 있으나 스키마가 문서에 없어 재지 않았다.
- 비용: 모델 1턴 11.2초, 약 2.5만 토큰(입력 1.9만, 캐시 0.6만, 출력 188). 나머지 세 번은 `session/new` 없는 시작만.
- 결론: ACP 에서는 settings `permissions` 의 deny·ask 도 파일 도구를 막거나 요청으로 바꾸지 않는다. agy 의 파일 접근을 ACP 안에서 막을 손잡이는 지금 찾은 것이 없다. 남은 후보(재지 않음): Project 범위 파일, OS 샌드박스가 있는 호스트.
- 로그: `/tmp/acpprobe-2/log1.jsonl`, 서버 로그 `/tmp/acpprobe-2/gem/antigravity-cli/log/`, 클라이언트 `/tmp/acpprobe-2/client/acp_client.py`(`--allow-reads` 추가).

### ACP plan 모드, print 모드 `--settings` (agy 1.5.8)
- 공통: HOME 과 `--gemini-dir` 은 일회용 폴더(토큰 파일만 복사), 프로세스 cwd 는 빈 작업 폴더, flash-low 1턴, 파일 도구만으로 작업 폴더 밖 `outside/secret*.txt` 읽기와 줄 추가를 지시.
- A. ACP `session/set_mode` `plan`(설명 "Plan carefully before executing a task"): `set_mode` 응답은 성공, `session/request_permission` 0건, `read`·`edit` 가 요청 없이 `completed`, 파일에 `probe-A` 줄이 붙었다(sha256 `106cead2…` → `b27ba70e…`). plan 모드도 파일 도구를 막지 않는다. 27.8k 토큰, 14초.
- B. print 모드 `agy -p --settings '{"permissions":{"deny":["read_file(<outside>)","write_file(<outside>)"]}}'`, `--dangerously-skip-permissions` 없음: 두 도구가 `Matches user-configured deny rule` 로 거절되고 파일은 그대로(sha256 `106cead2…`). CLI 로그에 `CLI settings initialized: permissions=&{… Deny:[read_file(…) write_file(…)]}, toolPermission=request-review`. 12.7k 토큰, 12.6초.
- 결론: settings `permissions` 는 print 모드에서는 듣고 ACP 에서는 듣지 않는다(ACP 는 CLI settings 의 permissions 를 읽지 않는 것으로 보인다[추정]). 격리가 없는 기계에서 agy 파일 도구를 막을 손잡이 후보는 print 모드 + deny 규칙이다. 재지 않은 것: 넓은 deny(`/`, HOME)와 작업 폴더 allow 의 우선순위, print 모드에서 셸(`command()`)과 `read_url()` 이 어떻게 되는지, 기호 링크·`..` 경로, 버전 차이.
- 로그: `/tmp/acpprobe-3/`(`logA.jsonl`, `outB.json`, `homeB/.gemini/antigravity-cli/log/`).

### print 모드 기본 프리셋, 규칙 없음, `--dangerously-skip-permissions` 없음 (agy 1.5.8)
- 규칙 우선순위는 문서상 Deny > Ask > Allow 로 고정이라 "넓게 deny + 작업 폴더 allow" 는 성립하지 않는다(deny 가 이김). 대신 기본 프리셋(문서: 파일은 작업 폴더와 임시 폴더 허용, 그 밖은 Ask; 셸은 샌드박스 안 허용, 아니면 Ask)이 print 모드에서 어떻게 되는지 쟀다. 바깥 비임시 경로는 `/code/.cache/acpprobe-out/`.
- C. 바깥(비임시) 읽기: `Print mode: soft-denying tool confirmation "ReadFile"`, JSON `denied_actions: [read_file]`, stderr "headless mode cannot prompt … auto-denied". 거절되면 그 턴이 빈 답으로 끝나 뒤 단계는 시도되지 않는다. 8.9k 토큰.
- D. 임시 폴더: 작업 폴더 안 생성, `/tmp/acpprobe-3/outside/secretD.txt` 읽기·줄 추가가 모두 묻지 않고 실행(sha256 `106cead2…` → `59fdf180…`). 기본 프리셋은 `/tmp` 전체를 연다. 15.6k 토큰.
- E. 작업 폴더 안 기호 링크(→ 바깥 비임시 파일) 읽기: 거절(`denied_actions: [read_file]`), 파일 그대로. 링크는 대상 경로로 판정된다. 8.8k 토큰.
- F. 셸(`cat` 바깥 파일): 거절(`denied_actions: [command]`). 이 호스트는 셸 샌드박스가 없어 Ask 가 되고 headless 가 거절한다. 로그에 시작 직후 `Terminal sandbox unavailable …` 와 "auto mode is unavailable because the terminal sandbox is unavailable" 가 찍힌다(print 모드는 시작 때 찍힘, ACP 는 session/new 뒤). 8.9k 토큰.
- 결론: print 모드에서 `--dangerously-skip-permissions` 를 빼면 기본 프리셋이 작업 폴더 밖 파일·셸을 거절한다. 구멍은 임시 폴더(`/tmp` 전체 허용)이고, B 처럼 명시 deny(`read_file(/tmp)`, `write_file(/tmp)`, 플랫폼 `$TMPDIR`)로 막을 수 있을 것으로 본다(조합은 재지 않음; 작업 폴더가 그 아래면 deny 가 이겨 작업도 막힌다). 지금 `delegate.sh` 는 agy 를 `--dangerously-skip-permissions` 로 돌려 이 보호를 모두 끈다. 재지 않은 것: `read_url`, 임시 폴더 deny 와 작업 폴더의 조합, OS 샌드박스가 있는 호스트에서 셸이 샌드박스 안에서 허용될 때의 범위.
- 로그: `/tmp/acpprobe-3/out{C,D,E,F}.json`, `home{C,D,E,F}/.gemini/antigravity-cli/log/`.

## 드라이버 기본 정책
OS 격리가 없는 곳(uid 격리도, 동작하는 OS 샌드박스도 없음, 비개발자 동료의 기본 환경)의 기본은 "읽기 전용 의견"이다. 위 실측 결과와 상관없이 사용자가 정했다.
- 격리 판정(모델 호출 없이 `doctor` 와 `run` 시작 때):
  - uid 격리: root 이고 `setpriv` 로 작업 uid 가 메인 작업 트리 쓰기, HOME 비밀(`~/.claude/.credentials.json`, `.git-credentials`, `.ssh`) 읽기에 실패한다(지금 `doctor` 검사).
  - codex OS 샌드박스: `codex sandbox` 자가 시험. 권한 프로필로 `~/.ssh` 읽기, worktree 밖 쓰기, `git push` 가 모두 실패하고 worktree 안 쓰기는 성공해야 통과.
  - agy OS 샌드박스: ACP 서버 시작 로그에 `Terminal sandbox unavailable` 줄이 없다. 이 샌드박스는 셸 명령만 감싸고 파일 도구는 위 실측처럼 따로 돈다. 파일 도구도 막는지 재기 전까지 agy 는 uid 격리가 있을 때만 worktree 모드로 연다.
- 모드:
  - `worktree`(격리 있음): worktree 안 편집과 셸 허용. 바뀐 내용은 `diff.patch` 로 참고용 수집, 메인에 그대로 적용하지 않는다.
  - `empty`(읽기 전용 의견, 격리 없을 때 기본이자 유일): 드라이버가 필요한 파일만 비밀 없이(`.env`, 키, 자격 증명 파일 제외) 버릴 임시 사본에 복사하고 그 사본을 cwd 로 돌린다. 셸 요청은 거절한다. 끝나면 사본의 변경은 버리고 보고만 남긴다. 지금 `empty` 모드에 가깝다.
- 한계: `empty` 는 보안 경계가 아니다. 에이전트는 사용자 권한으로 돌므로 파일 도구로 HOME 비밀을 읽을 수 있다. 사본은 에이전트가 보는 범위와 쓰기가 남는 곳을 줄일 뿐이다. 작업용 `--gemini-dir`·`CODEX_HOME` 에는 인증 파일만 넣는다.
