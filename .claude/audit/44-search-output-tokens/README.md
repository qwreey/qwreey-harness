# coderag search 출력 토큰 절감 실측

> Snapshot 2026-11-12. coderag 3fd0944(플러그인 0.4.0)의 `search` 출력 형식 변경 실측. 근거: quad 3질의 23결과에서 절대경로가 글자의 30%(추정 토큰 약 18%), 꼬리표 약 7%. 사용자 결정 "추천대로"(A+C 기본, B 옵션).

## 한 일
- 구현(coderag 저장소, 커밋 3fd0944, 푸시 없음):
  - A. 범례 + 상대 경로(기본): 맨 위에 결과에 나온 루트만 `@P = /절대/루트`, 결과는 `@P/rel:줄`. 라벨은 project `P`, global `G`, pack 은 이름 첫 글자 대문자(겹치면 `Lu`·`La`, P·G 와 겹쳐도 늘림).
    같은 라벨의 모듈이 여럿이면 루트의 공통 조상 한 줄(luau-kb 는 스킬마다 모듈이라 `@L = …/luau-kb/skills`, 결과는 `@L/luau-types/references/…`). 라벨은 코퍼스 내용만으로 정해져 호출 사이에 같다.
    `--abs` 는 옛 절대경로 출력 그대로(범례 없음, 꼬리표에 계층). 범례 형식 경로를 `coderag get '@P/rel'` 이 풀고, `→ 이 프로젝트:` 도 같은 형식.
  - C. 꼬리표: 구분 `, `, 범례 방식에서는 계층 조각(`project`·`pack:luau-kb`)을 뺌(라벨이 보임), `절 단위 13절` 은 `13절`. search·list·get 머리와 get 목차에 같이 적용. 예: `[reference, partial, 13절]`.
  - B. `--handles`: `#6자리:줄`(경로 없음). 핸들은 경로 FNV-1a 의 앞 6자리이고 코퍼스(숨김 포함)에서 접두가 겹치면 8·10자리로 늘림. `get '#핸들'`(`:a-b` 꼬리 허용, `--section`·`--body` 가능), 모호하면 오류에 후보 경로.
  - `--json` 은 모양 그대로, `root`·`handle` 필드만 추가. `--level` 출력도 같은 경로 형식.
- 안 한 것: M6 compact 포인터 줄(훅)은 손대지 않음(기본 유지, handles 옵션도 안 줌). `list`·`get`·`stale` 머리 경로는 옛 형식(cwd 상대/`--abs`) 그대로, 꼬리표만 압축.
- claude-doctor 호출부: q:recall 과 coderag `agents/doc-locator.md` 는 `--abs` 를 유지한다. 둘 다 결과 줄을 다른 에이전트에게 파일 경로로 넘기는 haiku 위치 조사자라, 범례를 쓰면 매번 루트+rel 을 다시 조립해야 한다(오조립 위험이 이득보다 큼).
  recall 에는 이유 한 구절을 더했고, doc-locator 는 새 꼬리표 모양으로 고쳤다. 그 밖에 검색 출력을 파싱하는 스크립트·스킬은 없다(grep 확인).
- 테스트: coderag `cargo test --workspace` 통과(범례 배정·번호·조상, 핸들 안정·유일·충돌 모호, 꼬리표, `--abs` 옛 출력, `get #핸들`·`@P/…`, `--json` 필드를 단위·e2e 로 추가), `claude plugin validate` 통과(경고만), claude-doctor 테스트 전부 통과.

## 측정
도구: 이 폴더 `measure.py`(audit/39 `measure.py` 의 트리 만들기·`--map move-map.tsv`·gold 를 불러 쓰고 audit/43 의 추정식 `0.4×ASCII + 1.6×한글 + 1.5×그 밖`). 격리 `CODERAG_CACHE`, 모델 호출 없음.
실행: `python3 -I measure.py --root <repo> --map ../39-records-experiment/move-map.tsv --new <새 bin> --old <옛 bin(3fd0944 의 부모)>`. 원출력은 `raw/`(gitignore).
12문항은 audit/39 gold(말뭉치를 `/tmp/cr44/code/Projects/claude-doctor` 로 복사, cwd 는 그 트리), 팩 5질의는 cwd quad(읽기 전용, `--layer project,pack`; quad 는 luau-kb 만 목록에 있어 web-security 질의는 뺌).
"old default" 는 옛 바이너리 기본 출력(cwd 아래는 상대, 밖은 절대). 질의당 추정 토큰 평균:

| 설정 | 12문항 | old default 대비 | 팩 5질의(quad) | old default 대비 |
|---|---|---|---|---|
| old default | 952 | - | 1,424 | - |
| old `--abs` | 1,044 | +10% | 1,446 | +2% |
| new default (A+C) | 976 | +2% | 1,306 | -8% |
| new `--abs` | 1,043 | +9% | 1,426 | +0% |
| new `--handles` | 869 | -9% | 1,222 | -14% |
| old default + auto 2000 | 1,849 | +94% | 1,913 | +34% |
| new default + auto 2000 | 1,875 | +97% | 1,959 | +38% |
| new `--handles` + auto 2000 | 1,791 | +88% | 1,951 | +37% |

- 랭킹은 모든 설정에서 같다(결과의 줄 범위·제목 순서가 old/new·`--abs`·`--handles`·auto 2000 사이에 일치). 새 `--abs` 로 잰 hit@5 는 12문항 11/12(MRR 0.743), 팩 5/5(MRR 0.900).
- 효과는 경로가 긴 쪽에서 난다. 에이전트가 쓰는 `--abs` 대비 새 기본은 12문항 -6%, 팩 질의 -8%(기본 대비는 -8%). 12문항에서 old default 보다 +2% 인 것은 cwd 상대 경로(`.claude/…`)가 이미 짧고,
  이 사본 설정에 프로젝트 모듈이 둘(`.claude` 와 루트 PLAN.md 용)이라 공통 조상이 저장소 루트가 되어 `@P/.claude/…` 로 접두가 붙기 때문이다(범례 한 줄도 추가). 실제 저장소(`.claude` 하나)에서는 접두가 없다.
- 처음 가설(경로 18%)만큼은 안 줄었다: 경로는 루트가 빠져도 `luau-types/references/type-functions-limits.md` 같은 rel 부분이 남는다. `--handles` 가 가장 싸다(-14%·-9%) 대신 경로가 안 보여 `get` 이 한 번 더 필요하다.
- auto 2000 은 줄어든 머리 글자 수만큼 예산이 남아 본문을 더 펼치므로 토큰이 오히려 +수십~80(old 대비 +1~3%포인트). 같은 예산에서 더 많은 본문을 얻는 것이라 손해로 보지 않지만 "절감" 은 아니다. 범례 줄은 예산에 안 센다.

## 모델 확인(경로 조립)
claude-doctor 에서 `claude -p --model sonnet --tools Read --max-budget-usd 0.6` 4회(이 CLI 에 `--max-turns` 없음, Read 만 허용). 새 기본 검색 결과를 프롬프트에 붙이고 둘째 결과의 줄 범위를 Read 하게 함(`raw/model-check-*.jsonl`).

| 질의 | 둘째 결과 | Read 경로·범위 | 판정 |
|---|---|---|---|
| p3 type function 제약 | `@L/luau-types/references/generics.md:95-109` | `…/luau-kb/skills/luau-types/references/generics.md` 95/15 | 정확 |
| p5 generic 상한 | `@L/luau-types/references/variance.md:135-141` | `…/skills/luau-types/references/variance.md` 135/7 | 정확 |
| p1 `__index` | `@P/base/README.md:1-48`(quad) | `/code/Projects/quad/.claude/base/README.md` 1/48 | 정확(첫 시도는 25k 토큰 상한 오류라 `allow_large` 로 재시도, 경로 문제 아님) |
| q03 coderag 검색 | `@P/.claude/audit/43-levels-measure/README.md:6-12` | `/tmp/cr44/code/Projects/claude-doctor/…/README.md` 6/7 | 정확 |

4/4 에서 루트+rel 조립과 offset=시작, limit=끝-시작+1 이 맞았다. 서로 다른 루트 둘(`@L`·`@P`)이 섞인 결과에서도 틀리지 않았다. 표본이 작아 haiku 로의 조립 안정성은 못 쟀다(그래서 recall·doc-locator 는 `--abs`).

## 못 한 것·열린 것
- 에이전트가 `--handles` 를 쓰고 `get` 을 더 부르는 총비용은 안 쟀다(한 호출 절감만 측정).
- 실제 quad 의 3질의 23결과 재측정은 안 했다(위 5질의로 대체). web-security 질의는 quad 에 팩이 없어 뺐다.
- M6 compact 포인터 줄의 핸들 옵션, `list`/`get` 의 범례 형식은 하지 않았다.
- 기본 출력 형식이 바뀌어 이 형식을 파싱하던 바깥 스크립트(이 저장소엔 없음)와 다른 저장소 문서의 `[… · …]` 예시는 옛 모양으로 남는다.
