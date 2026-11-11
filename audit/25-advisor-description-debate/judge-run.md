# second-opinion description 판정 실측 (judge-run)

날짜 2026-11-11. 새 안 = c5e60f5, 옛 안 = d6dfb99. 원자료: `/code/.cache/so-judge/`(raw/*.jsonl, w/*.txt 장면 원문, run1.sh, summ2.py).

## 방법
- 사본 `/code/.cache/so-judge/{new,old}/p` 는 `plugins/second-opinion` 복사 후 inherit-advisor, fresh-advisor 의 SKILL.md 만 각 커밋 것으로 교체(diff 로 description 줄만 다름을 확인).
- `claude -p --resume <기반 세션 c72a0f98> --fork-session --model sonnet --plugin-dir <사본> --max-turns 2 --tools=Skill,Agent --output-format stream-json --verbose`. 장면은 프롬프트에 대화 기록 형태로 넣고 "다음 응답이나 행동을 이어라" 로 끝낸다.
- init 의 skills 목록에 code-review 확인됨(양쪽 사본 모두 second-opinion:inherit/fresh/other-frame 포함).
- 발동 = Skill 호출(inherit/fresh) 또는 Agent 호출(fork, 표지 second-opinion). 도구 이름은 Skill/Agent(Task).

## 장면 요약
- S1(양성): install-hooks.sh 의 훅 덮어쓰기를 jq 로 고쳤다고 하고 "끝, 보존된다" 선언. 테스트 출력에 "기존 PreToolUse 훅 케이스 SKIP(fixture 없음)" 이 있으나 메인은 언급하지 않음. 사용자: "apply 안내 써 줘".
- S2(양성): `/code/.cache/so-ab/w/scene.md`(seen.json 훅 설계, "설계 끝, 로컬 테스트 통과" 주장, 동시 세션 약점) 재사용, 마지막 지시만 일반 "이어서 응답" 으로 교체.
- N1 변수 이름 바꾸기 후 "됐어?", N2 Python json 함수 질문, N3 README 오타 한 줄 수정 후 "됐어?".
- R1: "커밋 전에 이 diff 버그 봐줘"(diff 요약 포함).
- C1(확인): seen.json 로직 변경 후 사용자 "한 번 더 봐줘".

## 결과 (발동 수/시행)
| 장면 | 새 안 | 옛 안 |
|---|---|---|
| S1 양성 | 0/5 | 0/5 |
| S2 양성 | 0/5 | 0/5 |
| 양성 합계 | 0/10 | 0/10 |
| N1 | 0/2 | 0/2 |
| N2 | 0/2 | 0/2 |
| N3 | 0/2 | 0/2 |
| 오발동 합계 | 0/6 | 0/6 |
| R1 (second-opinion 으로 샌 횟수) | 0/2 | 0/2 |
| C1 확인 "한 번 더 봐줘" | 2/2 | 2/2 |

- N3 에서 양 안 1회씩 일반 Agent(파일 확인 서브에이전트)가 불렸으나 second-opinion 이 아니므로 오발동 아님.
- R1 은 양쪽 모두 Skill 없이 직접 처리(경로 정답).
- 양성 두 장면 모두에서 모델은 스킬 없이 스스로 약점(SKIP 된 테스트, 동시 세션)을 짚고 답을 정정했다. 즉 양 안 모두 "자발 발동" 은 0.

## 판정
- 두 안 모두 오발동 기준(2/15 이상 실격)은 통과(0/6).
- 양성 발동 차이 0/10 (기준 2/10) → **비김**. description 문구 차이는 이 장면 조건에서 자발 발동에 영향을 주지 못했다. 규칙대로 사용자가 고른 모양에 가까운 쪽을 택하는 단계이며 이 실측은 어느 쪽도 지지하지 않는다.
- 확인 장면은 양 안 모두 통과(2/2). 명시적 사용자 요청 경로는 두 안 모두 작동.
- 부수 관찰: 양성 장면에서 발동률 0 은 description 보다 장면 자체(모델이 약점을 혼자 정정함)에 가깝다. description 을 바꿔 자발 발동을 끌어올린다는 가설은 이 실측에서 확인되지 않았다.

## 비용
- 본 시험 약 $2.83 + 도구 설정 확인용 시험 약 $0.4 + 기반 세션 $0.02 = 약 $3.2. 상한 $3 을 약 $0.2 넘었다(예측 오차, 도구 제한 옵션 탐색 중 발생).
- 음성은 N=5 가 아니라 N=2(6시행), R1 N=2, C1 N=2 로 줄였다.

## 한계
- 음성 N=2 로 오발동 검출력이 낮다(기준 2/15 에 대응하는 표본 6). 양성이 0이라 오발동도 0일 가능성이 높지만 확정은 아니다.
- 양성이 양쪽 0 이라 바닥 효과가 있다. 차이를 가르려면 더 유도적인 장면이 필요하다.
- 도구를 Skill,Agent 로 제한했고(`--tools=`; 공백 형태는 무시됨) Bash/Read 등이 없어 모델이 직접 검증하지 못하는 환경이다. 장면은 대화 기록을 프롬프트에 붙인 모사로 실제 도구 결과가 없다.
- 장면 S1 약점이 transcript 에 보이게 심겨 있어 모델이 스스로 발견했다. "메인이 기록하지 않은 약점" 이라는 설계와 완전히 같지 않다.
- 플러그인 훅(nudge 등)은 양쪽 동일하게 활성이었으며 Bash 가 없어 거의 작동하지 않았다.
- 사용자 환경의 다른 스킬(verify, debug 등)이 목록에 함께 있었다.
- 새로 생긴 임시 프로젝트 키: `-code--cache-so-judge` 하나(`/code/.claude/projects/` 아래, 기반 세션과 fork 세션들).
