---
format: 1
title: qwreey-delegate 크로스플랫폼 Python 드라이버 설계
description: delegate.sh 를 stdlib Python 드라이버로 바꾸는 설계. 격리 판정(uid/codex sandbox/agy sandbox), 모드 선택 fail-closed, agy ACP·codex 어댑터, harness.env 키, 이전 단계, 시험 계획
status: active; draft for user review
---
# qwreey-delegate Python 드라이버 설계 (초안)

근거: `portable-isolation.md`(실측과 기본 정책), 지금 `plugins/qwreey-delegate/skills/delegate/scripts/delegate.sh`, `trial-2026-11-10.md`.
사용자: "root 가 없기도…agy 쪽엔 acp…codex 에는 많은 command line arguments", "delegate 랑 subagent 운용은 다를 수 있어…uid 격리는 windows 에서 먹지 않는 부분", "구독을 다중으로…여러 모델을 쓰는 사람도 있는데 안 그런 사람도 많고", agy 격리 규칙에 대해 "옵션을 주는건 괜찮을것 같아".
표시: [실측] 이 호스트에서 잼, [문서] 공식 문서·help, [추정] 재지 않음.

## 1. 목표와 비목표

| 목표 | 비목표 |
|---|---|
| root 없이 Linux·macOS·Windows 에서 돈다. 격리가 없으면 codex 는 `empty`(읽기 전용 의견)로 내려가고, agy 는 기본으로 꺼진다(사용자가 위험을 받아들여 켜면 `empty`, §3·§4.3) | 격리가 없는 곳에서 `empty` 를 보안 경계로 만들기(정책상 경계가 아님) |
| agy·codex 중 있는 것만 쓴다. 둘 다 없어도 오류가 아니라 "쓸 수 없음, Claude 서브에이전트로" 안내 | 세 번째 벤더 추가(어댑터 경계만 열어 둠) |
| 지금 명령 표면과 작업 폴더 꼴을 유지해 SKILL 절차가 거의 그대로 | 서브에이전트 운용(qwreey-operator)과 합치기 |
| 격리 판정은 모델 호출 없이, 판정이 불확실하면 닫힌 쪽 | 결과를 메인 저장소에 자동 반영 |
| 메시지는 판단 재료(이유와 선택지)를 주고, 위험할 때만 거절 | 동시 실행 한도를 넘는 병렬화 |

## 2. delegate.sh 에서 유지와 변경

지금 명령: `run`, `collect`, `remove`, `list`, `gc`, `doctor`, `register`(7개, 스크립트 머리와 case 문).

| 항목 | 지금 | 드라이버 |
|---|---|---|
| 명령과 인자 | 위 7개, `--repo --mode --ref --model --effort --timeout`, `--discard --delete-branch`, `--all --days --apply` | 그대로. `run` 에 `empty` 용 `--files <경로…>` 추가(§6). `doctor --json` 추가(스킬이 쓸 수 있는 에이전트·모드를 읽음) |
| 수명 주기 | run → collect → remove, gc 미리보기 기본 | 그대로 |
| 작업 폴더 | `<dirname(ROOT)>/<key>-<agent>/{<name>/, .homes/, .hooks/, runs/}` | uid 백엔드는 그대로(`conventions.md` §1, 기존 runs 를 그 자리에서 찾음). uid 가 없으면 플랫폼 상태 폴더 아래(§6): 동료의 저장소 옆(Documents, OneDrive 동기화 폴더)에 사본과 토큰을 두지 않는다. `.delegate/` 의 pid·exit·collected 는 `state.json` 하나로, 옛 파일도 읽음 |
| 격리 | 모든 모드가 setpriv uid(root 필수) | 백엔드 셋 중 판정된 것(§4). uid 는 Linux root 의 선택 강화층 |
| agy 호출 | `agy -p … --dangerously-skip-permissions`, 셸·파일 모두 무조건 허용 | ACP 클라이언트(§5). 셸 요청을 모드에 따라 허가·거절. print 방식은 uid 백엔드 전용 대체 경로로만 남김 |
| codex 호출 | `exec -s read-only --ignore-user-config …`, worktree 는 거부 | 작업별 `CODEX_HOME` 의 권한 프로필 + OS 샌드박스 자가 시험 통과 시 worktree 허용 |
| HOME | `.gemini` 통째 복사 후 기록 삭제 | 인증 파일만 복사(agy 는 `antigravity-oauth-token` 하나면 됨 [실측]) |
| 환경 | `env -i` + mise PATH + `/usr/bin:/bin` | 같은 원칙, 플랫폼별 최소 변수(Windows 는 `SYSTEMROOT`, `COMSPEC`, `PATHEXT`, `TEMP` 필요) |
| 잠금·동시 실행 | `/tmp/delegate-<agent>.lock` flock, pid 를 `kill -0` | OS 파일 잠금(§6). Windows 에서 `os.kill(pid, 0)` 은 프로세스를 끝내므로 쓰지 않음 |
| guard | 메인 HEAD·status 해시 전후 비교, worktree 변경 목록 | 그대로 + ACP 도구 호출 경로 감시(§4 표지선) |
| pre-push 훅 | `GIT_CONFIG_*` 로 `core.hooksPath` | 그대로(Windows git 도 훅을 sh 로 돌림 [추정]) |
| OOM 우선 희생 | `choom -n 1000` | Linux 는 `harness_env.heavy_wrap()`, 다른 OS 는 낮은 우선순위만(`os.nice`, Windows `BELOW_NORMAL_PRIORITY_CLASS`) |
| 실행 중 스크립트 수정 | 임시 사본으로 재실행 | Python 은 시작 때 모듈을 다 읽으므로 import·템플릿 읽기를 시작에 몰아 둠. 재실행 불필요 |
| 종료 코드 | 실행 완료면 0(모델 rc 는 guard) | 0 완료, 2 사용법, 3 에이전트 없음, 4 격리 정책으로 거절, 5 동시 실행 한도. 모델 rc 는 guard·state |

## 3. 플랫폼 표

모드: `worktree` = 저장소 사본에서 편집·셸 허용. `empty` = 셸 거절, 변경 버림, 보고만 남김. 같은 `empty` 라도 뜻이 다르다:
- codex `empty`: 읽기 전용 의견. OS 샌드박스 자가 시험이 통과했거나, Linux 에서 bwrap 이 뜨지 않아 셸이 아예 돌지 않을 때만(§5.2). 그 밖은 셸 없는 설정이 확인될 때까지 거절.
- agy `empty`: **제한된 사본, 강제 아님.** cwd 가 빈 폴더(또는 `--files` 사본)이고 셸은 거절되지만, 파일 도구는 사용자 권한으로 밖을 묻지 않고 읽고 쓴다 [실측]. `read_url` 은 미측. uid 백엔드 아래에서만 실제로 밖 쓰기가 막힌다. 그래서 uid 격리가 없으면(agy 셸 샌드박스는 셸만 감싸고 empty 는 셸을 이미 거절하므로 empty 에는 보탬이 없다) agy 는 모드와 상관없이 **기본으로 꺼진다**(`run` exit 4, `doctor` 가 이유를 보임). `HARNESS_DELEGATE_AGY_UNISOLATED=allow` 를 둔 사용자만 격리 없는 agy `empty` 를 쓴다(§4.3). M4 에서 SKILL·README 도 이 문구로 바꾼다.

agy 열: "꺼짐" = 격리가 없어 기본으로 막힘, `allow` = `HARNESS_DELEGATE_AGY_UNISOLATED=allow` 일 때 empty 만, 열림 = `HARNESS_DELEGATE_AGY_WORKTREE=sandbox`(§4.3). 열림은 셸 샌드박스의 양성 신호가 있는 곳에서만 효력이 있다.

| 환경 | 격리 백엔드 | agy | codex | 근거 |
|---|---|---|---|---|
| Linux root, userns 꺼짐(이 호스트) | uid | worktree·empty | empty(`-s read-only`, 셸 안 돎). worktree 는 거부(uid 아래 bwrap 실패), `danger-full-access`+uid 는 사용자 결정 | [실측] |
| Linux root, userns 켜짐 | uid, codex bwrap | worktree·empty | 자가 시험 통과 시 worktree·empty | uid 아래 bwrap 동작 [추정] |
| Linux 비root, userns 켜짐 | codex bwrap, agy 셸 샌드박스(양성 신호 필요, §4.1) | 꺼짐 / `allow` empty. 검증된 셸 샌드박스 + `sandbox` 키면 worktree | 자가 시험 통과 시 worktree·empty | [문서]. agy 의 "샌드박스 있음" 로그는 아직 본 적 없음 |
| Linux 비root, userns 꺼짐 | 없음 | 꺼짐 / `allow` empty | empty(셸이 돌지 않음) | agy [실측], codex [실측] |
| macOS | codex Seatbelt, agy Seatbelt(셸만) | 꺼짐 / `allow` empty. 열림 키는 무시(알려진 신호 없음) | 자가 시험 통과 시 worktree·empty, 실패 시 §5.2 | [문서], 미측 |
| Windows 11 24H2 26100.9278+ | codex MXC, agy AppContainer(2026-08 업데이트+) | 꺼짐 / `allow` empty. 열림 키는 무시(알려진 신호 없음) | 자가 시험 통과 시 worktree·empty. `unelevated` 는 읽기를 막지 않아 시험에서 떨어짐 → §5.2 | [문서], 미측 |
| 그 밖의 Windows·알 수 없는 OS | 없음 | 꺼짐 / `allow` empty | §5.2(거절 또는 셸 끈 empty) | [추정] |

격리가 없을 때 남는 위험: agy 파일 도구는 사용자 권한으로 워크스페이스 밖을 묻지 않고 읽고 쓴다(모든 행, [실측 Linux]). "샌드박스가 안 되면 codex 셸이 돌지 않는다"는 Linux(bwrap 실패) 실측뿐이다. macOS·Windows 에서 샌드박스가 떠도 새는 경우(Windows `unelevated` 처럼)는 셸이 돌며 읽기가 열릴 수 있어 `-s read-only` 로 내리지 않는다(§5.2).

## 4. 격리 판정과 모드 선택

### 4.1 판정 (`doctor` 와 `run` 시작 때 매번, 모델 호출 없음)

| 백엔드 | 통과 조건 | 실패 시 |
|---|---|---|
| uid | Linux, euid 0, `setpriv` 있음, uid 가 passwd 에 없음, 그 uid 로 ROOT 쓰기 실패, HOME 비밀(`<config_dir>/.credentials.json`, `~/.git-credentials`, `~/.ssh`) 읽기 실패. 경로는 `/code` 고정이 아니라 실행 사용자 HOME 에서 | 이 백엔드 없음 |
| codex sandbox | 양성 대조 먼저, 샌드박스 밖(드라이버 자신)에서: 미끼 파일(상태 폴더, 내용 없는 표지, 진짜 비밀은 쓰지 않음) 읽기 성공, 사본 밖 시험 경로 쓰기 성공. 그다음 `codex sandbox -P <프로필> -C <사본> -- <검사>` 로: `true` 가 exit 0(샌드박스가 떴다는 증거, bwrap 기동 실패와 거부를 가른다), 미끼 읽기 실패, 사본 밖 쓰기 실패, 사본 안 쓰기 성공, 네트워크 실패. 대조가 하나라도 어긋나면 판정 불가 = 실패 | codex 는 §5.2 의 empty 규칙 |
| agy 셸 샌드박스 | 셋 다 필요. (1) agy 버전이 허용 목록(`DEFAULT_AGY_SANDBOX_VERSIONS`, 로그 꼴을 잰 판: 1.5.7·1.5.8)에 있음, 밖이면 없음으로. (2) `agy acp` 를 task_home(토큰 사본)으로 띄워 `initialize`·`session/new` 까지(프롬프트 없음, 모델 호출 없을 것으로 [추정]) 진행한 뒤 서버 로그에 `Terminal sandbox unavailable` 이 없음. 이 줄은 `session/new` 뒤에야 찍히고(로그 87-91행, session/new 는 5행), 아예 안 찍힌 로그도 하나 있었다 [실측]: 그래서 줄 부재는 필요조건일 뿐 양성 신호가 아니다. (3) Linux: 드라이버가 따로 비특권 userns 를 확인(`unshare -U true` 또는 `bwrap --unshare-user true` 성공). macOS·Windows 는 알려진 양성 신호가 없어 언제나 없음 | 열림 설정이어도 agy worktree 거절 |

검사 하나라도 오류(시간 초과, 실행 파일 없음, 알 수 없는 출력)면 그 백엔드는 없는 것으로 본다. 결과는 캐시하지 않는다(uid 검사는 ms, codex 시험은 초 단위, agy 는 서버 기동 수 초 [추정]). agy 판정은 열림 키가 `sandbox` 일 때만 돌린다.

### 4.2 모드 선택

| 요청 | 허용됨 | 허용 안 됨 |
|---|---|---|
| `--mode` 없음 | agy: worktree, codex: empty(지금 기본 유지) | 한 단계 내려 empty 로 돌고 `mode: empty (이유)` 를 출력 |
| `--mode worktree` 명시 | 그대로 | exit 4, 이유와 선택지(`--mode empty`, 설정 키, Claude 서브에이전트). 조용히 내리지 않는다: 모델은 셸로 시험을 돌릴 줄 알고 맡겼다 |
| `--mode empty` | codex: §5.2 조건. agy: 격리가 있거나 `UNISOLATED=allow` | exit 4 |
| agy, 격리 없음 | `HARNESS_DELEGATE_AGY_UNISOLATED=allow` 이면 empty 만(worktree 요청은 exit 4) | 모드와 상관없이 exit 4. 이유와 선택지(codex, Claude 서브에이전트, 위험을 받아들이면 그 키) |

fail-closed 규칙: 알 수 없는 플랫폼·버전은 격리 없음(codex 는 §5.2, agy 는 꺼짐). ACP 권한 요청의 kind 가 `execute` 가 아니면 거절하고 기록. 설치된 `harness_env` 가 이 드라이버의 USER_ONLY 키를 모르면 저장소 층을 읽지 않는다(§7).

### 4.3 agy worktree 규칙 (사용자 결정 반영)

- 기본: agy `worktree` 는 uid 백엔드가 있을 때만. uid 격리가 없으면 agy 는 empty 도 막힌다(exit 4). 검증된 agy 셸 샌드박스는 `sandbox` 키의 worktree 판정에만 쓰고 empty 를 열지 않는다(파일 도구는 샌드박스 밖).
- 선택 키 `HARNESS_DELEGATE_AGY_UNISOLATED`: 빈 값(기본) | `allow`. `allow` 는 격리 없이 agy `empty` 만 연다(worktree 는 열지 않음). USER_ONLY. 위험(키 설명, `doctor`, `run` 시작 줄에 그대로): agy 파일 도구는 사용자 권한으로 HOME 비밀(`~/.ssh`, 자격 증명 파일, 다른 저장소)을 읽고 워크스페이스 밖에 묻지 않고 쓴다 [실측 Linux]. 드라이버가 할 수 있는 것은 §4.4 의 감지와 세션 취소뿐이고, 쓰기는 이미 끝났을 수 있다. 시작 줄: `agy without isolation (HARNESS_DELEGATE_AGY_UNISOLATED=allow): file tools can read your secrets and write outside; detection and cancel only`.
- 선택 키 `HARNESS_DELEGATE_AGY_WORKTREE`: `uid`(기본) | `sandbox`. `sandbox` 는 uid 가 없어도 agy 셸 샌드박스가 §4.1 의 양성 판정을 받으면 worktree 를 연다. 지금 그 판정이 날 수 있는 곳은 userns 가 켜진 Linux 뿐이고, macOS·Windows 에서는 신호를 잴 때까지 이 값을 받지 않는다(`doctor` 가 "set but not honored on this platform" 으로 알림). USER_ONLY 로 둔다: 커밋된 저장소 파일이 격리를 풀 수 있으면 안 된다.
- `sandbox` 의 위험(키 설명과 `doctor` 출력에 그대로): 셸 명령만 OS 샌드박스에 들어가고, agy 파일 도구(`read_file`, `write_file`)는 사용자 권한으로 워크스페이스 밖, 메인 작업 트리, `.git`, HOME 비밀까지 묻지 않고 읽고 쓴다(ACP, settings `permissions` deny·ask 도 막지 못함 [실측, OS 샌드박스 없는 Linux]). OS 샌드박스 아래에서 파일 도구도 막히는지는 미측이다.
- 셸 샌드박스도 없는 곳의 agy worktree 는 값으로 제공하지 않는다: 그때 셸은 사용자 권한 그대로라 격리가 0 이다.
- 키가 `sandbox` 이면 `run` 시작 줄에 `agy worktree without uid isolation (HARNESS_DELEGATE_AGY_WORKTREE=sandbox): file tools are not confined` 를 찍는다.
- macOS·Win11 에서 파일 도구가 막힌다고 실측되면 그 플랫폼은 기본을 바꿀지 사용자에게 다시 묻는다.

### 4.4 표지선 (막지는 못하고 알림)

- ACP `session/update` 의 도구 호출(kind `read`·`edit`, `locations`)을 `.delegate/acp.jsonl` 에 남긴다. 경로가 사본 밖이면 `session/cancel` 로 세션을 멈추고 guard 에 `outside access: <경로>` 를 적는다. 쓰기는 알림 전에 이미 끝났을 수 있다(요청 없이 `completed` [실측], 알림 순서 [추정]).
- 메인 HEAD·status 해시 비교는 그대로.

## 5. 에이전트 어댑터

어댑터 경계: `probe() -> 버전·인증 유무`, `prepare_home(task_home)`, `launch(workspace, prompt, mode, isolation) -> rc`, `report_fallback()`.

### 5.1 agy (ACP)

| 단계 | 내용 |
|---|---|
| 시작 | `agy acp --gemini-dir <task_home>/gemini`, Popen `cwd=<사본>`(session/new 의 cwd 는 무시됨 [실측]), env 의 HOME 도 task_home(`~/.config/antigravity/plugin-secrets.json` 을 HOME 에서 읽음 [실측]) |
| 메시지 | NDJSON, 응답 id 는 문자열 [실측]. `initialize` → `session/new`(models 목록에서 `--model` 확인, 없으면 목록과 함께 exit 2) → `session/set_model` → `session/prompt`(머리말+과제) → `session/update` 를 모으며 응답(stopReason)까지 |
| 권한 | `request_permission` kind `execute`: worktree 이고 격리 백엔드가 있으면 `allow_once`, 아니면 `reject_once`(거절된 셸은 실행 안 됨 [실측]). 그 밖의 kind 는 거절 |
| 보고서 | worktree: 모델이 `REPORT.md` 를 쓴다. empty 또는 누락: `agent_message_chunk` 를 이어 붙인 마지막 답 |
| 시간 | 전체 `--timeout`, 무응답 시간 제한, 초과 시 `session/cancel` 뒤 프로세스 트리 종료 |
| 인증 | `<HARNESS_DELEGATE_AGY_HOME>/antigravity-cli/antigravity-oauth-token` 만 복사 [실측 Linux]. macOS Keychain·Windows 자격 저장소 여부 [추정, 미측] |
| uid 백엔드 | 같은 ACP 를 setpriv 아래로. print 방식(`-p --dangerously-skip-permissions`)은 M1 동등성 단계와 ACP 장애 때의 대체로만 |

`_meta.antigravity.systemPrompt.append`(initialize 응답에 있음 [실행])로 머리말을 시스템 쪽에 넣는 것은 재지 않았다. 처음엔 사용자 프롬프트에 붙인다.

### 5.2 codex (CLI)

- 작업별 `CODEX_HOME=<task_home>/codex`: `auth.json` 사본(0600) + 드라이버가 쓰는 `config.toml`(권한 프로필 둘).
  - `deleg-ro`(empty): `extends=":workspace"` 읽기만, `":root"="deny"`, `":minimal"="read"`, `network.enabled=false`.
  - `deleg-rw`(worktree): 사본 쓰기, `.git` 읽기 전용(`:workspace` 기본 [문서]), 나머지 같음. worktree 의 gitdir 는 메인 `.git/worktrees/<id>` 라 사본 밖이므로 커밋 불가 [추정].
- 실행: `codex exec -m <model> -c model_reasoning_effort=<e> -c approval_policy=never --skip-git-repo-check --ephemeral --color never --json --disable apps,browser_use,computer_use,plugins -C <사본> -o <last> -`(stdin 프롬프트). `--json` 이벤트는 `.delegate/events.jsonl`.
- `--ignore-user-config` 가 작업 CODEX_HOME 의 `config.toml` 까지 무시하는지 미측. 무시하면 프로필을 `-c` 로 넘기거나 이 옵션을 뺀다(우리 파일이라). M3 에서 잰다.
- 자가 시험이 실패했을 때의 empty:
  - Linux(uid 백엔드 포함): 지금처럼 `-s read-only`. bwrap 이 뜨지 않아 셸이 하나도 안 돈다 [실측, Linux 만]. `-s` 를 주면 프로필 대신 옛 방식이 쓰인다 [문서].
  - macOS·Windows·그 밖: `-s read-only` 로 내리지 않는다. 샌드박스가 떠도 새는 경우(Windows `unelevated` 는 읽기를 막지 않음 [문서]) 셸이 돌며 디스크를 읽는다. 셸 도구를 끄는 codex 설정이 있다고 확인되면(키 이름 미확인 [추정], M3 에서 잼) 셸 없는 empty 로 돌고, 없으면 exit 4(이유: "codex sandbox self-test failed; no shell-less mode verified").
- `HARNESS_DELEGATE_CODEX_SANDBOX=danger-full-access` 는 uid 백엔드에서만 받는다. uid 가 없으면 이 값은 exit 4.

### 5.3 인증 사본의 위험

작업 사본에서 토큰이 갱신되면 원본 refresh token 이 무효가 될 수 있다 [추정]. 드라이버는 끝날 때 사본 토큰이 바뀌었는지 비교해 `state.json`·guard 에 `token refreshed in task` 를 적는다. 되쓰기 여부는 아래 측정 뒤 정한다(Q3).
- 관문: refresh token 이 한 번 쓰면 바뀌는지(회전, 옛 토큰 무효) agy·codex 각각 재는 것을 M3 를 동료에게 내놓기 전의 조건으로 둔다. 회전한다면 동료의 원본 로그인이 위임 한 번에 끊길 수 있다.
- 회전이 일회용이면 후보: 비교 후 교체(compare-and-swap). 복사 때 원본의 해시·mtime 을 기록해 두고, 끝날 때 사본이 바뀌었고 원본은 그대로면 사본을 원본 자리에 원자적으로 쓴다(임시 파일 + `os.replace`). 원본도 바뀌었으면(사용자가 그사이 로그인) 쓰지 않고 알림만. 회전하지 않으면 되쓰지 않고 알림만 남긴다.

## 6. 작업 사본, 수집, 정리, 상태

| 항목 | 설계 |
|---|---|
| worktree 모드 | 지금과 같이 `git worktree add --detach <사본> <commit>`. uid 백엔드면 사본·admin dir·task_home 을 chown. 공유 clone 도 검토했으나 agy 파일 도구가 풀려 있으면 어느 쪽이든 메인에 쓸 수 있고, `git worktree list` 로 찾는 장점을 잃어 택하지 않음 |
| empty 모드 | 빈 폴더(지금과 같음). `--files` 를 주면 `--ref` 커밋의 **추적 파일만** `git ls-tree`·`git cat-file --batch` 로 복사(추적 안 되는 `.env` 는 처음부터 안 들어감). 비밀 이름 거름: 기본 `.env*`, `*.pem`, `*.key`, `*.p12`, `*.pfx`, `id_rsa*`, `id_ed25519*`, `.npmrc`, `.pypirc`, `.netrc`, `.git-credentials`, `*credentials*.json`, `.claude/harness.local.env`, `.claude/settings.local.json` + `HARNESS_DELEGATE_SECRET_GLOBS` |
| 수집 | `collect` 가 `runs/<YYYYMMDD-HHMM>-<name>/` 에 prompt, report, guard, meta, stdout, state, `acp.jsonl`/`events.jsonl`, worktree 면 `diff.patch`(새 파일 포함, 참고용), agy 의 `brain/*/scratch` 와 transcript. empty 는 diff 없음(변경은 버림) |
| 정리 | `remove`(collect 전 거절, `--discard`), `gc`(미리보기 기본, 옛 꼴 인식 유지). "프로세스가 사본 안에서 도는지" 는 Linux `/proc/*/cwd` 만, 다른 OS 는 실행 잠금으로 판단 |
| 실행 잠금 | `.delegate/run.lock` 을 실행 내내 잡는다(POSIX `fcntl.flock`, Windows `msvcrt.locking`). 잡을 수 없으면 running. pid 재사용과 남은 잠금 파일 문제가 없다(`O_EXCL` 대신) |
| 동시 실행 | 상태 폴더 `slots/<agent>-<n>.lock` N 개 중 빈 것을 비차단으로 잡음(N = `HARNESS_DELEGATE_MAX_CONCURRENT`, 저장소 합계) |
| 프로세스 트리 | POSIX `start_new_session` + `killpg`, Windows Job Object(ctypes, 닫히면 종료) [추정, 미측] |
| 상태 폴더 | Linux `$XDG_STATE_HOME/qwreey-delegate`(기본 `~/.local/state`), macOS `~/Library/Application Support/qwreey-delegate`, Windows `%LOCALAPPDATA%\qwreey-delegate`(동기화되지 않는 로컬 폴더). 슬롯 잠금, 미끼 파일을 둔다 |
| 작업 폴더 위치 | uid 백엔드: 지금처럼 `<dirname(ROOT)>/<key>-<agent>/`(uid 소유 chown, 기존 runs). uid 없음: `<상태 폴더>/work/<key>-<ROOT 해시 8자>-<agent>/{<name>/, .homes/, .hooks/, runs/}`. 해시는 이름이 같은 두 저장소를 가른다. `runs/` 는 보존 기록이라 임시 폴더가 아니라 상태 폴더. `list`·`gc` 는 두 위치를 다 본다 |
| state.json | 원자적 쓰기(임시 파일 + `os.replace`). 필드: agent, mode, isolation 백엔드, repo, commit, model, started/finished, rc, collected, token_refreshed |

## 7. 설정

harness.env 층(`load_layers(ROOT)`) 하나로 읽는다. 옛 `DELEGATE_*` 이름은 배포 전 스크립트의 환경 변수였고 어느 harness.env 에도 없으므로, 호환 없이 새 이름으로 바꾼다(아래 "옛 이름" 열은 대응만 적는다).

| 키 | 기본 | USER_ONLY | 옛 이름 |
|---|---|---|---|
| `HARNESS_DELEGATE_REGISTRY` | 스킬 옆 사본 | 예(기존) | `DELEGATE_REGISTRY` |
| `HARNESS_TOOL_INSTALLS`, `HARNESS_HEAVY_WRAP` | 기존 | 예(기존) | - |
| `HARNESS_DELEGATE_AGY_BIN`, `HARNESS_DELEGATE_CODEX_BIN` | PATH 의 `agy`/`codex`, 없으면 `HARNESS_TOOL_INSTALLS` 아래 | 예(실행 파일) | `DELEGATE_AGY_BIN`, `DELEGATE_CODEX_BIN` |
| `HARNESS_DELEGATE_AGY_HOME` | `~/.gemini` | 예(인증 위치) | `DELEGATE_GEMINI_SRC` |
| `HARNESS_DELEGATE_CODEX_HOME` | `$CODEX_HOME`, 없으면 `~/.codex` | 예 | `DELEGATE_CODEX_AUTH`(파일) |
| `HARNESS_DELEGATE_AGY_WORKTREE` | `uid` | 예(보안 게이트) | 새 키(§4.3) |
| `HARNESS_DELEGATE_AGY_UNISOLATED` | 빈 값(격리 없으면 agy 꺼짐) | 예(보안 게이트) | 새 키(§4.3), `allow` 면 격리 없는 agy empty |
| `HARNESS_DELEGATE_CODEX_SANDBOX` | 빈 값(프로필) | 예(보안 게이트) | `DELEGATE_CODEX_SANDBOX` |
| `HARNESS_DELEGATE_KEEP_ENV` | 빈 값 | 예(환경 누출) | `DELEGATE_KEEP_ENV` |
| `HARNESS_DELEGATE_STATE` | 플랫폼 상태 폴더 | 예(경로) | `/tmp` 잠금 |
| `HARNESS_DELEGATE_MAX_CONCURRENT` | 1 | 예(한도는 사용자 구독) | `DELEGATE_MAX_CONCURRENT` |
| `HARNESS_DELEGATE_AGY_MODEL`, `HARNESS_DELEGATE_CODEX_MODEL` | `gemini-3.8-flash-high`, `gpt-6-luna` | 아니오(저장소가 정해도 무해) | 스크립트 고정값 |
| `HARNESS_DELEGATE_SECRET_GLOBS` | 빈 값(기본 목록에 더함) | 아니오(더하기만 됨, 더 엄격해질 뿐) | - |

- 새 키는 정본 `home/.claude/lib/harness_env.py` 의 `DEFAULTS`·`USER_ONLY` 에 넣고 `python3 -I tools/sync-copies.py --apply`, `tools/tests/test-harness-env.py` 에 USER_ONLY 검사 추가.
- 설치된 `~/.claude/lib/harness_env.py` 가 옛 판이라 새 USER_ONLY 키를 모르면 저장소 층이 격리를 풀 수 있다. 드라이버는 `installed()` 모듈의 `USER_ONLY` 가 위 "예" 키를 모두 포함하는지 보고, 아니면 자기 옆 사본을 쓴다.
- `DELEGATE_AGY_FULL_HOME` 은 없앤다(토큰 하나로 인증됨 [실측]). print 대체 경로에서만 M4 까지 유지.
- `registry.tsv`: uid 백엔드 전용으로 남긴다(열·`register` 그대로). uid 가 없는 환경은 등록 없이 돈다: key = `basename(ROOT)`, setup 없음(registry 에 줄이 있으면 setup 을 쓰되 사용자 권한으로). setup 은 명령 실행이므로 저장소 층으로 옮기지 않는다.

## 8. Python 제약

- 표준 라이브러리만, 진입은 `python3 -I <skill>/scripts/delegate.py`. 하한 3.11(저장소 README 전제). `-I` 는 3.11 부터 `-P` 를 포함해 스크립트 폴더가 `sys.path` 에 없으므로 드라이버가 자기 폴더를 직접 넣는다(지금 `harness_value()` 와 같은 방식).
- 파일: `delegate.py`(CLI·명령), `delegate_isolation.py`, `delegate_acp.py`, `delegate_codex.py`, `delegate_workspace.py`, 그리고 `harness_env.py` 사본(`@copy-of`, 지금 그대로). 모든 import 는 시작에(실행 중 플러그인 파일이 바뀌어도 돌던 작업이 깨지지 않게).
- ACP 클라이언트는 다른 플러그인(qwreey-debate 의 제3 목소리 등)이 쓸 수 있지만, 쓰는 곳이 둘이 되기 전까지 `lib/` 로 올리지 않는다.
- 정책 값(비밀 이름 목록, 시간 제한, 모델)은 `DEFAULT_*` 상수 + 설정 키, 불변 값(ACP 메서드 이름, 종료 코드)은 상수.
- Windows 의 `python3` 이름(py 런처, Store 스텁)은 미측. `doctor` 가 인터프리터 경로를 출력.

## 9. 이전, 시험, 단계

### 9.1 이전 원칙
- 훅·스크립트는 이 저장소에서 바로 돈다. 돌고 있는 세션의 SKILL 은 `${CLAUDE_SKILL_DIR}/scripts/delegate.sh` 를 부르므로 **그 경로를 지우지 않는다.**
- 전환(M4)은 `delegate.sh` 를 `exec python3 -I "$(dirname …)/delegate.py" "$@"` 셈으로 바꾸는 것. 지금 스크립트는 시작하자마자 임시 사본으로 재실행하므로, 이미 돌던 작업은 옛 본문으로 끝난다.
- `qwreey-proc-guard/hooks/heavy-proc-guard.py` 가 명령의 `delegate.sh` 문자열로 예외를 준다. 셈을 남기면 그대로 통하고, SKILL 이 `delegate.py` 를 직접 부르게 바꿀 때는 그 훅의 패턴도 같이 바꾼다.
- 옛 작업 폴더(`.delegate/pid|exit|collected`, 옛 `.home`, 브랜치 worktree)는 `list`·`gc`·`remove` 가 계속 인식.

### 9.2 시험

| 무엇 | 이 호스트 | 사용자 기기 |
|---|---|---|
| 모드 선택 표, 인자, state.json, 비밀 거름, 설정 층·USER_ONLY 방어 | 단위 시험 `tools/tests/test-delegate-*.py` | - |
| 가짜 agy(ACP NDJSON 서버: 권한 요청, 사본 밖 도구 호출), 가짜 codex | run→collect→remove→gc, 표지선 cancel, 동시 실행 거절 | - |
| uid 백엔드 | 실제 `doctor --all`, 실제 run 백엔드당 1회(사용자 동의, agy 1턴 약 2.5만 토큰 [실측]) | - |
| 비root, userns 꺼짐 | 드라이버 자체를 setpriv 로 무권한 uid 아래 돌려 흉내: codex 는 empty 만, agy 는 exit 4, `UNISOLATED=allow` 면 agy empty 와 셸 거절 | - |
| codex 권한 프로필 자가 시험 | 가짜 codex 로 코드 경로와 양성 대조(대조 실패 → 판정 불가)만(bwrap 불가) | macOS·Win11: 실제 `codex sandbox` 통과/실패, `--ignore-user-config` 와 CODEX_HOME config, 셸 도구를 끄는 설정 |
| agy 셸 샌드박스 판정 | 음성만 잴 수 있음: `session/new` 뒤 `Terminal sandbox unavailable` 줄이 찍히고 `unshare -U` 가 실패해 "없음" 이 나와야 함. initialize 만으로는 줄이 없어 거짓 양성이 됨 [실측] | userns 켜진 Linux: 양성 로그 꼴. macOS·Win11: 쓸 만한 양성 신호가 있는지 |
| 인증 위치, 토큰 회전(M3 관문) | agy·codex 각각: 사본에서 갱신이 일어난 뒤 원본 토큰이 아직 통하는지(사용자 동의, 실제 호출) | macOS: 토큰 파일인지 Keychain 인지 |
| agy 파일 도구가 OS 샌드박스 아래 막히는지 | 불가 | macOS·Win11: `portable-isolation.md` 의 `acpprobe` 와 같은 1턴 |
| Windows 고유 | - | 잠금(msvcrt), Job Object 종료, git 훅, 긴 경로, py 런처 |

### 9.3 단계

| 단계 | 내용 | 끝 조건 |
|---|---|---|
| M0 | 이 설계 검토 | 끝(§10) |
| M1 | `delegate.py` 동등 이식(uid 백엔드, agy print, codex 지금 꼴). `delegate.sh` 손대지 않음 | 가짜 에이전트 시험 통과, 같은 runs/ 꼴 |
| M2 | agy ACP 어댑터, 표지선 | uid 아래 실제 agy worktree·empty 각 1회 |
| M3 | 격리 판정·모드 선택, 비root empty, 상태 폴더 작업 위치, codex 프로필·자가 시험, 새 harness.env 키(정본+sync) | 비root 흉내 시험, `doctor --json`. 동료 배포 전 관문: 토큰 회전 실측(§5.3) |
| M4 | `delegate.sh` 를 셈으로, SKILL·README·how-it-works·plugin.json 요구 사항 갱신(격리 없으면 agy 꺼짐과 `UNISOLATED` 키, agy empty 는 "제한된 사본, 강제 아님", 비uid 작업 위치는 `conventions.md` §1 표에도), 버전 올림 | 세션 재시작 뒤 SKILL 이 새 경로 사용 |
| M5 | macOS·Win11 실측, §3 표의 [추정] 갱신, agy 기본 재검토 질문 | 실측 기록 추가 |
| M6 | proc-guard 패턴 갱신 뒤 SKILL 이 `delegate.py` 직접 호출. 셈은 남김(값쌈) | - |

## 10. 사용자 결정

Q1-Q6 은 권고대로 정했다(사용자 "전부 동의"). Q3 은 그 뒤 "측정 뒤 결정" 으로 바뀌었고, Q7 은 따로 정했다. Q5 는 옛 이름이 배포되지 않았으므로 호환을 두지 않는다.

| # | 결정 |
|---|---|
| Q1 | `empty` 는 빈 폴더 + 프롬프트 맥락이 기본, `--files` 로 고른 추적 파일만 넣는다 |
| Q2 | `--mode worktree` 를 명시했는데 격리가 없으면 거절(exit 4). 명시가 없을 때만 empty 로 내린다 |
| Q3 | 동료에게 내놓기 전에(M3 관문) refresh token 회전을 agy·codex 각각 잰 뒤 정한다. 회전이 일회용이면 비교 후 교체 되쓰기(§5.3), 아니면 되쓰지 않고 알림만 |
| Q4 | 비root 환경은 registry 없이 돈다(key = 폴더 이름) |
| Q5 | `DELEGATE_*` 호환 없음, 새 `HARNESS_DELEGATE_*` 이름만 |
| Q6 | codex 기본은 샌드박스가 통과해도 empty, worktree 는 명시할 때만 |
| Q7 | uid 격리가 없으면 agy 는 모든 모드에서 기본으로 꺼짐(exit 4). 위험을 받아들인 사용자만 USER_ONLY `HARNESS_DELEGATE_AGY_UNISOLATED=allow` 로 empty 를 연다(사용자 "응 추천대로 해줘") |

### 남은 측정 (진행 중, 각 1턴 정도)

agy 파일 도구를 막을 손잡이 후보 둘. 진행 중이다. 하나라도 파일 도구를 막으면 agy `empty` 가 "강제 아님" 에서 한 단계 안전해지고, 격리 없는 agy 를 기본으로 꺼 두는 Q7 을 다시 물을 근거가 된다.

| # | 측정 | 막으면 |
|---|---|---|
| M-a | ACP `session/set_mode` 로 `plan`·`accept-edits` 를 건 뒤 사본 밖 `read_file`·`write_file` 지시 | empty 를 그 모드로 연다 |
| M-b | print 방식 `-p --settings <JSON>` 의 `permissions.deny`(`read_file(<밖>)`, `write_file(<밖>)`)가 ACP 와 달리 듣는지 | empty 를 print 방식으로(셸은 settings 로 거절) |

## 11. 지금 문서·스크립트와 어긋나는 점

- `empty` 의 뜻: 정책(`portable-isolation.md`)은 "필요한 파일만 비밀 없이 복사한 사본", 스크립트·`preamble-empty.md`·`conventions.md` 는 "빈 폴더, 파일을 읽지 말 것"(Q1).
- agy `empty` 는 지금 `--dangerously-skip-permissions` 로 셸까지 허용(uid 아래). 정책의 empty 는 셸 거절.
- "`agy --sandbox`·codex `-s read-only` 가 cwd 밖을 못 막는다"는 서술이 `delegate.sh` 머리, SKILL "Isolation", how-it-works 에 일반 사실로 있으나 이 호스트(userns 꺼짐) 한정이다.
- 경로 고정: `GEMINI_SRC=/code/.gemini`, `CODEX_AUTH=/code/.codex/auth.json`, `SECRETS_PROBE=/code/…`, 설치 기본 `/code/.local/share/mise/installs`(harness_env 기본은 `~/.local/share/mise/installs`).
- `portable-isolation.md` "드라이버 기본 정책" 의 agy 판정("ACP 서버 시작 로그에 `Terminal sandbox unavailable` 줄이 없다")은 시작 직후에 보면 이 호스트에서도 거짓 양성이다. 줄은 `session/new` 뒤에 찍히고 안 찍힌 로그도 있다. 이 설계 §4.1 이 고친 판정이다.
- `portable-isolation.md` 의 "권장 설계" agy 항목(deny 규칙, worktree 안 편집만 허가)은 같은 문서의 뒤 실측으로 성립하지 않는다(문서 스스로 적음). 드라이버 항목의 `O_EXCL` 잠금은 이 설계에서 OS 파일 잠금으로 바꿈.
