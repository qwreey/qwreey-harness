# evals: 스킬 발동 실측

description 을 고치기 전후로 "맞는 스킬이 불리는가"를 잰 기록이다. 질문 세트·실행기·원자료는 `triggers/` 에 있다.

## 질문 세트 (`triggers/questions.tsv`)
- 발동해야 하는 질문 36개: 스킬 12개 x (한국어 2 + 영어 1). 정답은 스킬 이름 하나(`id kind lang expected question` 탭 구분).
- near-miss 14개(정답 "none"): TS·Python·Rust·Go·Node·Jest 의 비슷한 질문, Luau·Roblox 처럼 들리지만 이 지식이 필요 없는 질문(1부터 100 합, 문자열 뒤집기, 게임 아이디어, 수익화, 블렌더 내보내기, Lua 5.4 연산자), git 충돌.
- 판정: 발동 질문은 Skill 도구 호출 목록에 정답 스킬이 있으면 적중(다른 스킬이 같이 불려도 적중). near-miss 는 luau-kb 스킬이 하나라도 불리면 오발동.

## 방법
- `claude plugin eval` 은 쓰지 않았다. 이 환경의 `claude 2.1.316` 에 있으나 케이스 형식(`case.yaml`/`prompt.md` + graders)을 새로 만들어야 하고, 기본 판정 모델과 기준선 팔이 호출마다 비용을 더 쓴다. 비용 상한이 $6 라서 직접 만든 실행기 `triggers/run.py` 를 썼다.
- 호출: `claude -p --model sonnet --plugin-dir <플러그인> --setting-sources project --max-turns 1 --no-session-persistence --output-format stream-json --verbose`. 한 턴만 허용하므로 첫 도구 호출이 곧 발동 결정이다. `--setting-sources project` 로 사용자 레벨 CLAUDE.md·플러그인·메모리를 뺐다(격리, 입력 토큰 절감).
- 조건 (a) 단발: 빈 디렉터리에서 질문만. (b) 맥락 있음: `--!strict` 가 달린 `queue.luau`, `mise.toml`(luau 0.742), `.luaurc` 가 있는 디렉터리에서, 질문 앞에 "지금 Luau 라이브러리 저장소에서 작업 중이야 … 그 작업과 별개로 이걸 물어볼게." 한 단락을 붙였다.
- 기준선은 `git archive HEAD`(수정 전 description) 사본, 변경 후는 작업 트리. 같은 질문·같은 조건.
- 임시 디렉터리 `/code/.cache/luau-kb-evals/{single,ctx,base}`. 실행기: `python3 -I triggers/run.py --plugin-dir DIR --cond single|ctx --ids ... --out FILE`.

## 비용 때문에 줄인 것 (한계)
호출 하나가 약 $0.06(캐시 미적중)이라 합계 $6 안에 전부는 못 돌렸다.
- (a) 기준선: 발동 24(스킬마다 ko1 + en) + near-miss 8. 변경 후: 발동 24 + near-miss 6(ts1, rust, luau-easy, rbx-idea, lua, blender).
- (b) 기준선: 발동 12(스킬마다 ko1) + near-miss 4. 변경 후: 발동 12 + near-miss 2(luau-easy, rbx-idea).
- ko2 는 돌리지 않았다(testing-ko2 만 재시험에 1회). 질문마다 1회만 돌렸고, 어긋난 질문(testing-en)만 추가로 돌렸다.
- 기준선이 이미 100% 라서(천장 효과) 이 세트는 "떨어지지 않았는가"만 확인할 수 있고 "나아졌는가"는 말할 수 없다.
- `--setting-sources project` 라서 사용자 레벨의 다른 스킬과 경쟁하는 효과, 그리고 한 턴 뒤의 행동(스킬 로드 후)은 재지 않았다.

## 결과 (Wilson 95%)

| 조건 | 구분 | 기준선 | 변경 후 |
|---|---|---|---|
| (a) 단발 | 발동 전체 | 24/24 (86-100%) | 23/24 (80-99%) -> 재시험 뒤 24/24 |
| (a) 단발 | 한국어 | 12/12 (76-100%) | 12/12 (76-100%) |
| (a) 단발 | 영어 | 12/12 (76-100%) | 11/12 (65-99%), testing-en 이 1회 미발동 |
| (a) 단발 | near-miss 오발동 | 0/8 (0-32%) | 0/6 (0-39%) |
| (b) 맥락 | 발동 전체 | 12/12 (76-100%) | 12/12 (76-100%) |
| (b) 맥락 | near-miss 오발동 | 0/4 (0-49%) | 0/2 (0-66%) |

- 스킬별: 12개 스킬 모두 기준선에서 (a) 2/2, (b) 1/1. 변경 후에는 luau-testing 의 `testing-en`("debounce timer ... without waiting real time") 만 (a) 에서 미발동(호출 없음), 나머지 23/23 적중.
- testing-en 대응: description 의 "time or GC dependent tests" 를 "testing time-dependent logic (debounce, timers, virtual clock) or GC behavior" 로 바꾸고 한국어 트리거를 "디바운스·타이머 시험" 으로 고쳤다. 고친 뒤 3/3 적중, testing-ko2 1/1. 기준선 description 은 같은 질문에서 재시험 3/3 이었으므로 1회 미발동은 표본 변동일 수도 있다(그래도 고친 쪽이 더 명시적).
- 단발 대 맥락 차이: 관찰되지 않았다(둘 다 천장). 맥락 단락이 발동률을 올리는 효과는 이 세트로는 못 본다. 1단계의 `second-opinion:audit` 0/2 와 달리 이 지식 스킬들은 단발에서도 한 턴 안에 불렸다. 지식·증상형 질문은 description 과 직접 맞고, 감사형 요청("검토해 줘")은 모델이 스킬 없이 직접 한다는 차이로 보이나 추정이다.
- 되돌린 스킬: 없음.

## description 길이
평균 564.7자 -> 535.0자(12개). 영어 3인칭 + 끝에 한국어 트리거 구절 3개. 목표 300~500자를 못 지킨 스킬이 많다(주제 어휘를 줄이면 발동 근거가 줄 것이라 기준선 100% 를 지키는 쪽을 택했고, 더 줄인 뒤에는 재시험 예산이 없었다).

## 이번에 같이 한 것
- 본문의 시간 민감 서술 정리: luau-perf 의 절대 경로·결과 파일 날짜·원천 문서는 `skills/luau-perf/references/provenance.md` 로, luau-types·luau-verify 의 특정 버전 단정, luau-upstream 의 절대 경로와 구체 버전, luau-roblox 의 날짜는 일반 표현으로.
- `rules/luau-core.md` 에 "symptom -> skill / reference" 색인 추가: 40줄 -> 56줄(+16, 섹션 머리·안내 문장 포함).
- 아직 남은 것: 일부 references 에 `> 정책: 제안(D-xx)` 표시와 `decisions/README.md` 의 "미결·제안" 문구가 2026-11-11 확정 이전 그대로다.

## 다시 돌리기
```
python3 -I evals/triggers/run.py --plugin-dir . --cond single --ids types-ko1,neg-lua --out /tmp/x.jsonl
```
`triggers/results/*.jsonl` 에 이번 원자료(질문별 호출 목록·비용)가 있다. `base-single-rerun` 은 기준선의 testing-en 재시험(호출당 캐시 적중으로 비용이 낮게 찍힘).
