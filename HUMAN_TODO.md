# HUMAN_TODO — 사용자가 직접 처리할 일

에이전트가 대신 할 수 없는 일만 둔다. 끝난 줄은 지운다(이력은 git log). 정할 일은 여기 두지 않고 desk 질문으로 낸다.
각 줄은 "언제 하면 되는가" 아래에 둔다. 조건이 오지 않았으면 할 일이 없다.

## 그 저장소의 세션을 열 때
그 세션에 "HANDOFF-qwreey-harness.md 읽고 처리한 뒤 지워" 한 줄이면 된다(파일은 저장소 루트에 있고 `git status` 에 안 보인다).
- 인계 파일이 남은 곳: quad, devplorer, table-sim, rbvm, moonwave-luau, vitrine, mrow, nekolog, VideoSync
- 인계 파일에 없는 것:
  - vitrine, quad: 에이전트가 넣은 `coderag.toml` 과 `.gitignore` 의 `.coderag/` 가 커밋 전이다. 커밋해 두면 다른 기기에서도 팩 rule 이 실린다
  - 팩을 켠 저장소: `.luau`(또는 `.ts`) 파일을 Read 했을 때 rule 이 한 번만 붙는지 본다. `<rule plugin="web-security">` 가 두 개 보이면 알려 주면 고친다
  - stl-luau: `doctor/diet` 를 반영한 뒤에는 `/code/Projects/stl-luau-doctor` worktree 가 필요 없다. 치우는 명령: `git -C /code/Projects/stl-luau worktree remove ../stl-luau-doctor`
  - VideoSync: 옛 worktree 의 커밋 안 된 diff 하나가 `/code/backups/claude-doctor-2026-11-10/` 에 남아 있다(44K). 그 세션이 필요 없다고 하면 폴더째 지워도 된다
  - quad, stl-luau, tbox: 자주 도는 훅의 Rust 판은 세션을 다시 시작하면 실린다. 따로 할 일은 없다

## 동료에게 배포할 때
- Windows 동료 한 명: luau-lsp 플러그인 확인(`plugins/luau-lsp/README.md` 의 Windows 절 1-4번). `.cmd` 런처는 실기기에서 돌려 본 적이 없다
- 회사 Windows PC 첫 실행(README "Windows" 절). 결과를 알려 주면 남은 위험을 고친다
  1. Git Bash 에서 `python3 -c "import sys; print(sys.executable)"` 가 진짜 파이썬을 찍는다(Store 안내 창이 뜨거나 9009 로 끝나면 README 의 python3 항목)
  2. `tools/home-sync.sh diff` 의 settings diff 에서 `qwreey-harness` 마켓 경로가 클론 위치(`C:/Users/.../qwreey-harness` 꼴)이고, `apply` 가 `settings.json JSON OK` 로 끝난다
  3. 새 세션 첫 화면에 `<plugin name="q">` 블록이 보이고 훅 오류 줄이 없다. `claude --debug` 로그에서 훅 명령이 Git Bash 로 돌고 한국어가 깨지지 않는지 본다
  4. 아무 파일 하나를 고친 뒤 qwreey-conventions 알림이 뜨고, 다른 형제 저장소 파일을 고치려 하면 workspace 게이트가 뜬다
  5. `/q:away` 뒤 `/q:back` 이 오류 없이 요약을 내고, 대화가 몇 번 오간 뒤 `session-log status` 에 기록이 쌓인다
  6. `/q:doctor --user` 에 `WIN-PYTHON3`, `WIN-GITBASH` 가 없다
- 다른 기기: coderag 마켓 추가와 `coderag@coderag-market` 설치, `~/.coderag/coderag.toml` 에 팩마다 `[[packs]]` `name`·`path`(없으면 rule 이 조용히 빠진다), `claude plugin marketplace update qwreey-harness`, 새 세션. coderag 바이너리가 없으면 기록 규약 rule 이 실리지 않고 doctor 가 `SET-CODERAG-BINARY` 로 알린다
- 배포 안내문: qwreey-delegate README 의 "Windows·비개발자 동료" 절(공식 codex-plugin-cc 설치, Stop-gate 끔, rescue 쓰기 주의)을 넣는다

## 정본이 바뀌었을 때
- `home/` 아래가 바뀌면 `tools/home-sync.sh diff` 로 보고 `apply`. 에이전트가 바꿀 때마다 알린다
- 2026-11-27 기준 대기 없음

## 새 플러그인
- qwreey-voice 0.1.0(대화 지침): 써 보려면 `claude plugin marketplace update qwreey-harness`, `claude plugin install qwreey-voice@qwreey-harness`, 그다음 새 세션이나 `/clear`. 글은 `plugins/qwreey-voice/context/ambient.md`
