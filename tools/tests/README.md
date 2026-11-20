# tools/tests/

저장소 전체를 보는 테스트. 각각 `python3 -I tools/tests/<파일>` 로 돌린다(exit 0 = 통과, 표준 라이브러리만, 모델 호출 없음). 플러그인 하나만 보는 테스트는 그 플러그인의 `tests/` 에 있다.

| 파일 | 보는 것 |
|---|---|
| `test-prompt-surface.py` | 모델이 보는 글(rule 본문, 상시 규약 블록, 서브에이전트 글, 스킬과 에이전트 목록 줄, desk 도구 설명, 훅 알림 대표)이 스냅숏 `prompt-surface/*.txt` 와 같은지, 항목 크기가 `prompt-surface/sizes.json` 보다 늘지 않았는지, 훅 출력 하나가 9,000자 아래인지. 세션 시작 합계를 찍는다 |
| `test-hook-replay.py` | `hook-replay/cases/*.json` 사례마다 임시 저장소를 만들고 훅을 하위 프로세스로 돌려 판정(exit, decision, `<harness-hook name level>` 태그와 nonce, 핵심 문구)을 본다 |
| `hook_sandbox.py` | 위 둘과 `tools/regen-prompt-surface.py` 가 쓰는 샌드박스(TMPDIR, HOME, 설정 폴더, session-log 저장소, 고정 salt 를 모두 임시 폴더로). `HOOK_SANDBOX_SIMWIN=1` 이면 훅을 `simwin.py` 로 돈다. `HOOK_SANDBOX_PLUGIN_COPY=1` 이면 설치본을 흉내 낸다(아래). `run_argv` 는 실행 형식(command + args, 셸 없이)의 argv 를 같은 환경에서 띄우고, `plugin_env` 는 Claude Code 처럼 플러그인 환경 변수를 단다. `replay()` 는 사례의 파일, 준비 명령, 단계를 차례로 놓는 하나뿐인 정의(재생 시험과 `hook-parity.py` 가 함께 쓴다) |
| `simwin.py` | Windows 흉내: fcntl·pwd 를 막고 getuid·setsid·`/proc`·choom 을 지운 채 스크립트를 돈다. `HOOK_SANDBOX_SIMWIN=1 python3 -I tools/tests/test-hook-replay.py` 로 훅 재생을 그대로 흉내 낸다(경로 구분자, 셸, 코드 페이지, `os.name` 분기는 못 본다) |
| `test-hooks-simwin.py` | `hooks.json` 의 모든 훅을 `simwin.py` 로 한 번씩 돌려 죽지 않는지(exit 0 또는 2, Traceback 없음) |
| `test-hook-commands.py` | `hooks.json` 의 command 가 모두 `python3 -I -X utf8 "${CLAUDE_PLUGIN_ROOT}/...py"` 꼴(Windows 의 Git Bash·PowerShell 에서도 도는 꼴)이거나, `args` 가 있으면 `${CLAUDE_PLUGIN_ROOT}/native/<바이너리>` 실행 꼴인지(머리 주석에 이유) |
| `hook-parity.py` | 시험이 아니라 대조 실행기: python 훅과 바꿀 실행 형식(Rust 바이너리 등)에 hook-replay 사례와 트랜스크립트의 실제 도구 호출(`--from-transcripts N`)을 같은 샌드박스 둘에서 넣고 종료 코드와 stdout 을 바이트로 비교한다(stderr 는 따로 알림). 양쪽 모두 CLAUDE_PLUGIN_ROOT, CLAUDE_PLUGIN_DATA 를 단다. 대조표 형식은 머리 주석, `--identity <플러그인>` 은 python 대 python |
| `hook-corpus.py` | 시험이 아니라 대조 실행기: 다른 저장소의 실제 파일(읽기만, 임시 저장소에 복사)로 새 파일, Edit, 덮어쓰기를 흉내 내어 python 훅(conventions-check, reuse-check, structure-reminder)과 바이너리의 종료 코드와 stdout 을 견주고 양쪽 CPU 합을 찍는다. `--bin <바이너리> REPO...` |
| `test-hook-parity.py` | `hook-parity.py` 와 `run_argv`: identity 는 모두 같음, 다른 대역은 diff, 없는 바이너리는 exit 127, 양쪽에 플러그인 환경 변수, 가짜 트랜스크립트의 입력 만들기 |
| `test-ambient-lib.py`, `test-vendored-copies.py`, `test-sync-copies.py` | `lib/` 정본과 사본 |
| `test-harness-env.py`, `test-harness-env-owners.py`, `test-settings-migrate.py` | `home/` 의 harness.env 로더(플러그인 옵션 층 포함)와 settings 마이그레이션 |
| `test-rename-cutover.py` | `tools/rename-cutover.sh`(폴더·마켓 이름 전환): 가짜 저장소, 설정 폴더, session-log, coderag 설정과 `claude` 흉내로 dry-run 무변경, apply 와 재실행, main 이 움직였을 때 merge, 막는 조건마다 아무것도 바뀌지 않음 |
| `test-known-repos.py` | `lib/known_repos.py`: 세션 기록 cwd 로 저장소 모으기, worktree 합치기, extra, exclude, 기본 제외, 옛 `HARNESS_WORKSPACE`, 캐시 |
| `test-plugin-userconfig.py` | 모든 plugin.json 의 `userConfig`: 필수 필드, 키의 대문자를 그 플러그인 코드가 읽는지, `default` 가 코드 기본값(`*DEFAULTS`)과 같은지. `claude` 가 PATH 에 있으면 플러그인마다 `claude plugin validate` |
| `test-coderag-rules-parity.py`, `test-coderag-skip-dirs.py` | coderag 와의 대조(`CODERAG_SRC`, `CODERAG_BIN` 이 있어야 돈다) |
| `test-delegate-cli.py`, `test-delegate-config.py` | qwreey-delegate |
| `test-usage-report.py` | `tools/usage-report.py`: 가짜 트랜스크립트로 훅 목소리와 수준, 거부, 실행 시간(Stop 은 stop summary 에서만), 상시 주입, 서브에이전트, 토큰(message.id 마다 한 번), 시험 키 빼기, 창 거르기, 보고서에 내용이 새지 않음. 가짜 플러그인으로 `--time-hooks` 한 번 |

## prompt surface 스냅숏

훅은 고정 salt 로 돌리므로 태그의 nonce 까지 실행마다 같다. 기계마다 다른 경로는 `<sandbox>`, `<root>`, 오늘 날짜는 `<today>` 로 바꿔 둔다.
nonce 규칙 줄은 어느 플러그인이 맡을지가 병렬 훅의 경합이라 각 블록에서 빼고 `nonce-rule.txt` 하나로 센다.

- 다시 만든다: 모델이 보는 문구를 일부러 바꿨을 때(rule, `context/*.md`, 스킬 description, 훅 메시지, desk 도구 설명). `python3 -I tools/regen-prompt-surface.py`, 그리고 바뀐 `.txt` 를 같은 커밋에 넣는다. 의도하지 않은 diff 면 다시 만들지 말고 원인을 고친다.
- 크기는 래칫이다. 줄면 테스트는 통과하고 sizes.json 을 낮추라고 알린다(위 명령이 낮춘다). 늘거나 항목이 새로 생기면 테스트가 실패하고 위 명령도 sizes.json 을 올리지 않는다. 늘려야 하면 `--allow-growth` 로 올리고 무엇이 왜 늘었는지 커밋 메시지에 적는다. 먼저 줄일 곳을 찾는다.
- `--check` 는 아무것도 쓰지 않고 diff 만 보인다.
- 덮지 못하는 것: desk 모드가 실행 중에 만드는 글(결정 요약, 채팅 줄 기록)은 모드 엔진 없이 돌릴 수 없어 빠진다. 도구 설명과 입력 스키마는 `register.tsx` 소스의 리터럴에서 꺼낸다. 팩 rule 은 coderag 가 싣지만 그 출력은 `rules_inject.py` 와 바이트가 같으므로(`test-coderag-rules-parity.py`) 참조 구현으로 만든다.

## 설치본 흉내

`HOOK_SANDBOX_PLUGIN_COPY=1 python3 -I tools/tests/test-hook-replay.py` 는 `plugins/*`, `packs/*` 를 저장소 밖 임시 폴더의 `cache/<마켓>/<이름>/<버전>/` 으로 플러그인마다 따로 복사하고, 훅을 그 사본에서 `CLAUDE_PLUGIN_ROOT`(사본 폴더), `CLAUDE_PLUGIN_DATA`(`<cfg>/plugins/data/<이름>-<마켓>`)와 함께 돌린다. GitHub 마켓으로 받은 동료의 설치본처럼 이 저장소의 클론 위치나 옆 플러그인 폴더에 기대는 훅이 여기서 드러난다. 출력의 사본 경로는 `<root>/plugins/<이름>` 꼴로 되돌려 비교한다. 출시 전에 평소 모드와 함께 돌린다.

## 훅 재생 사례 더하기

`hook-replay/cases/` 에 JSON 파일 하나를 더한다. 형식은 `test-hook-replay.py` 머리에 있다. 훅은 `hooks.json` 이 부르는 스크립트 경로로만 부르므로 스크립트 안을 나눠도(경로와 출력이 같으면) 사례는 그대로다.
