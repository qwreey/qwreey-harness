# D-05. 툴체인 버전 핀 (luau 0.734 / 0.742, luau-lsp 1.69.0 / 1.70.1)

> 작성 2026-11-10. 실험 `/tmp/cd-exp/stl`(stl 현재 사본), `/tmp/cd-exp/stl-old`(`git archive 2bbdc93~1`, 0.742 승격 직전), `/tmp/cd-exp/quad`(quad-base/types/error 사본).

## 1. 각 프로젝트의 입장

| 프로젝트 | luau | luau-lsp | 핀 이유 | 위치 |
|---|---|---|---|---|
| stl-luau | **0.742** | **1.70.1** | 실행기·검사기가 같은 배포판, 배터리 기대 건수 재현. 0.734 는 병렬 검사 힙 손상(#3020) | `stl-luau/mise.toml:10-23` |
| quad | 0.734 | **1.70.1** | "스펙 49개가 이 버전으로 돈다, typing-limits 실측이 빌드별" | `quad/mise.toml:12-15` |
| moonwave | 0.734 | 1.69.0 | stl 구성을 따름(stl 이 올리기 전 복제) | `moonwave-luau/mise.toml:3-6,19-20` |
| table-sim | 0.734 | 1.69.0 | "형제와 같은 값, 형제가 올릴 때 같이"; lsp 는 typedefs 정의 파일 버전과 맞춤 | `table-sim/mise.toml:3-5,14-16` |
| devplorer | 0.734 | 1.69.0 | 같은 이유 | `devplorer/mise.toml:3,9-11` |
| tbox | 0.734 | 1.69.0 | lsp 는 typedefs/roblox 와 맞춤 | `tbox/mise.toml:13,20-21` |
| rbvm | 핀 없음(mise.toml 없음) | check.sh 가 1.69.0 기준 | 골격을 만들지 말라는 보류 결정 | `rbvm/CLAUDE.md:10-12`, `.claude/tools/check.sh:12` |

- 낡은 서술이 둘 있다.
  - stl `mise.toml:18-19` "quad 는 luau 를 고정하지 않는데"는 거짓이다. quad 는 2026-09-07 부터 0.734 를 핀했다.
  - table-sim `mise.toml:3-5` "형제(quad·tbox·stl-luau)와 같은 값"도 거짓이다. stl 은 0.742/1.70.1, quad 는 lsp 1.70.1 이다.

## 2. 실제 근거

### 2-1. 0.734 병렬 분석 힙 손상 (#3020)
- [기록] stl 커밋 `2bbdc93`(2026-10-14) 메시지에 이렇게 적혀 있다.
  - `Frontend.cpp:2194 iceHandler->moduleName` 에 작업 스레드들이 동시에 대입해 `corrupted size vs. prev_size` 가 났다.
  - ASan(double-free)·TSan 으로 짚었다.
  - "재현 자리에서 기본 3/30 → `-j1` 0/30" 이었고, 0.742 에서 고쳐졌다.
- [실행, 이번 세션 — **재현 실패**] 4코어 컨테이너에서 0.734 `luau-analyze` 로 다음을 돌렸다.
  - stl 현재 사본 40회, 0.742 승격 직전 스냅숏 60회, 같은 스냅숏 `-j16` 80회, quad 코퍼스 30회.
  - 비정상 종료는 **0건**이었다.
  - 원 재현은 특정 파일("작은 모듈과 배럴을 같이 require 하는 파일")이었고 그 파일은 지금 트리에 없다.
  - **결론: 확률적 결함이라 이 환경·코퍼스에선 드러나지 않았다. 근거 등급은 [기록](ASan/TSan + 상류 이슈)이다.**
  - 0.734 를 쓰는 저장소는 게이트가 "비정상 종료 = 실패"로 판정하는지 확인하면 된다. stl `check.sh:29` 이 그 모양이다.

### 2-2. 버전을 바꾸면 기준선이 바뀐다 [실행]

| 코퍼스 | 0.734 `luau-analyze` | 0.742 `luau-analyze` | lsp 1.69.0 | lsp 1.70.1 |
|---|---|---|---|---|
| stl 현재(0.742 기준선 0건) | **TypeError 30건**(Deque 트레이트 등) | 0건 | **TypeError 308건**(타입 함수 API `is`/`returns` 누락 — 번들 Luau 가 낡음) | TypeError 3건 + LocalShadow 1 |
| quad 엔진 무관 그룹 | 8건 | 8건(같은 줄 집합 — 둘 다 `luau_packages` 누락 노이즈) | — | — |

- stl 은 0.742 전용 동작에 이미 기대고 있다. 0.734 로 내려가면 게이트가 깨진다.
- quad 엔진 무관 코퍼스는 0.734 → 0.742 에서 **진단 차이가 0** 이다. 올려도 무해할 가능성이 크다.
  - 단서가 있다. `luau_packages` 를 relink 하지 않은 사본이라 패키지 의존 줄은 비교 밖이다.
- **luau-lsp 는 자기 번들 Luau 를 쓴다.** CLI 핀과 별개로 움직이고, 1.69↔1.70 사이 차이가 크다.
  - 그래서 stl 은 1.69.0 의 "거짓 경보 20건" 때문에 1.70.1 로 올렸다(커밋 `3b3d281`).
- table-sim·devplorer·tbox 의 lsp 1.69.0 핀은 **Roblox `globalTypes.d.luau` 버전과 짝**이다(각 mise.toml 주석). lsp 만 따로 올릴 수 없다. [기록]

## 3. 합의안

### 안 A. 공통 기준 핀 하나 + "같이 올린다" 절차
- 공통 기준은 `luau 0.742`, `luau-lsp 1.70.1`, `stylua 2.5.2` 다. 정본은 스캐폴딩 스킬(또는 luau-kb `toolchain-pins.md`) 한 곳에 둔다.
- 올리는 절차는 "음성 대조군 배터리 수치가 바뀌는지 확인 → 바뀐 진단은 고치거나 기록"이다(stl `mise.toml:14-15` 원칙).
- Roblox typedefs 를 쓰는 저장소(table-sim, devplorer, tbox)는 lsp 를 typedefs 와 함께 올린다.

| 프로젝트 | 변경량 |
|---|---|
| stl | 0 |
| quad | luau 핀 1줄. 엔진 무관 그룹 진단 차이 0(이번 측정), 패키지 포함 전체는 test.sh 로 확인 필요 |
| moonwave | luau·lsp 2줄 + 배터리 재확인 |
| table-sim, devplorer, tbox | luau 1줄(즉시 가능) + lsp 는 typedefs 갱신과 묶어 별도 |
| rbvm | 핀 자체가 보류 결정(사용자) — 0 |

### 안 B. 버전 의존 규칙 — 핀은 저장소 자유, 대신 "핀 버전 명시 의무"
- 각 저장소는 자기 핀을 유지한다.
- 규칙은 둘이다. (1) **"실측 수치·결함 서술에는 그 버전을 같이 적는다"**. (2) 0.734 를 쓰는 저장소는 `luau-analyze` 비정상 종료를 실패로 판정한다.
- 공통 스킬의 결함 표는 버전 열(`0.734 / 0.742 / lsp 1.70.1`)을 가진다.

## 4. 추천: 안 B 를 공통 규칙으로, 안 A 를 권고 목표로

- 공통 rules 에는 안 B 의 두 줄만 둔다. 핀 값은 프로젝트 소유로 둔다.
  - 이유: 핀 값을 사용자 레벨 rules 에 적으면 저장소 7곳 중 5곳에서 즉시 거짓이 된다.
- quad·moonwave·table-sim·devplorer·tbox 를 0.742 로 올리는 일은 프로젝트별 할 일로 제안한다.
  - quad 는 이번 측정으로 위험이 낮다고 확인됐다.
  - 이 일은 각 세션의 몫이다. 이 저장소들은 다른 세션이 작업 중이라 여기서 바꾸지 않는다.

## 5. 사용자 확인 질문

luau 핀을 전 저장소 0.742(luau-lsp 는 typedefs 와 함께 따로)로 맞추는 것을 목표로 두고 공통 규칙에는 "수치에 버전을 적는다"만 넣을까요, 아니면 지금처럼 저장소마다 자유롭게 두고 동기화 목표도 두지 않을까요?
