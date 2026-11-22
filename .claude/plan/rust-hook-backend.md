---
format: 1
title: 훅 백엔드를 Rust 로 (계획, Q38 b)
description: python 훅(매번 34 ms CPU)을 플러그인별 Rust 바이너리(매번 0.5 ms)로 옮기는 계획; 0단계(대조 실행기, 빈 바이너리로 배포 경로 확인)와 proc-guard 시범을 나란히, 런처 없이 바로 실행, OS별 배포 ref 가 우선 후보(Q39 a)
status: active; Q39 a 로 순서 확정, 배포 세부는 사용자 답 대기
keywords: [rust, hook backend, 훅 백엔드, CPU, daemon, single-flight, parity, 배포]
---

# 훅 백엔드를 Rust 로

Q38 b(사용자): 계획만 먼저 쓰고 debate 로 확정한다. debate 종합은 `.claude/audit/67-rust-hook-backend-debate/synthesis.md`, 사용자 답 Q39: "a) 합침: 시범과 0단계를 나란히, 바로 실행, OS별 ref 를 우선 후보로".

## 왜
- 비용
  - 훅마다 python 을 새로 띄워 CPU 약 34 ms, 프로세스 14~23 MB 가 든다.
  - 도구 한 번에 Bash 0.44 초, Edit 0.33 초, Read 0.15 초, 사용자 말 0.23 초.
  - 이 호스트는 quad, stl-luau, devplorer, tbox 세션이 함께 돌아 CPU 가 늘 빠듯하다.
- Rust 를 매번 띄우면 0.5~0.6 ms(`.claude/audit/66-hook-server-language/one-shot.md`).
- 유지보수(사용자): "네가 쓴 코드 끔찍히 분석하기 힘듦 ... 타입도 없는 상태라 난 보고서 cfg 가 뭔지 몰라 ... 그걸 다 끌고 와서 파이썬이라도 ... 아에 다시 작성하는거랑 뭐가 다른지 모르겠음".
- 사용자는 Rust 를 잘 쓴다. "툴링이 잡아주는 실수가 줄이는 시행착오도 큰데 ... 컴파일 하는건 종종이고 사용하는건 절대적으로 많은 시간".

## 지킬 것 (이미 정한 원칙)
- 벤더 중립(사용자: "qwreey-harness 는 다른 하네스를 고려할 수 있다는 입장"). 검사는 하네스를 모르는 백엔드에 두고, 하네스마다 어댑터(설정 파일)만 다르다. mod 는 UI(desk)에만 쓴다.
- 플러그인 독립(Q28 a, Q29 a): 플러그인 하나만 설치해도 돈다. 서로 기대지 않는다.
- 규약(qwreey-conventions)과 coderag 는 잇지 않는다(`.claude/base/harness-principles.md`). 같은 Rust 라 짜는 방식만 참고한다.
- 빌드된 바이너리는 GitHub release 로 내고 사용자가 GPG 로 서명한다(같은 원칙 파일).
- 훅은 막지 않는다. 막는 훅(workspace-gate, heavy-proc-guard, auditor-readonly-guard, self-match-guard 의 루프)만 예외이고, 그 동작은 그대로 지킨다.
- 결과가 지금과 같아야 한다. 모델에게 가는 글(HOOK-MESSAGES.md 형식, nonce)과 사용자 줄(systemMessage)이 바이트로 같다.

## 모양
- **워크스페이스:** 이 저장소에 Cargo 워크스페이스 하나.
  - 공통 crate: 훅 입출력 JSON, nonce(`lib/harness_nonce.py` 대응), 설정 층(`home/.claude/lib/harness_env.py`, 플러그인 옵션), compact 회차, 파일 잠금, known_repos.
  - 플러그인마다 crate 하나가 바이너리 하나를 낸다.
  - 공통 코드는 컴파일 때 공유한다. 설치된 바이너리끼리는 서로 기대지 않는다. `lib/` 바이트 사본과 `tools/sync-copies.py` 는 옮긴 만큼 필요 없어진다.
- **실행:** 훅은 명령 훅으로 바이너리를 바로 실행한다(`command` + `args`, 셸 없이). 하위 명령은 `<바이너리> hook <이벤트>`.
  - python 으로 돌아가는 런처는 두지 않는다(셸을 다시 띄우고, PowerShell 에서 깨진 전례). main 은 이 기기 전용이고, 동료는 배포 ref 에서 받는다. 0단계가 끝나기 전에는 동료에게 Rust 훅을 내지 않는다.
  - 바이너리 자리는 플러그인 안 `native/`(이름은 제안). 맨 위 `bin/` 은 Bash PATH 에 오르고 claude.ai·Cowork 가 설치를 거부해서 쓰지 않는다.
  - 같은 바이너리가 사람과 모델이 부르는 명령도 맡는다. 예: `conventions-scan` 은 지금 `conventions-check.py` 의 함수를 불러 쓰므로, 검사를 옮기면 scan 도 같이 옮긴다.
- **데몬(나중, 선택):** 바이너리가 먼저 사용자별 로컬 소켓의 데몬에 묻고, 없으면 혼자 계산한다.
  - 데몬이 없어도 결과와 막는 훅은 늘 맞다. 데몬은 빨라지게만 한다.
  - 데몬은 캐시 목록(경로, 크기, 수정 시각, 검사기 버전, 설정 -> 결과)을 한 벌 쥐고, 같은 키의 계산은 한 번만 한다(single-flight). 계산은 작업 스레드 여럿이 한다.
  - 서브에이전트 둘이 같은 파일의 같은 버전을 동시에 검사하면 계산은 한 번이다. 알림은 요청마다 그 에이전트가 추가한 줄로 걸러 각자 받는다.
  - 운영: 잠금 파일로 하나만 뜨고, 쉬면 꺼지고, 바이너리와 버전이 다르면 다시 띄운다.
- **하네스 어댑터:** Claude Code 는 플러그인 `hooks/hooks.json`. codex, agy 는 그 하네스의 훅 설정(나중, 있으면).

## 0단계 (시범과 나란히)
1. **대조 실행기:** 같은 입력을 python 훅과 바이너리에 넣어 stdout, 종료 코드를 바이트로 비교한다. `hook_sandbox.py` 와 `tools/tests/test-hook-commands.py` 의 `FORM` 이 실행 형식(`command` + `args`)도 받게 고친다. 끝(9dbb5e5): `tools/tests/hook-parity.py`, `--identity all` 122 입력 모두 같음.
2. Cargo 워크스페이스와 공통 crate(훅 입출력, nonce, 설정 층). 끝(761224d, bbfc686): `crates/harness-hook`, 검토에서 python 에도 있던 결함(claim 폴더 링크를 따라 지움 등)을 양쪽에서 고침. 이름은 Q40, rustix 의존성은 Q41.
3. **배포 경로:** 빈 바이너리 하나로 CI -> release(사용자 GPG 서명) -> OS별 배포 ref -> 설치본까지 실기기에서 통과한다. 확인할 것: `/plugin marketplace add <repo>#<ref>` 설치, Windows 의 `.exe` 실행 형식, macOS 격리 속성. 시험 훅은 workspace-gate 처럼 모든 OS 에서 도는 것으로.

## 옮기는 순서 (매 도구마다 뜨는 것, CPU 큰 것부터)
훅이 쓰는 python(시험 제외, `lib/` 사본 포함) 약 2만 4천 줄. 위임·토론·라이선스의 스킬 스크립트는 훅이 아니라 대상에서 뺀다.

1. **qwreey-proc-guard** (1.6k 줄): Bash 앞에 3개, 뒤에 1개. 작고 막는 훅이 있어 첫 시범으로 알맞다(어댑터, 막기, 시험 대조를 다 거친다). 이 기기에서 0단계와 나란히 한다. 끝(aaf316a, e96f75d): python 과 대조 모두 같음, Bash 한 번 훅 CPU 약 94 ms -> 2.5 ms, 0.4.0 에서 hooks.json 을 바이너리로(Q43 a, 실사용 주간 전에). 정규식은 직접 짠 python re 호환 엔진, conventions 때 fancy-regex 와 다시 잰다(Q42 c). Windows 는 거치지 않으므로(heavy-proc-guard 는 Linux 에서만 막음) Windows 확인은 0단계 몫이다.
   - 그 다음 막는 훅은 **qwreey-workspace** 의 workspace-gate 를 앞당긴다. 모든 OS 에서 돈다.
2. **qwreey-sessions** `hook.py`, `records_read.py` (3.6k 줄 중 훅 부분): 도구 앞뒤마다 45~55 ms. 요약 작업자(`cli.py flush`)는 백그라운드라 나중. 끝(962ee77, 1af251b): PostToolUse, PreToolUse, UserPromptSubmit, records-read 를 0.7.0 에서 바이너리로(Q46 a). 도구 한 번 약 80 ms -> 1~1.5 ms. SessionStart, compact, SessionEnd, 작업자는 python. 공통 crate 에 python json 호환 파서, jiff(Q44 a), close_fds(Q45 a).
3. **qwreey-advisor** (2.7k 줄): Bash 앞, PostToolBatch, Stop, 사용자 말. 이식 끝(73c6209, 검토 반영 뒤): readonly-for-reviewers, second-opinion-nudge 모든 이벤트, expand-inherit-prompt, track-reviewer, ambient UserPromptSubmit. qwreey-reply-language 도 같이. 0.7.0(advisor), 0.2.0(reply-language) 에서 hooks.json 을 바이너리로(Q51 a). ambient 의 SessionStart, PreCompact 는 python.
4. **qwreey-conventions** (6.6k 줄, 1단계 끝 8bfb163·d33c591: conventions-check, reuse-check, structure-reminder, memory-placement, 3.3k 줄 파일 conventions-check 83 -> 10.6 ms; 0.16.0 에서 이 넷의 hooks.json 을 바이너리로(Q51 a). 2단계(86dcbb6: rules-inject, bash-bypass-reminder, bash-writes, Bash 한 번 약 60 ms -> 약 2~13 ms)도 0.17.0 에서 바이너리로(Q54 a), compact_epoch 만 python. 고정 정규식은 regex crate(Q48 a), perf-dfa 는 모든 crate(Q50 a)): 가장 크다. bash-bypass-reminder, bash_writes, structure-reminder, rules_inject, conventions-check, reuse-check, memory-placement, 그리고 conventions-scan. rules_inject 는 coderag 와 바이트 대조 시험이 있으니 그 시험을 그대로 쓴다.
5. **qwreey-workspace** (2.0k 줄): 끝(d3c429c, 99d7d9e): workspace-gate(세 이벤트), sibling-notice, 0.4.0 에서 hooks.json 을 바이너리로(Q54 a). gate 17 -> 0.9 ms, sibling-notice 27 -> 0.6 ms. python 쪽 막기를 놓치던 셋(Windows 홈 경로 escape 등)도 고침. **qwreey-operator** (1.0k 줄), **q** (5.4k 줄 중 훅): 끝(99e61a8, 1a1ae3f): operator 의 delegate-nudge, subagent-bg-tasks, q 의 subagent-slots, stale-work, mise-hint, ambient UserPromptSubmit(ambient 보충은 harness-hook 으로 옮겨 advisor 와 함께 씀). 훅 하나 12~27 ms -> 1~1.6 ms. 0.5.0(operator), 0.13.0(q) 에서 hooks.json 을 바이너리로(Q55 a). **qwreey-reply-language** (0.9k 줄): 3 에서 끝.
6. 세션 시작에만 도는 것(ambient, drift, stale_worktrees)은 마지막. 자주 돌지 않는다.

## 플러그인 하나를 옮기는 단계
1. crate 를 만들고 훅마다 하위 명령을 짠다.
2. **결과 대조:** 지금의 python 시험(`plugins/<p>/tests/`, `tools/tests/test-hook-replay.py`)을 바이너리에도 돌려 출력이 바이트로 같은지 본다. 시험 실행기가 훅 명령을 바꿔 끼울 수 있게 고친다.
3. `cargo test`, `cargo clippy -D warnings`, `cargo fmt --check` 를 통과한다.
4. `hooks.json` 을 바이너리로 바꾼다. python 파일은 열린 세션이 모두 다시 읽을 때까지 그 자리에 둔다(디렉터리 마켓이라 살아 있는 세션이 옛 경로를 부른다). 지우는 것은 사용자 몫(HUMAN_TODO).
5. `python3 -I tools/usage-report.py --time-hooks` 로 전후를 잰다.

## 열린 문제
정해진 것(Q39 a): 순서, 런처 없음, 바이너리 단위(플러그인마다 하나), 워크스페이스 자리(이 저장소), `native/`. 남은 것은 사용자 답을 기다린다(audit 67 "For the user").
1. **배포 ref 확정:** OS별 ref 가 우선 후보. 0단계에서 `#<ref>` 설치를 확인한 뒤 정한다. 이 저장소의 브랜치 대 별도 저장소(Q19 공개 시점과 함께).
   - 바이너리 자리(audit 68, Q57 c: 열어 둔다): 동료가 플러그인을 받는 길에 달렸다. claude.ai 조직 배포는 기본 브랜치만 읽고 `archive` 소스와 맨 위 `bin/` 을 받지 않으므로, 그 길이면 플러그인에 싣되(바이너리를 기본 브랜치에 커밋하거나 다른 길을 0단계에서 찾는다) PATH 설치는 밀 수 없다. 마켓 CLI 면 (1b) 플러그인 `native/` + OS별 release zip 과 (2) PATH 에 한 벌 + hooks.json 이 이름으로 부르기가 둘 다 된다. rtk·qx 꼴(setup 이 settings.json 에 훅을 적기)은 플러그인 옵션이 오지 않아 쓰지 않는다. 0단계에서 잴 것: Windows 실행 형식이 확장자 없는 이름에서 `.exe` 를 찾나, 모든 OS 에서 `<bin>.exe` 이름이 되나, GUI·Cowork 로 띄운 Claude 의 PATH, 바이너리가 없을 때 사용자에게 보이는 것. audit 68 이 '어느 쪽이든' 고칠 것으로 적은 `CLAUDE_PLUGIN_ROOT` 우선은 실제로는 (2) PATH 안을 고를 때만 필요하다. 플러그인에 실으면 바이너리 자리가 python `__file__` 과 같은 뜻이라 지금 바꾸면 대조 기준에서 멀어진다. 그래서 (2)를 고를 때 한다.
2. **동료 환경:** claude.ai 조직 배포·Cowork 를 쓰나, OS 와 아키텍처(macOS, ARM), 회사 Windows 가 서명 없는 exe 를 막나.
3. **바이너리가 없을 때 막는 훅:** 진행(오늘과 같음) 대 `onFailure: "block"`.
4. **CI 러너 비용:** macOS, Windows.
5. **시범을 켜는 때:** 실사용 주간(11-23~)에 이 기기에서 켜 둘지.
6. **이름:** 바이너리, crate, `native/`, 환경 변수 이름은 사용자가 정한다(제안만).
7. **데몬 시점:** conventions 차례에서 재고 정한다.
8. **python 을 남길 곳:** 훅이 아닌 스크립트(세션 요약 작업자, doctor, 위임 드라이버)를 언제 옮기나, 그대로 두나.
9. **옮기는 동안:** 플러그인 하나 안에서 python 과 Rust 가 섞이는 기간의 버전 표시와 설정 키.

## 이식 뒤에 할 것
- 시험 가독성(Q47 a): 시험 함수마다 한 줄 doc 주석, 준비·실행·확인을 빈 줄과 이름표로, 뻔하지 않은 기대값은 이유를 적는다. readable-code 규약에 넣을 문구는 debate 로 정하고, 이미 있는 crate 시험(harness-hook, proc-guard, sessions)은 이식이 끝난 뒤 동작은 그대로 두고 시험만 다듬는다. 새로 쓰는 시험은 지금부터 이 꼴.

- 남은 작은 일(conventions 검토 뒤): git 실행기 둘(qwreey-advisor, qwreey-conventions)을 harness-hook 하나로(close_fds 포함); FIFO 를 열면 멈추는 설정 읽기가 더 있다(`.claude/conventions.json`, reuse·conventions-check 설정, python 과 양쪽, `open_regular` 로); coderag 의 팩 rule 읽기도 FIFO 에서 멈출 수 있다(rules_inject 와 대조 계약); structure.json `exempt` 의 path 가 목록·dict 이면 Rust 만 건너뛴다(`str_value` 로). operator·q 뒤: advisor, workspace 의 `Context`·epoch 코드를 harness-hook `HookEnv`·`epoch` 로 합치기; q 의 상태 파일이 아주 깊게 중첩되면(손으로 고친 파일만) python 은 RecursionError 로 조용하고 Rust 는 빈 상태로 읽는다; stale_work.py 가 쓸 수 없는 서로게이트가 든 상태에서 JSON 을 반만 낸다(python 쪽 결함, 손으로 고친 파일만); subagent-slots 의 빠른 길이 `$TMPDIR` 가 쓸 수 없으면 다른 곳을 본다(양쪽 같음).

## python 이 물러날 때 걷어낼 것
python 과 바이트로 같게 하려고만 둔 것이다. python 판을 지우면 표준 crate 로 바꾸거나 지운다(Q48 a, Q53 a). 새로 넣을 때는 갈리는 입력이 실제로 오는지 먼저 재고, 오지 않는 입력에서만 갈리면 표준 crate 를 쓰고 그 차이를 알려진 차이로 둔다.
- `harness_hook::py::re`(사용자·설정 패턴) -> regex crate. `rx` 의 py::re 갈래도.
- `harness_hook::py::toml`(tomllib 이식) -> toml crate.
- `harness_hook::py::json_load`(python json 호환 파서), `py::json` 의 python 꼴 출력 -> serde_json.
- `harness_hook::py::{repr, unicode_extra, unicode_tables, surrogate, num}` 의 python 글 꼴 맞춤, `py::{ntpath, ospath, fnmatch, shlex, tempfile}` 가운데 std 나 흔한 crate 로 되는 것.
- 각 crate 의 `Unported`, `Raises` 갈래(python 이 예외로 끝나던 자리를 흉내 낸 것)와 대조 도구(`tools/tests/hook-parity.py`, `hook-corpus.py`, `HOOK_TEST_BIN`).

## 끝났다고 볼 때
- 매 도구마다 뜨는 훅이 모두 Rust 이고, 도구 한 번의 훅 CPU 가 Bash 기준 30 ms 아래.
- 지금 시험이 바이너리에서 모두 통과하고, 출력이 python 과 바이트로 같다.
- 배포 방법이 정해져 동료 기기(Windows 포함)에서 설치본만으로 돈다.
