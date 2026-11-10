# repo-practices — 이 사용자의 Luau 저장소들은 실제로 어떻게 테스트하나

## 이 파일이 답하는 질문
- Q1 각 저장소의 러너, 단언 방식, 에러 줄 단언, Roblox 의존 처리는?
- Q2 공통점과 차이는? 새 저장소는 무엇을 따라 하면 되나?
- Q3 원천 저장소 서술 가운데 재현해 보니 틀렸거나 빠진 것은?

## 목차
- §1 저장소별 표
- §2 공통점과 따라 할 것
- §3 정정 (각 저장소 세션에 전달)

---

## §1 저장소별 표
status: verified (2026-11-10 작업 트리를 읽기 전용으로 확인, 실행 열은 원천 claude-doctor `drafts/gaps/testing.md` §11 의 직접 실행) · 근거: 표의 경로:줄

| 저장소 (luau 핀) | 프레임워크 | 러너 | 단언 | 에러 줄 단언 | `-O2` 실행 | Roblox 의존 처리 | 타입 음성 대조군 |
|---|---|---|---|---|---|---|---|
| stl-luau (0.742) | 없음 | `luau tests/run.luau`, 엔트리가 `spec.*` 를 require(`scripts/check.sh:349-353`) | `assert` + 메시지 | 정확한 사용자 줄, `where = debug.info(1, "l") + 1`(`tests/spec.common.luau:99-130`, `conventions.md:138`) | **있음**(`scripts/check.sh:355-360`) | 의존 없음 | 스파이크 기대표(`scripts/spike-expectations.tsv`) |
| quad (0.734) | 없음 | 파일마다 `luau "$f"`(`scripts/test.sh:7,81-84`) | `assert` + 절 `print` | 한 스펙은 정확한 줄, 공용 `assertBlamesUser` 는 파일 이름만(`quad-base/test/mock.luau:854-858`) | 없음 | mock + `getfenv` 주입(`quad-roblox/test/spec.elem.luau:43`), 타입은 luau-lsp + 정의 파일 | 문서 스니펫 통제군(`scripts/doc-snippets.py`) |
| table-sim (0.734) | 없음 | `luau tests/run.luau`, 집계형 `test(name, fn)`(`tests/run.luau:27-43`) | `assert` | 없음 | 없음 | 엔진 무관 코어만 스펙(`tests/core`), Studio 는 게이트 밖(`scripts/check.sh:4`) | 3 파일 + 린트 1(`scripts/check.sh:29-62`), 등록 누락 grep(`:79-88`) |
| devplorer | 없음 | `luau tests/run.luau`, 집계형(`tests/run.luau:1-3`, `scripts/check.sh:84-85`) | `assert` | — | 없음 | 엔진 무관 코어(`tests/core`) | `tests/negative/*-error.luau` 가 반드시 실패(`scripts/check.sh:37-50`) |
| tbox | 없음 | 같은 `test/run.luau` 를 `luau` 와 `lute run` 으로(`mise.toml:23-26`), symlink 때문에 `cp -rL` 사본(`:31-42`) | `assert` | — | 없음 | `test/studio` 분리 | `test/static` 을 luau-lsp 로(`mise.toml:46`) |
| moonwave-luau (0.734) | 없음 | `luau tests/run.luau`, 즉시 실패형(`tests/run.luau:1-20`) | `assert` | — | 없음 | 의존 없음 | 게이트에 음성 대조군 단계(`scripts/check.sh:2`), 골든은 셸(`scripts/golden.sh`) |
| rbvm | 없음. **유닛 테스트 0개**(`.claude/conventions.md:71-74`) | 재현 스크립트를 `luau` 로 | `print` 로 나란히 출력 | 없음 | 없음 | 26줄 fake Instance/Signal(`.claude/review/2026-10-05-repro/fake.luau`) | 게이트는 타입·포맷만 |

원천 실행 결과(2026-11-10): quad 67/67(`-O1`), `-O2` 로는 64/67. stl-luau `-O1`·`-O2` 모두 통과. table-sim 277 passed, 0 failed.

## §2 공통점과 따라 할 것
status: described (판단) · 근거: §1

- 일곱 곳 모두 프레임워크(TestEZ, Jest)를 쓰지 않고 순수 `luau` CLI + `assert`/`pcall` 이다. D-03 의 결정과 같다.
- 음성 대조군 규칙("진단 0건을 믿지 않는다")이 다섯 곳의 게이트에 들어가 있다. 실행 테스트 쪽 대조군(러너 대조군, `-O2` 실패 고정)은 드물다(`negative-controls.md`).
- `-O2` 로도 도는 곳은 stl-luau 하나다. 에러 위치를 단언하는 저장소(quad)가 `-O2` 를 돌리지 않아 실패 3건을 놓쳤다(`optimize-levels.md` §5).
- 새 저장소의 출발점: 집계형 러너(table-sim 모양) + 등록 누락 grep + 타입 음성 대조군 파일 + `luau -O2` 두 번째 실행 + 에러는 메시지와 사용자 줄을 같이 단언.

## §3 정정 (각 저장소 세션에 전달)
- `quad/scripts/test.sh:81-84` — 스펙을 기본 `-O1` 로만 돈다. `-O2` 에서 3개 실패(`spec.errorutil`, `spec.fallback`, `spec.relate`).
- `quad/quad-base/test/mock.luau:854-858` — `assertBlamesUser` 가 파일 이름과 `/src/` 부재만 본다. level 이 틀려 같은 파일의 다른 줄을 가리켜도 통과한다(`snippets/test-blame-filename-only.luau`).
- `quad/quad-base/test/spec.errorutil.luau:21-23` — 기대 줄을 헬퍼 `curline()` 으로 잰다. `-O2` 에서 -1.
- `quad/quad-base/src/Relate.luau:28-29` — 손으로 센 `error(…, 3)`. `-O2` 에서 사용자 줄을 가리키지 않는다.
- `quad/.claude/audit/round13-e79-deferred-signals/` — 심 결과는 엔진 실측이 아니다(원천도 경고함). 이것을 엔진 사실로 인용하지 않는다.
- Jest Roblox `docs/docs/GettingStarted.md` 의 `^3.21.0` — wally 최신은 3.20.1 이라 해석에 실패할 것으로 보인다(미실행). 상류 문서 문제.
