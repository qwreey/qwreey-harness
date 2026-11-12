# 모델별 특성: Claude / GPT(codex) / Gemini(agy)

2026-11-10 초안. 실제 작업 기록과 이번 시범 실행(`trial-2026-11-10.md`)에서 뽑았다. 주장마다 근거 경로를 단다. 기록이 아니라 내 해석이면 **(추측)**이라고 적는다.

근거 수집은 서브에이전트가 했다. 그중 다음 근거는 원문을 직접 열어 맞는 것을 확인했다.
- `SA/2026-10-02-hunt.md:1-25`, `SA/2026-10-14-trait-typing-dx.md:3`, `SA/2026-10-14-src-index.md:7-9`
- table-sim 검토 기록(비공개, 경로 생략)
- `QQ/external-review-entry.md:3-7, 139`, `QA/post-implementation-review-round6.md:20-24`, `QA/…round3.md:163-166`, `QQ/code-quality-review-round15.md:34-50, 586-600`

나머지 줄 번호는 수집 결과를 그대로 옮겼다. 인용하기 전에 한 번 더 연다.

**경로 약어**
- QA = `quad/.claude/archive/post-implementation-review/`
- QQ = `quad/.claude/qa-request/`
- QU = `quad/.claude/audit/`
- QC = `/code/Projects/quad-codex/`
- SA = `stl-luau/.claude/audit/agy/`
- TR = table-sim 의 검토 기록 폴더(비공개, 경로 생략)
- MQ / MS / MT = `/code/.claude/projects/-code-Projects-{quad,stl-luau,table-sim}/memory/`
- SKq / SKs = `{quad,stl-luau}/.claude/skills/delegate-agy/SKILL.md`
- 시범 = `drafts/delegate/trial-2026-11-10.md`

## 한눈에

| | Claude | GPT (codex, gpt-6-luna) | Gemini (agy, gemini-3.8-flash-high) |
|---|---|---|---|
| 잘하는 것 | 지시 이행, 인용 정확도, 실측 판정 | 짧고 형식을 지키는 객관 평가. 인용이 정확했다(시범) | 틀 밖으로 튀어 근본 원인 찾기, 좁은 결함 사냥, 이름의 생태계 충돌 찾기 |
| 자주 틀리는 것 | 같은 틀 안에서만 메운다. 리뷰 말을 결정처럼 받는다 | 저장소 밖 맥락(생태계 관례)을 모른다 | 지어낸 인용, "실측" 표기 오용, Luau·엔진 사실 반대로 말하기, 심각도 과장 |
| 맡길 일 | 판정, 반영, 설계 대화(opus). 감사·거르기(sonnet). 읽기 전용 위치 조사(haiku) | 프롬프트 하나로 완결되는 평가(이름, 작은 코드 조각 위험 검토) | 메커니즘 하나로 좁힌 사냥, 상류 소스 파기, 다른 시선 |
| 맡기지 말 일 | 같은 계열끼리 서로 다른 시선이라 치기 | 저장소를 읽어야 하는 일(지금 worktree 모드가 돌지 않는다) | 전수 감사·리뷰 라운드, 엔진·클라이언트 상태 추론, 소리 판정 |
| 비용·속도 | opus 구현 서브에이전트 단계당 45~56만 토큰 | 이름 질의 2~9k 토큰, 72KB 코드 질의 26.6k 토큰·38초(시범) | 쿼터 넉넉한 편(사용자), 과제당 4~8분, 보고서가 길다 |

## 1. Claude

### Claude 내부 모델 사용 규칙 (사용자 결정, 2026-11-10)

- **haiku**: 읽기 전용 위치 조사에만 쓴다. 예: 어디서 정의되나, 무엇이 무엇을 부르나, 파일 찾기.
- **sonnet 이상**: 쓰기가 있거나 위험이 있는 일. 파일 수정, git, 설치, 판정이 결과에 들어가는 일이 여기에 든다.
- 기록상 haiku 쓰임과 특성 관찰은 **없다**. 규약 한 줄뿐이다(`quad/.claude/conventions.md:30-32` "작은 단발 위임은 haiku/sonnet 기준"). 이 규칙은 위 사용자 결정이 정본이다.

### 계열 전체
- **편향을 공유한다.** sonnet과 opus는 같은 베이스에서 증류되어 어휘와 선택 편향이 같다. "외부자·내부자 시선"을 지정해도 이 편향은 좁혀지지 않는다(SKq:10, SKs:13-17). 그래서 sonnet과 opus를 두 개의 다른 시선으로 세지 않는다.
- **강점**: 할루시네이션 통제가 높아 지시를 잘 따른다(사용자 평가, SKs:38-39).
- **약점: 일차원적이다.** 버그를 찾으면 고치고, 고친 것이 낳은 문제를 다시 고친다(같은 곳). 에러 규약 리뷰 여덟 라운드가 2→5→3→2→3→3→1건으로, 같은 틀 안의 빈틈만 메웠다(SKs:42-44).
- **리뷰를 과신한 사고**: 리뷰·탐사 입력을 사용자 결정처럼 반영했다가 나중에 걷어냈다(QQ/round14:3-5, QQ/round16:5).

### opus
- **강점**
  - 판정과 정독에 강하다. 회신 단계 시범 여섯 문항을 전부 맞혔고, fable이 놓친 둘을 잡았다. 그래서 메인을 opus로 바꿨다(`quad/.claude/conventions.md:36-40`).
  - 단일 맥락 정독은 파일 안 결함에 강하다(QQ/round15:589-595).
  - Gemini 주장의 판정자로 썼다. 주장마다 HEAD를 열고 프로브로 재현했다(QU/round14-reflect-review-2026-10-06/agy-triage.md:4).
  - Gemini의 HKT 오판을 바로잡았다(SA/2026-10-14-trait-typing-dx.md:3).
- **약점**
  - 혼자 정독하면 "관례로 여겨 넘김"으로 10건을 놓쳤다. 교차 세기와 DX 근거는 "여럿 + 판정자" 구성이 더 강했다(QQ/round15:597-600).
  - 지시대로 임시 사본을 지워서 메인이 프로브를 다시 짰다(MS/subagent-keep-artifacts.md:13). 산출물은 "남겨라"로 지시한다.
- **비용**: 구현 서브에이전트가 단계마다 약 45~56만 토큰이었고, 사용자가 효율을 요구했다(MQ/feedback-token-efficiency-2026-10-21.md:11-13).

### sonnet
- **잘 맞는 일**
  - 감사자(`quad-doc-auditor` 고정)
  - flash 결과 거르기. REAL/PARTLY/WRONG으로 나눴다(TR/<비공개>)
  - 루프 끝의 회귀 검토(TR/<비공개>)
  - 이름 검토의 한 시선
- **약점**
  - 사용자: *"sonnet 실수가 너무 많아서 감사 루프가 길어져서 오히려 비용이 높아지더라"*. 반영과 설계 대화에는 쓰지 않는다(MQ/feedback-model-choice-for-reflection.md:15-18).
  - 결정 없이 새 개념을 제안하는 일이 반복됐다(같은 파일:18).
  - 일괄 치환으로 깨진 링크 43곳을 만들었다(`quad/.claude/session/2026-09-21-03…:49`).

### fable
- quad 메인에서는 opus로 대체됐다(위).
- table-sim 사용자 지시: *"fable 만 쓰지 말고, 또 속도를 위해 항상 opus 를 쓰지도 마."* 메인은 이를 "훑기는 sonnet, 설계 판단은 opus, 다른 시선은 fable"로 해석했다(MT/subagent-model-mix.md:13-15).

### 프롬프트 요령
- 산출물(프로브, 사본)은 지우지 말고 경로를 남기라고 쓴다(MS/subagent-keep-artifacts.md:15).
- 앵커링을 재려면 독립 패스를 먼저 시키고, 원장은 그 뒤에 보여 준다(QQ/round15 §6, 558행 부근).
- SendMessage로 이어 보낼 때 본문이 빠진 사고가 있었다(QU/naming-base-2026-10-22/README.md:3). 보낸 길이를 확인한다.

## 2. GPT (codex CLI, gpt-6-luna, effort medium)

쓰인 범위
- quad 이름 검토 8회(QC/*). 첫 위임은 2026-10-20이다(`quad/.claude/session-summary.md:2554`).
- 이번 시범의 코드 질의 1회(시범)
- 코드 리뷰나 감사에 쓴 기록은 **없다**.

### 강점
- **짧고 형식을 지킨다.** 지시한 항목(판정, 최선, 대안, 위험)을 그대로 따르고 "추정" 표기를 쓴다(QC/naming-devui/stdout.txt:46-97). 이름 답은 15~53줄이다. 같은 1021e 과제에서 Gemini 보고서는 244줄, codex는 18줄이었다(`quad-agy/naming-1021e/AGY_REPORT.md`, QC/naming-1021e).
- **다수안에 자주 든다**: `SearchCombo`, `Items`, `AnchorRect`, `ConfirmLabel`, `Follow` 등(QU/naming-devui-2026-10-21{b,c,d,e}/README.md 표).
- **시범에서 인용이 정확했다.** 저장 코드 질의에서 파일:줄과 테스트 이름 둘이 모두 맞았다. 줄 범위는 주석 한 줄을 끼워 넣는 정도로 어긋났다(시범 §3).
- **실패를 정직하게 보고한다.** 셸이 막히자 *"보고서에 근거를 적으면 확인하지 않은 내용을 사실처럼 쓰게 됩니다"*라며 지어내지 않고 멈췄다(시범 §2, `table-sim-codex/runs/20261110-1620-trial-query/report.md`).

### 약점과 실수
- **저장소 밖 생태계 관례를 모른다.** Gemini와 함께 "`asState`는 감싸는 것으로 안 읽힌다"고 했지만, devui와 material의 로컬 `asState`가 바로 그 뜻으로 쓰이고 있어 메인 검증에서 틀렸다(QU/naming-marker-helper-2026-11-06/README.md:12-18). 빈 디렉터리 실행이라 생긴 일이다.
- **혼자 다른 쪽으로 가는 일이 잦았다**: `OnTick`, `VirtualList`, `Modality` 등(각 README 표). 이것을 "틀림"으로 본 메인 메모는 없다. 판정은 다수결이었다.
- **위험 항목이 일반론으로 흐른다(시범).** 위험 3개 중 둘은 "미래에 단계가 중첩 표를 고치면", "미래에 필수 필드가 생기면"처럼 일반적인 가정이었다. 지금 코드의 구체적 결함은 아니다(시범 §3). 표본 하나라 **(추측)** 수준의 관찰이다.

### 맡길 일 / 맡기지 말 일
- **맡길 일**: 프롬프트 하나로 완결되는 객관 평가. 사용자: *"객관 평가엔 luna로 충분"*(MQ/reference-codex-delegation.md:11). 코드 조각을 줄 번호와 함께 넣은 좁은 질문도 된다(시범).
- **맡기지 말 일**
  - 저장소를 직접 읽어야 하는 일. 이 호스트에서는 무권한 uid의 codex 샌드박스(bubblewrap)가 namespace를 못 만들어 셸이 하나도 돌지 않는다(시범 §2). 샌드박스를 끄는 것은 사용자 결정이다.
  - 생태계 관례가 걸린 판정을 맥락 없이 맡기는 일

### 프롬프트 요령
- 영어로 완결되게 쓰고, *"Everything you need is below — do not look for files. Reply in Korean, concisely"*로 지시한다. 피해야 할 Roblox 이름 충돌도 직접 적는다(QC/naming-devui/stdout.txt:15,26).
- 답 형식과 "Mark guesses as 추정"을 명시한다(같은 파일:38-42).
- 코드를 줄 때는 `nl -ba`로 줄 번호를 붙여 넣는다. 그래야 파일:줄로 답한다(시범).
- 생태계 관례(같은 이름이 이미 어디서 무슨 뜻으로 쓰이나)는 메인이 grep해서 프롬프트에 넣는다. asState 사례에서 얻은 교훈이다 **(추측 — 시험 안 함)**.

### 비용과 속도
- **토큰**: 이름 질의 3,040 / 4,083 / 3,798 / 8,580 / 4,142 / 4,036 / 3,853 / 4,223(QC/*/stdout.txt "tokens used"). effort low 첫 시험은 1,953(`quad/.claude/session/2026-10-19-01-decl-3-4-decisions.md:50`).
- **시범**: 72KB 프롬프트로 26,647 토큰, 38초. 셸이 막힌 실패 실행도 20,001 토큰, 32초를 썼다.
- **과금**: ChatGPT Plus 구독(`auth_mode: chatgpt`)이라 쿼터가 작다. 사용량은 사용자가 확인한다. 사용자: "5시간 한도가 안전장치라 써도 됨"(MQ/reference-codex-delegation.md:11).

## 3. Gemini (agy, gemini-3.8-flash-high)

옛 기록(QA/round2·4·5·6)은 사용자가 Gemini 세션에서 받아 온 것이라 버전이 없다. round12는 3.1 Pro다(QA/round12:3).

### 강점
- **틀 밖에서 근본 원인을 짚는다.**
  - quad에서 다패스 검증이 못 찾던 nil 구멍을 대거 찾았다. "전부 사실은 아니었지만 제기한 문제는 진짜"였다(SKq:11).
  - Context 설계, `q.Out` 부재, diff-and-set 논의가 Gemini에서 시작됐다(SKq:12-14).
- **좁은 사냥이 잘 맞았다.**
  - stl-luau `hunt`는 Claude 리뷰 여러 라운드가 지나친 실제 결함 셋을 찾았고, 메인 판정은 "틀림 없음"이었다(SA/2026-10-02-hunt.md:7-23).
  - table-sim holes 한 건은 Claude 검토 8번이 못 본 것이었다(TR/<비공개>).
  - quad round4는 다섯 건이 전부 실존했다(QA/round3:53-62).
- **상류 소스를 판다.** Luau `Subtyping.cpp:830-836`의 *"TODO: These branches are entirely incorrect"*를 찾았고, 메인이 확인해 결함의 뿌리로 연결했다(SA/2026-10-14-src-index.md:7).
- **이름의 생태계 충돌을 찾는다.**
  - Roblox `AbsoluteContentSize`가 반대 뜻이라는 점(QU/naming-devui-2026-10-20/README.md:17)
  - `Memo`가 반응형 memo로 오해된다는 점(QU/naming-base-2026-10-22/README.md:7)
- **토론에서 자기 제안을 철회한다.** round15에서 C·D가 신설 제안을 철회했고, 판정자의 줄 번호 오기도 바로잡았다(QQ/round15:34-44).

### 약점과 자주 하는 실수
- **지어낸 인용**: "원문 그대로"라며 붙인 코드에 실제 파일에 없는 `GetDescendants` 고리가 있었다(TR/<비공개>). 들여쓰기를 바꿔 인용한 일도 있다(SKq:56).
- **"실측" 표기 오용(반복)**: 돌리지 않은 테스트를 "[실측]"으로 적었다(QU/round14-principle-audit/agy-roots-2026-10-02.md:6). 비슷한 일이 agy-name-storebind:5, TR/<비공개>에도 있다.
- **인용 반전과 입력 베끼기**: 문서를 반대로 인용했고, 기준 커밋을 입력 파일에서 옮겨 적었고, 닫힌 문항을 열린 것으로 셌다(agy-roots:6-7). 그래서 머리말에 "기준 커밋 직접 확인"이 생겼고 효과가 있었다(SA/hunt.md:22-23).
- **Luau와 엔진 사실을 반대로 말한다.**
  - nil 키 읽기를 VM 에러로 전제했다. 실제로 에러는 쓰기만 난다(QA/round3:165).
  - 없는 문법 `x is Type`을 제안했다. 사용자: *"없는 문법이고 검색만 해봐도 나오는 부분임"*(QA/round6:22).
  - 파트 속성 복제를 반대로 알고 Replication Storm 결론까지 냈다(TR/<비공개>).
- **심각도 과장과 단정적 어조**: UB를 High 결함으로 올렸지만 "확정된 동작 결함 0"이었다(QU/gemini-core-2026-10-15/README.md:6-12). "치명적", "100%" 같은 말을 쓴다(SKs:137).
- **기각된 것을 다시 낸다**: 반증된 Effect `return nil`, 사용자가 기각한 표면(QQ/round15:37-40), 미리 알린 "위조는 결함 아님"(SA/2026-10-06-trait-review.md:4,16).
- **닿지 않는 경로**: table-sim holes 17건 대부분은 입구가 이미 거르는 값을 캐스트로 core에 넣은 프로브였다(TR/<비공개>). R2는 11건 중 7건이 틀렸다(TR/<비공개>).
- **처방이 성능을 안 본다**: `FromIter` 수정안은 맞았지만 2.1배 느렸다(SA/hunt.md:11-12).
- **지시를 안 지킨다**: "파일을 보지 말라"고 해도 레포를 읽었다(QU/naming-devui-2026-10-20/README.md:3). 이름 과제인데 전체 테스트를 돌렸다(`quad-agy/naming-1021e/.agy/stdout.txt:99`).
- 사용자 총평: 조작 실수가 Anthropic 모델보다 **"훨씬"** 잦다(SKq:16). *"flash는 실수가 훨씬 잦고 agy 하네스가 완고하지 않다"*(`quad/.claude/conventions.md:380`).

### 맡길 일 / 맡기지 말 일
- **맡길 일**
  - 메커니즘 하나로 좁힌 결함 사냥(SKs:54-56)
  - 상류 소스에서 근본 원인 찾기
  - 이름 객관성과 Roblox 충돌 찾기
  - 문서 잔재 대조. round14 반영 확인에서 확정 셋이 모두 CHANGELOG·주석 잔재였다(agy-triage.md:8).
  - 여러 문항을 정책 하나로 묶기(QQ/round14:191)
  - 엔진 없이 재현되는 core 경계값(TR/<비공개>)
- **맡기지 말 일**
  - 전수 감사와 리뷰 라운드. 사용자: *"다른 시선 제공자일 뿐 전체 감사에 쓰는 목적은 아니라서"*. 타입 쌍 전수표를 맡겼더니 결함 0건이었다(MS/agy-is-second-opinion.md:13).
  - 엔진·클라이언트 상태 추론. table-sim R4부터 틀린 지적이 절반을 넘어 루프를 멈췄다(TR/<비공개>).
  - 소리 판정. 두 음 비교 2/6, 440→880을 "낮아짐"으로 답했다. 사용자: *"제미니는 그냥 쓰지 않는거로 해야겠다. 들어가는 토큰 대비 너무 아깝군."*(MT/no-gemini-for-audio.md:13)

### 프롬프트 요령
- **앞선 리뷰의 분류표를 주지 않는다.** 주면 그 분류에 고정된다. 뿌리 여섯 중 셋이 기존 분류를 다시 묶은 것이었다(agy-roots:9, SKs:83-84).
- **잘 된 모양**: 원장(질문·코드)만 준다, 각도는 열어 둔다("갇히지 말 것"), 메커니즘별로 묶게 한다, 결함마다 실행 가능한 프로브를 요구한다(SKs:128-133).
- **결정 이력은 직접 넣는다.** agy는 `CLAUDE.md`를 싣지 않는다(SKq:28,40). `AGENTS.md`와 `GEMINI.md`는 싣는다(`conventions.md` §2).
- **"다시 올리지 말 것" 목록과 "Luau 언어 사실은 실측 뒤 주장"을 준다**(QQ/external-review-entry.md:85-100, 139).
- **입력을 다른 모델과 같게 하려면 empty 모드로 돌린다.** 지시로는 파일 읽기를 막지 못했다(위). **(추측 — agy empty 모드는 아직 시범 전)**

### 비용과 속도
- 사용자: flash 3.8이 300 tok/s 이상이고 pro보다 낫다. *"pro 는 없는것 취급"*(SKq:49).
- **걸린 시간**: quad roots 4분, fresh 8분(agy-roots:3). table-sim 소리 묶음 50분(`table-sim/<비공개>`). 이번 시범은 시범 §4를 본다.
- **쿼터에 관한 사용자 발언**
  - 10-14: *"위클리 83.99% 잔여 … 둘씩 계속 돌려도 될 만큼"*(MS/agy-budget-generous.md:13)
  - 10-20: *"제미니 하나씩 올려줘. 겹치는거 나오면 토큰 아까워서"*(같은 곳)
  - table-sim: *"한번에 뜰 수 있는게 제어되어야해. 토큰 소진이 문제라서 그럼."*(TR/<비공개>)
- 토큰 수 기록은 **못 찾음**(agy는 출력에 토큰을 적지 않는다).

## 4. 세 계열을 함께 쓸 때

- **합의가 곧 정답은 아니다.** codex와 Gemini가 `asState`로 수렴했지만 메인이 반증했다(QU/naming-marker-helper-2026-11-06/README.md:12-18). 판정은 늘 메인의 실측으로 한다.
- **다수결은 동률이 난다.** 6·6·6이 나온 적이 있다(QU/naming-devui-2026-10-21e/README.md:7). 사용자가 다수안을 뒤집기도 했다(10-22).
- **입력을 같게 맞춘다.** codex는 빈 디렉터리, Gemini는 worktree로 돌려 입력이 달랐다(QU/naming-devui-2026-10-20/README.md:3).
- **토큰을 아끼는 판**: sonnet을 빼고 메인(opus)이 세 번째 시선을 맡은 회차가 있다(QU/naming-marker-helper-2026-11-06/README.md:3).
- 형식과 절차는 `skills/debate/SKILL.md`를 본다.
