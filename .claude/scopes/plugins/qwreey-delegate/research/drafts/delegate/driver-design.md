---
format: 1
title: qwreey-delegate 크로스플랫폼 Python 드라이버 설계
description: delegate.sh 를 stdlib Python 드라이버로 바꾸는 설계. 격리 판정(uid/codex sandbox/agy sandbox), 모드 선택 fail-closed, agy print 모드 권한 정책(ACP 없음)·codex 어댑터, 상태 폴더 작업 위치와 run 끝 자동 수집·정리, harness.env 키, 이전 단계, 시험 계획
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
| 수명 주기 | run → collect → remove, gc 미리보기 기본 | `run` 이 끝에 collect, 사본 확인, remove 까지 한다(§6 자동 정리). `--keep` 이면 지금처럼 collect·remove 를 따로. gc 미리보기 기본 |
| 작업 폴더 | `<dirname(ROOT)>/<key>-<agent>/{<name>/, .homes/, .hooks/, runs/}` | 모든 백엔드가 상태 폴더 아래 `<상태>/work/<key>-<agent>/`, 결과는 `<상태>/runs/<key>/<날짜>-<name>/`(§6). 저장소 옆에는 새로 아무것도 만들지 않는다(Projects 폴더가 어수선해지고, 동료의 저장소 옆은 동기화 폴더일 수 있다). 기록은 `.runs/<name>/state.json` 등 root 소유 폴더, 옛 자리와 옛 파일도 읽음 |
| 격리 | 모든 모드가 setpriv uid(root 필수) | 백엔드 셋 중 판정된 것(§4). uid 는 Linux root 의 선택 강화층 |
| agy 호출 | `agy -p … --dangerously-skip-permissions`, 셸·파일 모두 무조건 허용 | print 모드, `--dangerously-skip-permissions` 없이 `--settings` 권한 정책과 `--output-format json`(§5.1). ACP 는 쓰지 않는다(파일 도구를 막을 손잡이가 없음 [실측]) |
| codex 호출 | `exec -s read-only --ignore-user-config …`, worktree 는 거부 | 작업별 `CODEX_HOME` 의 권한 프로필 + OS 샌드박스 자가 시험 통과 시 worktree 허용 |
| HOME | `.gemini` 통째 복사 후 기록 삭제 | 인증 파일만 복사(agy 는 `antigravity-oauth-token` 하나면 됨 [실측]) |
| 환경 | `env -i` + mise PATH + `/usr/bin:/bin` | 같은 원칙, 플랫폼별 최소 변수(Windows 는 `SYSTEMROOT`, `COMSPEC`, `PATHEXT`, `TEMP` 필요) |
| 잠금·동시 실행 | `/tmp/delegate-<agent>.lock` flock, pid 를 `kill -0` | OS 파일 잠금(§6). Windows 에서 `os.kill(pid, 0)` 은 프로세스를 끝내므로 쓰지 않음 |
| guard | 메인 HEAD·status 해시 전후 비교, worktree 변경 목록 | 그대로 + agy `denied_actions`, 끝난 뒤 남은 작업 uid 프로세스 수(§4.4) |
| pre-push 훅 | `GIT_CONFIG_*` 로 `core.hooksPath` | 그대로(Windows git 도 훅을 sh 로 돌림 [추정]) |
| OOM 우선 희생 | `choom -n 1000` | Linux 는 `harness_env.heavy_wrap()`, 다른 OS 는 낮은 우선순위만(`os.nice`, Windows `BELOW_NORMAL_PRIORITY_CLASS`) |
| 실행 중 스크립트 수정 | 임시 사본으로 재실행 | Python 은 시작 때 모듈을 다 읽으므로 import·템플릿 읽기를 시작에 몰아 둠. 재실행 불필요 |
| 종료 코드 | 실행 완료면 0(모델 rc 는 guard) | 0 완료, 2 사용법, 3 에이전트 없음, 4 격리 정책으로 거절, 5 동시 실행 한도. 모델 rc 는 guard·state |

## 3. 플랫폼 표

모드: `worktree` = 저장소 사본에서 편집·셸 허용. `empty` = 셸 거절, 변경 버림, 보고만 남김. 같은 `empty` 라도 뜻이 다르다:
- codex `empty`: 읽기 전용 의견. OS 샌드박스 자가 시험이 통과했거나, Linux 에서 bwrap 이 뜨지 않아 셸이 아예 돌지 않을 때만(§5.2). 그 밖은 셸 없는 설정이 확인될 때까지 거절.
- agy `empty`: **제한된 사본, 강제 아님.** cwd 가 빈 폴더(또는 `--files` 사본)이고 셸은 거절된다. 파일 도구는 print 모드 정책(§5.1) 아래에서 작업 폴더 밖과 임시 폴더를 거절당한다 [실측 1.5.8]. 그러나 이것은 agy 자신이 지키는 규칙이지 OS 경계가 아니고 판마다 달라질 수 있다. ACP 나 `--dangerously-skip-permissions` 에서는 파일 도구가 사용자 권한으로 밖을 묻지 않고 읽고 쓴다 [실측]. `read_url` 은 print 모드 도구 목록에 없다 [모델 진술, 1.5.8]. uid 백엔드 아래에서만 OS 가 밖 쓰기를 막는다. 그래서 uid 격리가 없으면(agy 셸 샌드박스는 셸만 감싸고 empty 는 셸을 이미 거절하므로 empty 에는 보탬이 없다) agy 는 모드와 상관없이 **기본으로 꺼진다**(`run` exit 4, `doctor` 가 이유를 보임). `HARNESS_DELEGATE_AGY_UNISOLATED=allow` 를 둔 사용자만 격리 없는 agy `empty` 를 쓴다(§4.3). 이 기본을 바꾸는 제안이 사용자 확인을 기다린다(§10 P1: 잰 판에서는 print 정책 아래 empty 를 기본으로 연다). M4 에서 SKILL·README 도 이 문구로 바꾼다.

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

격리가 없을 때 남는 위험: agy 파일 도구는 사용자 권한으로 돈다. print 정책이 밖을 거절하는 것은 agy 의 규칙 판정이라, 재지 않은 판·경로 표기(링크는 대상으로 판정 [실측])에서 새면 막을 것이 없다(모든 행, [실측 Linux 1.5.8]). "샌드박스가 안 되면 codex 셸이 돌지 않는다"는 Linux(bwrap 실패) 실측뿐이다. macOS·Windows 에서 샌드박스가 떠도 새는 경우(Windows `unelevated` 처럼)는 셸이 돌며 읽기가 열릴 수 있어 `-s read-only` 로 내리지 않는다(§5.2).

## 4. 격리 판정과 모드 선택

### 4.1 판정 (`doctor` 와 `run` 시작 때 매번, 모델 호출 없음)

| 백엔드 | 통과 조건 | 실패 시 |
|---|---|---|
| uid | Linux, euid 0, `setpriv` 있음, uid 가 passwd 에 없음, 그 uid 로 ROOT 쓰기 실패, HOME 비밀(`<config_dir>/.credentials.json`, `~/.git-credentials`, `~/.ssh`) 읽기 실패. 경로는 `/code` 고정이 아니라 실행 사용자 HOME 에서 | 이 백엔드 없음 |
| codex sandbox | 양성 대조 먼저, 샌드박스 밖(드라이버 자신)에서: 미끼 파일(상태 폴더, 내용 없는 표지, 진짜 비밀은 쓰지 않음) 읽기 성공, 사본 밖 시험 경로 쓰기 성공. 그다음 `codex sandbox -P <프로필> -C <사본> -- <검사>` 로: `true` 가 exit 0(샌드박스가 떴다는 증거, bwrap 기동 실패와 거부를 가른다), 미끼 읽기 실패, 사본 밖 쓰기 실패, 사본 안 쓰기 성공, 네트워크 실패. 대조가 하나라도 어긋나면 판정 불가 = 실패 | codex 는 §5.2 의 empty 규칙 |
| agy 셸 샌드박스 | 셋 다 필요. (1) agy 버전이 허용 목록(`DEFAULT_AGY_SANDBOX_VERSIONS`, 로그 꼴을 잰 판: 1.5.7·1.5.8)에 있음, 밖이면 없음으로. (2) `agy acp` 를 task_home(토큰 사본)으로 띄워 `initialize`·`session/new` 까지(프롬프트 없음, 모델 호출 없을 것으로 [추정]) 진행한 뒤 서버 로그에 `Terminal sandbox unavailable` 이 없음. 이 줄은 `session/new` 뒤에야 찍히고(로그 87-91행, session/new 는 5행), 아예 안 찍힌 로그도 하나 있었다 [실측]: 그래서 줄 부재는 필요조건일 뿐 양성 신호가 아니다. (3) Linux: 드라이버가 따로 비특권 userns 를 확인(`unshare -U true` 또는 `bwrap --unshare-user true` 성공). macOS·Windows 는 알려진 양성 신호가 없어 언제나 없음. (2) 의 ACP 기동은 M3 에서 print 모드 시작 로그로 바꿀 후보(§11) | 열림 설정이어도 agy worktree 거절 |

검사 하나라도 오류(시간 초과, 실행 파일 없음, 알 수 없는 출력)면 그 백엔드는 없는 것으로 본다. 결과는 캐시하지 않는다(uid 검사는 ms, codex 시험은 초 단위, agy 는 서버 기동 수 초 [추정]). agy 판정은 열림 키가 `sandbox` 일 때만 돌린다.

### 4.2 모드 선택

| 요청 | 허용됨 | 허용 안 됨 |
|---|---|---|
| `--mode` 없음 | agy: worktree, codex: empty(지금 기본 유지) | 한 단계 내려 empty 로 돌고 `mode: empty (이유)` 를 출력 |
| `--mode worktree` 명시 | 그대로 | exit 4, 이유와 선택지(`--mode empty`, 설정 키, Claude 서브에이전트). 조용히 내리지 않는다: 모델은 셸로 시험을 돌릴 줄 알고 맡겼다 |
| `--mode empty` | codex: §5.2 조건. agy: 격리가 있거나 `UNISOLATED=allow` | exit 4 |
| agy, 격리 없음 | `HARNESS_DELEGATE_AGY_UNISOLATED=allow` 이면 empty 만(worktree 요청은 exit 4). 제안(§10 P1, 확인 대기): 허용 목록 판이면 키 없이도 empty | 모드와 상관없이 exit 4. 이유와 선택지(codex, Claude 서브에이전트, 위험을 받아들이면 그 키) |

fail-closed 규칙: 알 수 없는 플랫폼·버전은 격리 없음(codex 는 §5.2, agy 는 꺼짐). agy 작업 폴더가 정책이 거절하는 임시 폴더 아래면 거절(exit 4, §5.1). 드라이버는 설치된 `harness_env` 가 아니라 늘 자기 옆 사본을 써서, 옛 설치본이 드라이버의 USER_ONLY 키를 몰라도 저장소 층이 격리를 풀지 못한다(§7).

### 4.3 agy worktree 규칙 (사용자 결정 반영)

- 기본: agy `worktree` 는 uid 백엔드가 있을 때만. uid 격리가 없으면 agy 는 empty 도 막힌다(exit 4). 검증된 agy 셸 샌드박스는 `sandbox` 키의 worktree 판정에만 쓰고 empty 를 열지 않는다(파일 도구는 샌드박스 밖).
- 선택 키 `HARNESS_DELEGATE_AGY_UNISOLATED`: 빈 값(기본) | `allow`. `allow` 는 격리 없이 agy `empty` 만 연다(worktree 는 열지 않음). USER_ONLY. 위험(키 설명, `doctor`, `run` 시작 줄에 그대로): agy 파일 도구는 사용자 권한으로 HOME 비밀(`~/.ssh`, 자격 증명 파일, 다른 저장소)을 읽고 워크스페이스 밖에 묻지 않고 쓴다 [실측 Linux]. 드라이버가 할 수 있는 것은 print 정책(§5.1)과 `denied_actions` 기록뿐이다. 시작 줄: `agy without isolation (HARNESS_DELEGATE_AGY_UNISOLATED=allow): file tools run with your rights; only agy's own permission rules stand in the way`.
- 선택 키 `HARNESS_DELEGATE_AGY_WORKTREE`: `uid`(기본) | `sandbox`. `sandbox` 는 uid 가 없어도 agy 셸 샌드박스가 §4.1 의 양성 판정을 받으면 worktree 를 연다. 지금 그 판정이 날 수 있는 곳은 userns 가 켜진 Linux 뿐이고, macOS·Windows 에서는 신호를 잴 때까지 이 값을 받지 않는다(`doctor` 가 "set but not honored on this platform" 으로 알림). USER_ONLY 로 둔다: 커밋된 저장소 파일이 격리를 풀 수 있으면 안 된다.
- `sandbox` 의 위험(키 설명과 `doctor` 출력에 그대로): 셸 명령만 OS 샌드박스에 들어가고, agy 파일 도구(`read_file`, `write_file`)는 사용자 권한으로 워크스페이스 밖, 메인 작업 트리, `.git`, HOME 비밀까지 묻지 않고 읽고 쓴다(ACP 에서는 settings `permissions` 도 막지 못함 [실측]; print 정책의 deny 는 듣는다 [실측] 그러나 OS 경계가 아님). OS 샌드박스 아래에서 파일 도구도 막히는지는 미측이다.
- 셸 샌드박스도 없는 곳의 agy worktree 는 값으로 제공하지 않는다: 그때 셸은 사용자 권한 그대로라 격리가 0 이다.
- 키가 `sandbox` 이면 `run` 시작 줄에 `agy worktree without uid isolation (HARNESS_DELEGATE_AGY_WORKTREE=sandbox): file tools are not confined` 를 찍는다.
- macOS·Win11 에서 파일 도구가 막힌다고 실측되면 그 플랫폼은 기본을 바꿀지 사용자에게 다시 묻는다.

### 4.4 표지선 (막지는 못하고 알림)

- agy `--output-format json` 의 `denied_actions` 를 guard(`agy denied: read_file, command`), meta, state 에 남긴다. headless 거절(기본 프리셋의 Ask)은 그 턴을 빈 답으로 끝내므로 `run` 은 "MISSING" 대신 거절 때문에 답이 비었다고 알린다. 명시 deny 규칙은 도구 오류로 돌아오고 턴은 이어진다(`denied_actions` 없음) [실측].
- 실행이 끝나면 그 uid 의 남은 프로세스를 끝내고 수를 guard 에 적는다.
- 메인 HEAD·status 해시 비교는 그대로.

## 5. 에이전트 어댑터

어댑터 경계: `credentials(cfg)`, `prepare_home(task_home)`, `policy(mode, backend, workspace) -> (설정, 알림)`, `argv(...)`, `outcome(record) -> 답·거절`, `report_rel(mode)`·`fallback(mode)`(보고서 파일).

### 5.1 agy (print 모드)

ACP 는 쓰지 않는다(사용자 "acp 없이 하는게 맞겠다"). ACP 에서는 settings `permissions` 도 plan 모드도 파일 도구를 막지 못했고 [실측], print 모드의 `--settings` 권한은 듣는다 [실측]. 근거는 `portable-isolation.md` 의 ACP·print 모드 실측과 "Python 드라이버 실제 실행".

| 항목 | 내용 |
|---|---|
| 호출 | `agy --model <m> --print-timeout <t>s --output-format json --settings '<JSON>' -p <머리말+과제>`, Popen `cwd=<사본>`, env 의 HOME 은 task_home, `TMPDIR` 은 task_home 안 `.tmp`. `--dangerously-skip-permissions` 는 어느 모드·백엔드에서도 쓰지 않는다(기본 프리셋의 headless 거절을 모두 끈다) |
| 기본 프리셋 [실측 1.5.8] | 작업 폴더 밖 비임시 경로의 파일 도구, 밖을 가리키는 링크(대상 경로로 판정), 샌드박스 없는 셸은 Ask 가 되고 headless 라 거절된다. 그 턴은 빈 답으로 끝나고 JSON 에 `denied_actions`. 구멍: 임시 폴더(`/tmp` 전체)는 묻지 않고 열려 있다 |
| 규칙 우선순위 | Deny > Ask > Allow [문서]. 그래서 "넓게 deny + 작업 폴더 allow" 는 성립하지 않고, 필요한 곳만 deny 한다 |
| `--settings` 정책 | deny: `read_file(<d>)`, `write_file(<d>)` 를 `/tmp`, `tempfile.gettempdir()`, `$TMPDIR` 에(쓴 그대로와 실제 경로, 중복 없이). allow: 작업 폴더의 `read_file`·`write_file`(쓴 그대로와 실제 경로). permissions 를 넘기면 프리셋의 "작업 폴더 쓰기 허용" 이 빠져 worktree 안 새 파일 쓰기가 거절됐다 [실측]. empty: deny 에 `command(*)`(셸 샌드박스가 있는 곳에서 기본이 셸을 샌드박스 안에서 열기 때문). uid 백엔드의 worktree: allow 에 `command(*)`(시험·확인 명령), 그 밖의 백엔드는 deny |
| 작업 폴더 위치 | 작업 폴더가 deny 하는 임시 폴더 안이면 deny 를 빼야 하므로 대신 run 을 거절한다(exit 4, `HARNESS_DELEGATE_STATE` 로 옮김). `doctor` 가 FAIL 로 보인다. 그래서 작업 폴더는 `/tmp` 가 아니라 상태 폴더에 둔다(§6) |
| 명시 deny 와 headless Ask | deny 규칙에 걸린 도구는 오류로 돌아오고 턴은 이어진다(`/tmp` 읽기, `denied_actions` 없음) [실측]. 기본 Ask 의 headless 거절은 턴을 빈 답으로 끝낸다 [실측] |
| 답과 거절 | stdout 은 JSON 하나(`response`, `status`, `denied_actions`), stderr 는 따로. 보고서 순서: 머리말이 정한 파일(worktree `REPORT.md`, empty `.delegate/report.md`), 그다음 `response`. `denied_actions` 는 guard·meta·state 에, 답이 거절로 비면 `run` 출력에 그 이유 |
| `read_url` | print 모드 empty 에서 도구 목록에 없다 [모델 진술, 1.5.8]. 다른 웹 도구는 재지 않음 |
| 인증 | `<HARNESS_DELEGATE_AGY_HOME>` 에서 기록(brain, conversations 등)을 뺀 사본. 토큰 파일 하나로 인증된다 [실측 Linux, uid 61004]. macOS Keychain·Windows 자격 저장소 여부 [추정, 미측] |
| uid 백엔드 | 같은 호출을 setpriv 아래로. 정책은 OS 격리 위에 한 겹 더 |

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
- codex 에는 임시 폴더 정책이 없다. 작업 env 의 `TMPDIR` 은 agy 와 같이 task_home 안.

### 5.3 인증 사본의 위험

작업 사본에서 토큰이 갱신되면 원본 refresh token 이 무효가 될 수 있다 [추정]. 드라이버는 끝날 때 사본 토큰이 바뀌었는지 비교해 `state.json`·guard 에 `token refreshed in task` 를 적는다. 되쓰기 여부는 아래 측정 뒤 정한다(Q3).
- 관문: refresh token 이 한 번 쓰면 바뀌는지(회전, 옛 토큰 무효) agy·codex 각각 재는 것을 M3 를 동료에게 내놓기 전의 조건으로 둔다. 회전한다면 동료의 원본 로그인이 위임 한 번에 끊길 수 있다.
- 회전이 일회용이면 후보: 비교 후 교체(compare-and-swap). 복사 때 원본의 해시·mtime 을 기록해 두고, 끝날 때 사본이 바뀌었고 원본은 그대로면 사본을 원본 자리에 원자적으로 쓴다(임시 파일 + `os.replace`). 원본도 바뀌었으면(사용자가 그사이 로그인) 쓰지 않고 알림만. 회전하지 않으면 되쓰지 않고 알림만 남긴다.

## 6. 작업 사본, 수집, 정리, 상태

| 항목 | 설계 |
|---|---|
| worktree 모드 | 지금과 같이 `git worktree add --detach <사본> <commit>`. uid 백엔드면 사본·admin dir·task_home 을 그 실행의 uid 로 chown(fd 기반 `os.fwalk`, 링크는 따라가지 않음). 저장소 층의 setup 줄(`HARNESS_DELEGATE_SETUP`)은 작업 uid 로, 작업의 빈 환경 + mise(자기 폴더를 PATH 에, `MISE_DATA_DIR` = `HARNESS_TOOL_INSTALLS` 의 부모)로 돈다. 공유 clone 도 검토했으나 agy 파일 도구가 풀려 있으면 어느 쪽이든 메인에 쓸 수 있고, `git worktree list` 로 찾는 장점을 잃어 택하지 않음 |
| empty 모드 | 빈 폴더(지금과 같음). `--files` 를 주면 `--ref` 커밋의 **추적 파일만** `git ls-tree`·`git cat-file --batch` 로 복사(추적 안 되는 `.env` 는 처음부터 안 들어감). 비밀 이름 거름: 기본 `.env*`, `*.pem`, `*.key`, `*.p12`, `*.pfx`, `id_rsa*`, `id_ed25519*`, `.npmrc`, `.pypirc`, `.netrc`, `.git-credentials`, `*credentials*.json`, `.claude/harness.local.env`, `.claude/settings.local.json` + `HARNESS_DELEGATE_SECRET_GLOBS` |
| 실행 기록 | `<작업 폴더>/.runs/<name>/`(root 소유, 폴더 0700·파일 0600): state.json, run.lock, prompt.md, meta.txt, stdout.txt, guard.txt, exit, 보고서 사본 report.md. 작업 uid 가 쓰는 곳은 `<name>/.delegate/`(report.md, codex `-o`)와 `<name>/REPORT.md` 뿐이고, root 는 chown 뒤 작업 쪽 폴더(`<name>/`, `.homes/<name>/`)에 쓰지 않는다. 거기서 읽을 때는 root 소유 작업 폴더에서 연 fd 로 한 단계씩 O_NOFOLLOW(링크·FIFO 거절, 크기 상한). 끝난 뒤 보고서를 기록으로 복사하고 `run` 은 그 사본 경로를 알린다 |
| 수집 | `collect` 가 `<상태>/runs/<key>/<YYYYMMDD-HHMM>-<name>/`(0700, 파일 0600)에 기록의 prompt, report, guard, meta, stdout, state, exit, worktree 면 `diff.patch`(새 파일 포함, 참고용. git 은 작업 uid 로, 새 객체는 작업 HOME 의 객체 폴더에, 메인 `.git/objects` 는 alternate 로 읽기만), agy 의 `brain/*/scratch` 와 transcript(fd 로 걸어 링크 제외, "이후" 기준은 기록의 시작 시각). empty 는 diff 없음(변경은 버림). 쓴 파일마다 sha256 을 남기고 다 쓴 뒤 다시 읽어 맞춘다 |
| 자동 정리 | `run` 은 기록을 마친 뒤, 잠금을 쥔 채로 collect(보고서, diff.patch, stdout/stderr, guard, meta, state, agy transcript·scratch)를 하고 사본을 확인한 다음 작업 폴더(worktree, admin dir, HOME, 기록)를 지운다. 확인이 하나라도 어긋나면(git 실패, 복사 오류, 해시 불일치) 아무것도 지우지 않고 `kept: <사본> - automatic collect failed …` 를 알린다. 성공하면 `run` 은 runs/ 안 보고서 경로를 알린다. `--keep` 은 끈다(그때는 지금처럼 `collect`·`remove`). 사용자: "남는 폴더는 그 때 그 때 처리될 수 있게…다만 보고서나 필요한건 전부 받은 다음 삭제되도록" |
| 정리 | `remove`(실행 중·collect 전 거절, `--discard`): 사본을 `shutil.rmtree`(작업 쪽 트리 안에서 git 을 돌리지 않음), 기록의 admin 경로가 `<root>/.git/worktrees/` 아래면 지운 뒤 `git worktree prune`, HOME 과 기록 폴더 삭제. collect·remove 전과 실행이 끝난 직후에 그 uid 의 남은 프로세스를 `/proc` 로 찾아 끝낸다(그 uid 의 실행 잠금이 비어 있을 때만). `gc`(미리보기 기본): 새 자리의 실행 중이 아닌 작업 폴더는 모으지 않은 것이면 먼저 모으고(실패하면 남김) 지운다, 주인 없는 HOME 도. `<상태>/runs/` 의 결과는 `HARNESS_DELEGATE_RUNS_DAYS`(기본 14일, `--days` 가 이김)보다 오래되면 지운다. 저장소 옆 옛 자리(`<dirname(ROOT)>/<key>-<agent>/`)는 목록만 보이고 지우지 않는다(지우는 것은 사용자 몫, `remove` 나 손으로). "프로세스가 사본 안에서 도는지" 는 Linux `/proc/*/cwd` 만, 다른 OS 는 실행 잠금으로 판단 |
| 실행 잠금 | 기록의 `run.lock` 을 실행 내내 잡는다(POSIX `fcntl.flock`, Windows `msvcrt.locking`). 잡을 수 없으면 running. pid 재사용과 남은 잠금 파일 문제가 없다(`O_EXCL` 대신) |
| 동시 실행 | 상태 폴더 `slots/<agent>-<n>.lock` N 개 중 빈 것을 비차단으로 잡음(N = `HARNESS_DELEGATE_MAX_CONCURRENT`, 저장소 합계). 그와 별개로 `uids/<uid>.lock` 으로 uid 하나에 작업 하나 |
| uid | 대역 하나(`HARNESS_DELEGATE_UIDS`, 기본 `61100-61115`, USER_ONLY, 옛 표의 61000-61005 를 피함)에서 실행마다 비어 있는 첫 uid 를 쓴다(Q31 a). 비어 있음: `/etc/passwd`·`/etc/group` 에 그 번호가 없음(작업은 그 번호를 gid 로도 쓴다), 기기 전체 잠금 `/run/qwreey-delegate/uids/<uid>.lock` 을 잡을 수 있음(`/run` 을 못 쓰면 상태 폴더 `uids/`), 모으지 않은 작업 폴더의 기록이 그 uid 가 아님(메인이 읽기 전에 새 작업이 고치지 못하게, 잠근 뒤 다시 확인). 없으면 exit 5, 대역이 실제 계정뿐이면 exit 4, 값이 잘못되면 exit 2. 대역 크기가 동시 실행 수. 지키는 것은 메인 작업 트리, `.git/objects`, 인증 정보, push 이고, 위임 작업 폴더끼리의 격리는 사용자 위협 모델에서 필요 없다(같은 uid 를 다른 저장소의 위임이 나중에 받는다). uid 가 실행마다 달라 남은 것을 다시 쓰지 않는다: 같은 이름의 작업 폴더·기록은 거절, 같은 이름의 HOME 은 root 가 지우고 새로 만든다. collect·remove·gc 는 기록의 uid 잠금을 쥐고 쓴다(기록이 없는 delegate.sh 작업은 작업 폴더 주인) |
| 프로세스 트리 | POSIX `start_new_session` + `killpg`, Windows Job Object(ctypes, 닫히면 종료) [추정, 미측] |
| 상태 폴더 | `HARNESS_DELEGATE_STATE`, 없으면 Linux `$XDG_STATE_HOME/qwreey-delegate`(기본 `~/.local/state`), macOS `~/Library/Application Support/qwreey-delegate`, Windows `%LOCALAPPDATA%\qwreey-delegate`(동기화되지 않는 로컬 폴더). 슬롯·uid·시작 잠금, 미끼 파일, `work/`, `runs/` 를 둔다 |
| 작업 폴더 위치 | 모든 백엔드: `<상태>/work/<key>-<agent>/{<name>/, .homes/, .hooks/, .runs/}`, 결과 `<상태>/runs/<key>/`. 모두 root 소유. 작업 uid 가 지나가야 하는 폴더(상태 폴더, `work/`, `<key>-<agent>/`, `.homes/`, `.hooks/`)는 0711(지나가되 목록은 못 봄), 기록·`runs/`·잠금 폴더는 0700, 파일 0600. 상태 폴더의 부모들은 작업 uid 가 지나갈 수 있어야 한다(`doctor` 확인). `/tmp` 가 아닌 까닭: agy 정책이 `/tmp` 를 deny 하므로 그 아래 작업 폴더는 deny 를 빼야 한다(§5.1). 저장소 키는 `<ROOT 폴더 이름>-<ROOT 경로 sha256 앞 8자>` 라 폴더 이름이 같은 두 저장소가 겹치지 않는다. 한 번 돈 저장소는 `<상태>/repos/<key>`(root 소유 0700/0600)에 ROOT 가 남아 `--repo <key 또는 폴더 이름>` 과 `--all` 이 찾는다(`--all` 에는 지금 저장소도 든다). 아는 키가 아닌 `work/`·`runs/` 폴더는 목록만 보이고 그 결과는 보존 기간으로 지운다. 저장소 옆 옛 자리(`<dirname(ROOT)>/<폴더 이름>-<agent>/`)는 `list`·`collect`·`remove` 가 계속 찾는다 |
| state.json | 기록 폴더 안, 원자적 쓰기(임시 파일 + `os.replace`). 필드: agent, mode, isolation 백엔드, repo, root, uid, commit, ref, model, effort, pid, started/started_ts/finished, rc, admin, collected, token_refreshed. 기록이 있는 실행은 작업 쪽 `.delegate/` 의 pid·exit·collected 를 보지 않는다(작업이 무엇이든 쓸 수 있다). delegate.sh 의 옛 작업은 그 파일들을 fd 로 읽기만 하고 쓰지 않는다. `delegate.sh` 는 이제 `delegate.py` 를 부르는 셈이다. 플러그인 캐시에 남은 옛 본문(갱신 전 설치본)은 새 자리를 모르므로 이 드라이버의 실행을 세지 않는다. 드라이버는 옛 본문의 시작 잠금과 살아 있는 pid 를 세므로 한쪽 방향은 막힌다 |

## 7. 설정

harness.env 층(`load_layers(ROOT)`) 하나로 읽는다. 옛 `DELEGATE_*` 이름은 배포 전 스크립트의 환경 변수였고 어느 harness.env 에도 없으므로, 호환 없이 새 이름으로 바꾼다(아래 "옛 이름" 열은 대응만 적는다).

| 키 | 기본 | USER_ONLY | 옛 이름 |
|---|---|---|---|
| `HARNESS_DELEGATE_UIDS` | `61100-61115` | 예(작업이 어느 uid 로 도는지) | `DELEGATE_REGISTRY`(저장소별 uid 표, Q31 a 로 대역 하나로 바뀜) |
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
| `HARNESS_DELEGATE_RUNS_DAYS` | 14(결과는 끝나자마자 읽고, 남길 보고서는 저장소 `.claude/audit/` 로 옮기므로 놓친 읽기와 주말을 덮는 두 주) | 예(모든 저장소의 결과를 지움) | 새 키 |
| `HARNESS_DELEGATE_AGY_MODEL`, `HARNESS_DELEGATE_CODEX_MODEL` | `gemini-3.8-flash-high`, `gpt-6-luna` | 아니오(저장소가 정해도 무해) | 스크립트 고정값 |
| `HARNESS_DELEGATE_SECRET_GLOBS` | 빈 값(기본 목록에 더함) | 아니오(더하기만 됨, 더 엄격해질 뿐) | - |
| `HARNESS_DELEGATE_SETUP` | 빈 값 | 아니오(worktree 모드의 에이전트가 같은 uid 로 거기서 셸을 이미 쓰므로 더 할 수 있는 일이 없음). `$NAME` 을 드라이버 환경으로 풀지 않고 적힌 그대로 읽는다(드라이버 환경의 토큰이 저장소가 쓴 명령에 들어가지 않게) | uid 표의 setup 열 |

- 위임 키는 `delegate.py` 의 `ENV_DEFAULTS`·`ENV_USER_ONLY` 에 넣고 `load_layers(defaults=, user_only=)` 로 넘긴다. `HARNESS_DELEGATE_UIDS`(/q:doctor 의 DRIFT-UID 도 읽음), `HARNESS_TOOL_INSTALLS`, `HARNESS_HEAVY_WRAP` 은 다른 플러그인도 읽어 로더(`home/.claude/lib/harness_env.py`)가 정한다. 위 표는 `tools/tests/test-delegate-config.py` 의 `USER_ONLY_YES`·`USER_ONLY_NO` 와 맞춘다.
- 사람이 고르는 다섯 키(uid 대역, 두 모델, 두 실행 파일)는 `plugin.json` 의 `userConfig` 에도 두어 `/config` 에서 바꾼다(설정 층의 플러그인 옵션, 사용자 harness.env 위, 저장소 층 아래). 격리 게이트, 상태 폴더, 한도는 harness.env 에만 둔다.
- 설치된 `~/.claude/lib/harness_env.py` 는 옛 판일 수 있어 새 USER_ONLY 키를 모를 수 있다. 그래서 드라이버는 늘 자기 옆 사본을 쓴다(`tools/tests/test-harness-env-owners.py` 가 옛 설치본으로 확인).
- `DELEGATE_AGY_FULL_HOME` 은 없앤다(토큰 하나로 인증됨 [실측]).
- uid 표(`registry.tsv`)와 `register` 는 없앴다(Q31 a). 등록 없이 모든 git 저장소에서 돈다. `register` 는 더는 필요 없다는 말만 찍고 exit 0(옛 SKILL 본문을 읽은 세션을 위해). setup 은 저장소 층 `HARNESS_DELEGATE_SETUP` 으로 옮겼다: 위 표의 이유대로 저장소가 정해도 격리가 줄지 않는다. uid 가 없는 환경(M3)도 같은 키와 setup 을 쓰되 사용자 권한으로 돈다.

## 8. Python 제약

- 표준 라이브러리만, 진입은 `python3 -I <skill>/scripts/delegate.py`. 하한 3.11(저장소 README 전제). `-I` 는 3.11 부터 `-P` 를 포함해 스크립트 폴더가 `sys.path` 에 없으므로 드라이버가 자기 폴더를 직접 넣는다(지금 `harness_value()` 와 같은 방식).
- 파일: `delegate.py`(CLI, run, doctor), `delegate_results.py`(collect, remove, 자동 정리, list, gc), `delegate_agents.py`(agy·codex 어댑터, agy 정책), `delegate_isolation.py`(uid 백엔드, 환경, 프로세스), `delegate_workspace.py`(저장소 키, uid 대역과 고르기, 자리, 기록, 잠금, fd 기준 읽기), 그리고 `harness_env.py` 사본(`@copy-of`, 지금 그대로). 모든 import 는 시작에(실행 중 플러그인 파일이 바뀌어도 돌던 작업이 깨지지 않게).
- 정책 값(비밀 이름 목록, 시간 제한, 모델, 결과 보존 일수)은 `DEFAULT_*` 상수 + 설정 키, 불변 값(종료 코드, 폴더 모드)은 상수.
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
| 가짜 agy(print 모드 JSON, `denied_actions`), 가짜 codex | run→자동 수집·정리, `--keep`→collect→remove→gc, 정책 JSON, 거절 표시, 동시 실행 거절 | - |
| uid 백엔드 | 실제 `doctor --all`, 실제 run 백엔드당 1회(사용자 동의, agy 1턴 약 2.5만 토큰 [실측]) | - |
| 비root, userns 꺼짐 | 드라이버 자체를 setpriv 로 무권한 uid 아래 돌려 흉내: codex 는 empty 만, agy 는 exit 4, `UNISOLATED=allow` 면 agy empty 와 셸 거절 | - |
| codex 권한 프로필 자가 시험 | 가짜 codex 로 코드 경로와 양성 대조(대조 실패 → 판정 불가)만(bwrap 불가) | macOS·Win11: 실제 `codex sandbox` 통과/실패, `--ignore-user-config` 와 CODEX_HOME config, 셸 도구를 끄는 설정 |
| agy 셸 샌드박스 판정 | 음성만 잴 수 있음: `session/new` 뒤 `Terminal sandbox unavailable` 줄이 찍히고 `unshare -U` 가 실패해 "없음" 이 나와야 함. initialize 만으로는 줄이 없어 거짓 양성이 됨 [실측] | userns 켜진 Linux: 양성 로그 꼴. macOS·Win11: 쓸 만한 양성 신호가 있는지 |
| 인증 위치, 토큰 회전(M3 관문) | agy·codex 각각: 사본에서 갱신이 일어난 뒤 원본 토큰이 아직 통하는지(사용자 동의, 실제 호출) | macOS: 토큰 파일인지 Keychain 인지 |
| agy print 정책이 다른 판·OS 에서도 같은지 | 1.5.8 실측 | macOS·Win11: 같은 정책으로 밖 읽기·`/tmp`·셸 1턴씩 |
| Windows 고유 | - | 잠금(msvcrt), Job Object 종료, git 훅, 긴 경로, py 런처 |

### 9.3 단계

| 단계 | 내용 | 끝 조건 |
|---|---|---|
| M0 | 이 설계 검토 | 끝(§10) |
| M1 | `delegate.py` 동등 이식(uid 백엔드, agy print, codex 지금 꼴). `delegate.sh` 손대지 않음 | 가짜 에이전트 시험 통과, 같은 runs/ 꼴 |
| M2 | agy print 모드 정책(ACP 대신): skip 플래그 없음, `--settings` deny·allow, JSON 답과 `denied_actions`, 작업 폴더를 상태 폴더로, run 끝 자동 수집·정리 | uid 아래 실제 agy worktree·empty, codex empty(끝남, `portable-isolation.md`) |
| M3 | 격리 판정·모드 선택, 비root empty, codex 프로필·자가 시험, 남은 harness.env 키(정본+sync) | 비root 흉내 시험, `doctor --json`. 동료 배포 전 관문: 토큰 회전 실측(§5.3) |
| M4 | `delegate.sh` 를 셈으로, SKILL·README·how-it-works·plugin.json 요구 사항 갱신(agy empty 는 "제한된 사본, 강제 아님", 상태 폴더 작업 위치는 `conventions.md` §1 표에도), 버전 올림(qwreey-delegate 0.2.0) | 끝(문서·셈·proc-guard 0.1.6). 남은 끝 조건: 사용자가 두 플러그인을 갱신하고 세션을 다시 연 뒤 SKILL 이 `delegate.py` 사용(`HUMAN_TODO.md`). 격리 없을 때 agy 꺼짐과 `UNISOLATED` 키, 비uid 작업 위치의 문서화는 M3 구현과 함께 |
| M5 | macOS·Win11 실측, §3 표의 [추정] 갱신, agy 기본 재검토 질문 | 실측 기록 추가 |
| M6 | proc-guard 패턴 갱신 뒤 SKILL 이 `delegate.py` 직접 호출. 셈은 남김(값쌈) | M4 와 함께 끝(proc-guard 가 `delegate.py`·`delegate.sh` 둘 다 통과) |

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
| Q8 | agy 는 ACP 없이 print 모드로(사용자 "acp 없이 하는게 맞겠다") |
| Q9 | 작업 폴더는 저장소 옆이 아니라 상태 폴더에, `run` 이 끝에 결과를 모은 뒤 지운다(사용자 "남는 폴더는 그 때 그 때 처리될 수 있게…다만 보고서나 필요한건 전부 받은 다음 삭제되도록"). 사용자가 꺼낸 `/tmp` 대신 상태 폴더인 까닭은 §6 작업 폴더 위치 |

### 확인 대기 제안

| # | 제안 | 근거 |
|---|---|---|
| P1 | uid 격리가 없을 때 agy `empty` 를, 잰 agy 판(허용 목록 `DEFAULT_AGY_PRINT_VERSIONS`, 지금 1.5.8)에서는 print 정책 아래 기본으로 연다. 목록 밖 판은 지금처럼 꺼짐이고 `HARNESS_DELEGATE_AGY_UNISOLATED=allow` 로만 연다. Q7 을 바꾸는 것이라 사용자 확인 전에는 구현하지 않는다 | 1.5.8 print 모드에서 밖 비임시 읽기·링크·셸이 headless 거절, `/tmp` 는 명시 deny 로 막힘 [실측]. 남는 위험: OS 경계가 아니라 agy 규칙이고 판마다 다를 수 있다, 재지 않은 경로 표기 |

### 끝난 측정

| # | 측정 | 결과 |
|---|---|---|
| M-a | ACP `session/set_mode` `plan` 뒤 사본 밖 `read_file`·`write_file` | 막지 못함 [실측] |
| M-b | print 모드 `--settings` `permissions.deny` | 듣는다 [실측]. 기본 프리셋도 밖 비임시 경로·셸을 headless 거절, `/tmp` 만 열림. 정책은 §5.1 |

## 11. 지금 문서·스크립트와 어긋나는 점

- `empty` 의 뜻: 정책(`portable-isolation.md`)은 "필요한 파일만 비밀 없이 복사한 사본", 스크립트·`preamble-empty.md`·`conventions.md` 는 "빈 폴더, 파일을 읽지 말 것"(Q1).
- 옛 `delegate.sh` 본문(갱신 전 플러그인 캐시)의 agy 는 모든 모드에서 `--dangerously-skip-permissions` 라 셸·파일이 다 열리고(uid 아래) 작업 폴더가 저장소 옆이다. 저장소의 `delegate.sh` 는 M4 에서 드라이버를 부르는 셈이 됐고, 옛 자리는 드라이버 gc 가 목록만 보인다.
- "`agy --sandbox`·codex `-s read-only` 가 cwd 밖을 못 막는다"는 이 호스트(userns 꺼짐) 한정이다. SKILL "Isolation"·how-it-works 는 M4 에서 "이 호스트" 로 좁혔다.
- 경로 고정: `GEMINI_SRC=/code/.gemini`, `CODEX_AUTH=/code/.codex/auth.json`, `SECRETS_PROBE=/code/…`, 설치 기본 `/code/.local/share/mise/installs`(harness_env 기본은 `~/.local/share/mise/installs`).
- `portable-isolation.md` "드라이버 기본 정책" 의 agy 판정("ACP 서버 시작 로그에 `Terminal sandbox unavailable` 줄이 없다")은 시작 직후에 보면 이 호스트에서도 거짓 양성이다. 줄은 `session/new` 뒤에 찍히고 안 찍힌 로그도 있다. 이 설계 §4.1 이 고친 판정이다. print 모드는 시작 때 그 줄을 찍으므로 [실측], ACP 를 쓰지 않는 드라이버의 판정을 print 모드 시작 로그로 옮길지는 M3 에서 정한다.
- `portable-isolation.md` 의 "권장 설계" agy 항목(deny 규칙, worktree 안 편집만 허가)은 같은 문서의 뒤 실측으로 성립하지 않는다(문서 스스로 적음). 드라이버 항목의 `O_EXCL` 잠금은 이 설계에서 OS 파일 잠금으로 바꿈.
