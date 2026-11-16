---
format: 1
title: 59. 외부 플러그인·하네스 7개 조사 (superpowers, gstack, awesome-claude-skills, oh-my-claudecode, ECC, claude-mem, hermes-agent)
description: 잰 근거가 있는 것만 들인다: compact 뒤 사용자 원문·식별자 목록·복구 경로(hermes +22.5pt), 훅 출력 10,000자 절벽(claude-mem), 큰 파일 통째 읽기 사전 차단(32KB 이상 -30~38%, 19KB 는 역효과), 프롬프트 시점 힌트의 오발 방지(에코·정보성 질문 거르기, gstack 오발 17/32); "스킬을 반드시 먼저" 상시 문구·첫 편집 deny(ECC 비용 +37% 효과 p=0.21)·라우터 메타 스킬은 들이지 않는다
---
# 59. 외부 플러그인·하네스 조사

> Snapshot 2026-11-16. May differ from now; check current files and git log before relying on it.

사용자: "스킬 뿐만 아니라 플러그인도 조사할만한게 많이 있어보여. 특히 우리가 플러그인 만들면서 다른 플러그인은 어떻게 하는지 파본적이 없는것 같아서." 서브에이전트(opus) 3개가 `/tmp/ext/` 에 clone 해 읽기만 했고, 메인이 효과 수치 몇 개를 원문에서 다시 확인했다(hermes SCORECARD, claude-mem ContextBudget, ECC McNemar, OMC persistent-mode). 저장소별 메모는 `raw/` (커밋 안 함).

## 잰 근거가 있는 것
| 출처 | 무엇 | 결과 |
|---|---|---|
| hermes `evals/compaction/results/SCORECARD-2026-08-15.md` | 자체 압축기에 사용자 발화 원문, 정규식 식별자 목록(Anchor Index), 복구 경로를 붙임 | 평균 +22.5pt(68.3 대 45.8), 토큰 1/3.3; needle 질문 23.3 -> 60.0 (transcript 4개, LLM judge) |
| claude-mem `tests/evals/read-gate/` (`claude plugin eval`) | 32KB 이상 파일 통째 Read 를 PreToolUse 에서 막고 부분 읽기를 안내 | 49KB 에서 비용 sonnet -38%, opus -30%, 정답 유지. 19KB 까지 막으면 opus +20% |
| claude-mem `src/services/context/ContextBudget.ts:3-9` | 훅 stdout 은 10,000자까지만 그대로 전달, 넘으면 약 2KB 미리보기로 바뀌고 훅은 성공으로 보고 | 코드 상수로 고정. MCP instructions 는 4,096자 |
| gstack `docs/skill-routing-and-contracts.md:38` | 설치된 모든 스킬 트리거로 라우팅 | 맞지 않는 프롬프트 32개 중 17개 오발, 4개 스킬로 줄이니 4개 |
| gstack CHANGELOG `:1054` | 설명 없이 /investigate | opus 252회 중 0회 |
| ECC `docs/gateguard/question-effectiveness.md` | 첫 편집 deny 후 사실 진술 강요(사전 등록, 96회) | 25/48 대 18/48, McNemar p=0.21 미확인; 턴 +37%, 비용 +40%. 그래도 기본 켜짐 |
| superpowers `docs/superpowers/specs/2026-06-10-positive-instruction-redesign-design.md` | 문구 변형 micro-test(API 1회, grep 채점, 대조군) | 금지문이 지침 없음보다 나쁨(4.4 대 3.6), "Ties go to the shorter phrasing" |
| superpowers RELEASE-NOTES `:535` | 계획 검토 서브에이전트 루프 | 시간 약 25분 늘고 품질 차이 없음(5버전 x 5회) |

## 우리 결론과 같은 것
- 스킬 본문·rule·CLAUDE.md 의 "자세한 건 보라" 포인터는 로드를 일으키지 않는다: gstack "routing prose there never routed anything"(CHANGELOG `:6068`), claude-mem "never actually loaded"(docs/CHANGELOG `:191`), audit 57.
- 프롬프트 시점의 좁은 힌트만 효과가 있다(audit 58, gstack 결정적 라우터).
- 막는 것보다 한 번 알리는 것: ECC GateGuard 의 비용·효과 수치.

## 들일 만한 것 (우리 플러그인별)
- qwreey-sessions: compact 뒤 주입에 그 구간 사용자 발화 원문과 기계로 뽑은 식별자(바뀐 파일, 커밋, 오류 문자열), 복구 경로를 넣는다(우리 compaction 위에서 효과는 먼저 잰다). 인계에 "X 는 안 된다" 같은 부정 주장과 못 푼 시도를 결론처럼 넣지 않는다(hermes background_review).
- 모든 훅: 출력 10,000자 상한을 확인한다(인계, coderag-recall, rule 묶음).
- 스킬 힌트 훅(audit 58 실측 중): 붙여 넣은 훅 출력·기록을 지운 뒤 매칭(OMC #2795), 키워드 가까이 "뭐야/어떻게/설명해줘" 면 내지 않음, 오발 측정 묶음, `--explain`, `/` 와 8,000자 초과 프롬프트 건너뜀, 로그에 프롬프트 원문을 남기지 않음.
- qwreey-sessions `records_read.py`: 큰 기록 통째 Read 를 사후 경고에서 사전 차단으로(하한 약 32KB; 막는 장치라 사용자 결정).
- 서브에이전트 규범(operator): "자식을 띄웠으면 결과를 모은 뒤 끝낸다, 'waiting' 으로 끝내지 않는다"(ECC 관찰 근거; 이 세션에서도 보고 뒤 백그라운드 작업이 남은 에이전트가 두 번 있었다). 기본 지시와 겹치는지 먼저 확인.
- HOOK-MESSAGES: Stop 을 막는 훅의 안전 목록(맥락 한도·사용자 중단·인증 오류로 멈춘 경우와 `stop_hook_active` 재진입은 막지 않음, 횟수 상한; OMC #213 compact 교착). SubagentStop 의 additionalContext 가 끝나는 서브에이전트에 다시 들어간다는 OMC #3209/#3233 은 우리 환경에서 확인한다.
- 시험: 늘 실리는 문구(ambient, rule, 스킬 description, HOOK-MESSAGES) 스냅숏과 크기 상한 시험(hermes prompt surface, gstack 바이트 래칫); 훅 발화의 결정적 재생 코퍼스(ECC); audit 57·58 프로브를 `claude plugin eval` 스위트로(claude-mem).
- 측정 위생: 칸당 3회 이상, 단발 차이 +-3% 는 소음(hermes), 대조군과 placebo arm, 사전 등록과 McNemar(ECC), 답이 저장소 안에 있는 함정은 재지 못한다.
- 나중(미측정): 편집 직전 교훈 tripwire(great_cto), 스킬 산출물 계약 Stop 한 번 막기(gstack), 스킬 범위 훅(SKILL.md `hooks:`), 설치 때 묻는 `userConfig`(ECC, env 전달 미확인), 스킬 실사용 집계(hermes curator 착상).

## 들이지 않을 것
- 세션마다 "스킬이 1% 라도 맞으면 반드시 불러라" 류 상시 bootstrap(superpowers, hermes): 로드율 측정이 없고, superpowers 가 근거로 든 설득 연구는 거부 우회 연구다.
- 라우터·인덱스 메타 스킬, CLAUDE.md 라우팅 표(gstack 스스로 효과 없음).
- 첫 편집 deny(ECC GateGuard), 도구마다 일반 리마인더(OMC, 우리 HOOK-MESSAGES 규칙 4 위반).
- `~/.claude/CLAUDE.md` 덮어쓰기(OMC setup), 검증 안 된 LLM 요약 주입(claude-mem), 스킬·메모리 자동 작성 루프(hermes).
- 방법 없는 수치(OMC "30-50% token savings", ECC "Haiku 90% of Sonnet", CEK "99%").

## 확인할 주장
- compaction 뒤 불린 스킬 본문이 20,000자에서 잘린다(superpowers #2481; audit 53 에서 update-config 가 정확히 20,000자로 잘린 것과 맞는다).
- 스킬 목록에 description 첫 문장만 보인다(gstack; 이 세션 목록에는 여러 문장이 보여 의심스럽다).
- 플러그인 `rules/` 는 실리지 않는다(ECC README `:300` 은 우리 전제와 같고, context-engineering-kit 은 반대로 주장).
- 훅 출력 10,000자 절벽, MCP instructions 4,096자(claude-mem 실측 2.1.319).
