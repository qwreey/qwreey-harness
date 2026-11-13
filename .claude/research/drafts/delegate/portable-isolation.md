---
format: 1
title: delegate 를 root 없이 macOS·Windows·Linux 에서 돌리는 방안
description: codex 는 exec + 권한 프로필과 작업별 CODEX_HOME 으로 root 없이 가능(OS 샌드박스가 있는 곳). agy 는 ACP 권한 응답이 셸 명령만 묻고 파일 읽기·쓰기는 워크스페이스 밖이어도 묻지 않아(실측), OS 격리 없이는 격리되지 않는다
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
- agy: ACP 클라이언트로. accept-edits, `toolPermission: proceed-in-sandbox`, deny `write_file`(메인 저장소)·`read_file(~)`·`read_url(*)`. 권한 요청은 worktree 안 편집만 허가. OS 샌드박스가 없으면 명령 요청을 전부 거절하는 셸 없는 모드(codex `empty` 에 해당).
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
- 결론: OS 격리(uid 분리, 컨테이너, OS 샌드박스)가 없으면 agy 는 ACP 만으로 격리되지 않는다. 위 "권장 설계"의 agy 항목(worktree 안 편집만 허가)은 이 호스트에서 성립하지 않는다. OS 샌드박스가 있는 macOS·Windows·userns 켜진 Linux 에서 파일 도구도 막히는지는 아직 모른다. 남은 후보: settings `permissions.deny/ask`(`read_file()`/`write_file()`) 가 ACP 에서 요청·거부로 이어지는지(모델 호출 1회), 이것도 프로세스 안 정책.
- 클라이언트와 로그: `/tmp/acpprobe-1/client/acp_client.py`, `/tmp/acpprobe-1/log.jsonl`.
