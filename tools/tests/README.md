# tools/tests/

저장소 전체를 보는 테스트. 각각 `python3 -I tools/tests/<파일>` 로 돌린다(exit 0 = 통과, 표준 라이브러리만, 모델 호출 없음). 플러그인 하나만 보는 테스트는 그 플러그인의 `tests/` 에 있다.

| 파일 | 보는 것 |
|---|---|
| `test-prompt-surface.py` | 모델이 보는 글(rule 본문, 상시 규약 블록, 서브에이전트 글, 스킬과 에이전트 목록 줄, desk 도구 설명, 훅 알림 대표)이 스냅숏 `prompt-surface/*.txt` 와 같은지, 항목 크기가 `prompt-surface/sizes.json` 보다 늘지 않았는지, 훅 출력 하나가 9,000자 아래인지. 세션 시작 합계를 찍는다 |
| `test-hook-replay.py` | `hook-replay/cases/*.json` 사례마다 임시 저장소를 만들고 훅을 하위 프로세스로 돌려 판정(exit, decision, `<harness-hook name level>` 태그와 nonce, 핵심 문구)을 본다 |
| `hook_sandbox.py` | 위 둘과 `tools/regen-prompt-surface.py` 가 쓰는 샌드박스(TMPDIR, HOME, 설정 폴더, session-log 저장소, 고정 salt 를 모두 임시 폴더로). `HOOK_SANDBOX_SIMWIN=1` 이면 훅을 `simwin.py` 로 돈다 |
| `simwin.py` | Windows 흉내: fcntl·pwd 를 막고 getuid·setsid·`/proc`·choom 을 지운 채 스크립트를 돈다. `HOOK_SANDBOX_SIMWIN=1 python3 -I tools/tests/test-hook-replay.py` 로 훅 재생을 그대로 흉내 낸다(경로 구분자, 셸, 코드 페이지, `os.name` 분기는 못 본다) |
| `test-hook-commands.py` | `hooks.json` 의 command 가 모두 `python3 -I -X utf8 "${CLAUDE_PLUGIN_ROOT}/...py"` 꼴인지(Windows 의 Git Bash·PowerShell 에서도 도는 꼴, 머리 주석에 이유) |
| `test-ambient-lib.py`, `test-vendored-copies.py`, `test-sync-copies.py` | `lib/` 정본과 사본 |
| `test-harness-env.py`, `test-harness-env-owners.py`, `test-settings-migrate.py` | `home/` 의 harness.env 로더와 settings 마이그레이션 |
| `test-coderag-rules-parity.py`, `test-coderag-skip-dirs.py` | coderag 와의 대조(`CODERAG_SRC`, `CODERAG_BIN` 이 있어야 돈다) |
| `test-delegate-cli.py`, `test-delegate-config.py` | qwreey-delegate |

## prompt surface 스냅숏

훅은 고정 salt 로 돌리므로 태그의 nonce 까지 실행마다 같다. 기계마다 다른 경로는 `<sandbox>`, `<root>`, 오늘 날짜는 `<today>` 로 바꿔 둔다.
nonce 규칙 줄은 어느 플러그인이 맡을지가 병렬 훅의 경합이라 각 블록에서 빼고 `nonce-rule.txt` 하나로 센다.

- 다시 만든다: 모델이 보는 문구를 일부러 바꿨을 때(rule, `context/*.md`, 스킬 description, 훅 메시지, desk 도구 설명). `python3 -I tools/regen-prompt-surface.py`, 그리고 바뀐 `.txt` 를 같은 커밋에 넣는다. 의도하지 않은 diff 면 다시 만들지 말고 원인을 고친다.
- 크기는 래칫이다. 줄면 테스트는 통과하고 sizes.json 을 낮추라고 알린다(위 명령이 낮춘다). 늘거나 항목이 새로 생기면 테스트가 실패하고 위 명령도 sizes.json 을 올리지 않는다. 늘려야 하면 `--allow-growth` 로 올리고 무엇이 왜 늘었는지 커밋 메시지에 적는다. 먼저 줄일 곳을 찾는다.
- `--check` 는 아무것도 쓰지 않고 diff 만 보인다.
- 덮지 못하는 것: desk 모드가 실행 중에 만드는 글(결정 요약, 채팅 줄 기록)은 모드 엔진 없이 돌릴 수 없어 빠진다. 도구 설명과 입력 스키마는 `register.tsx` 소스의 리터럴에서 꺼낸다. 팩 rule 은 coderag 가 싣지만 그 출력은 `rules_inject.py` 와 바이트가 같으므로(`test-coderag-rules-parity.py`) 참조 구현으로 만든다.

## 훅 재생 사례 더하기

`hook-replay/cases/` 에 JSON 파일 하나를 더한다. 형식은 `test-hook-replay.py` 머리에 있다. 훅은 `hooks.json` 이 부르는 스크립트 경로로만 부르므로 스크립트 안을 나눠도(경로와 출력이 같으면) 사례는 그대로다.
