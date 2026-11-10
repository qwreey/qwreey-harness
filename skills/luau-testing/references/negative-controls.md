# negative-controls — 테스트가 실제로 무언가를 잡는지 확인하기

## 이 파일이 답하는 질문
- Q1 "0 failed" 가 나왔다. 러너가 케이스를 정말 돌렸나?
- Q2 스펙 파일을 만들었는데 엔트리에 등록을 안 하면?
- Q3 테스트 스위트가 버그를 잡는다는 증거는? (돌연변이)
- Q4 차등 시험·퍼즈는 어떻게 짜나? 퍼저 자체는 어떻게 믿나?
- Q5 무작위 시드는 어떻게 다루나?

## 목차
- §1 러너의 음성 대조군
- §2 등록 누락 검사
- §3 돌연변이 검사
- §4 차등 시험과 퍼즈
- §5 시드와 결정성

타입 검사 쪽 음성 대조군(진단 0건을 믿기)은 luau-verify 스킬 `negative-controls.md` 가 다룬다. 이 파일은 **실행 테스트** 쪽이다.

---

## §1 러너의 음성 대조군
status: verified · last-confirmed: luau 0.742 (0.734 동일, `-O2` 같음) · 근거: `snippets/test-mini-runner.luau`(`--@run-opt=2`), `snippets/opt-cli-level-o1.luau`

- "0 failed" 는 러너가 케이스를 하나도 돌리지 않았을 때도 나온다. 러너 자체를 시험하려면 **일부러 실패하는 케이스 하나**를 두고 "실패 1건을 셌다"와 그 메시지를 단언한다.
- 게이트 수준에서는 "반드시 실패해야 하는 실행"을 하나 둔다. 이 저장소 하네스의 `--@run-with … => fail` 이 그것이다(`opt-cli-level-o1.luau` 는 `-O2` 에서 반드시 실패해야 한다).
- 실패를 rc 로 내는지 확인한다. 실패를 `print` 만 하고 rc=0 으로 끝나는 러너는 게이트가 통과시킨다. 실패가 있으면 마지막에 `error("spec failures", 0)` 로 끝낸다.

## §2 등록 누락 검사
status: described · 근거: `table-sim/<비공개>`, `moonwave-luau/tests/run.luau:12-14`

- 스펙 파일을 만들고 엔트리의 목록에 넣지 않으면 조용히 돌지 않는다. table-sim 게이트는 `tests/core/*.spec.luau` 마다 `tests/run.luau` 에 그 경로 문자열이 있는지 grep 하고 없으면 실패한다.
- require 경로를 문자열 리터럴로 쓰면 이 grep 이 가능해진다(동적 경로는 require-by-string 도 못 푼다).

## §3 돌연변이 검사
status: verified (이 저장소) / described (원천) · 근거: `snippets/test-blame-filename-only.luau`, `stl-luau/.claude/conventions.md:138,159`, `stl-luau/.claude/tools/mutate.sh`, 후보 S-118·M-18

- 테스트가 버그를 잡는다는 증거는 **일부러 깨뜨렸을 때 실패하는 것**이다. raise 자리의 level 을 바꾸거나(`2 → 1`), 비교 연산자를 뒤집거나, 경계 조건을 하나 바꾼 사본에서 스위트를 돌린다. 통과하면(생존) 그 자리는 테스트 공백이다.
- `test-blame-filename-only.luau` 가 작은 예다: `error(msg, 1)` 돌연변이는 파일 이름 단언을 통과하고 줄 단언에서만 걸린다.
- 돌연변이는 **작업 트리가 아니라 사본**에서 하나씩 돈다. 연결 구조를 건드리는 돌연변이는 순환을 만들어 메모리를 다 쓸 수 있으므로 `ulimit -v`·`timeout` 안에서 돌리고, 시간 초과·자원 초과(124, 134, 137, 143)도 "잡힘"으로 친다(stl-luau 기록, described). 절차의 일반형은 luau-verify 스킬 `negative-controls.md` §5.

## §4 차등 시험과 퍼즈
status: described · 근거: `quad/.claude/audit/README.md:82,88-101`, `moonwave-luau/.claude/audit/mrow-spike/README.md:18-20,72-90,201-203`, `stl-luau/.claude/conventions.md:157`, 후보 Q-124·M-18

- **차등 시험**: 작은 참조 모델(규칙 10~20여 개짜리 단순 구현, 또는 레거시 구현)과 실구현을 같은 입력열로 돌려 결과를 비교한다. 이분 탐색 ↔ 선형 탐색, 힙 ↔ 정렬, 집합 연산 ↔ 해시 집합처럼 "느리지만 뻔한" 짝을 쓴다.
- **입력 공간 나누기**: 축(axes) 목록으로 입력 생성을 나누면 어떤 축에서 갈렸는지 바로 보인다.
- **퍼저부터 검증**: 결함 주입 변이(`mut-*`)를 넣은 구현에서 퍼저가 실제로 차이를 찾는지 먼저 확인한다. 원천 하나는 비교기 변이 10/10 을 잡은 뒤에야 퍼즈 결과를 믿었다.
- **축소**: 실패하면 입력을 줄여 최소 재현을 만들고 고정 테스트로 옮긴다.
- 재작성 검증 3단(원천 실례): 레거시와의 차등 비교(픽스처 103/103) → 고정 시드 퍼즈 → 비교기 변이 자가검사.
- 무거운 퍼즈는 OOM 희생 순위를 올려(`choom -n 1000`) 메모리 상한 안에서 돌린다. 반복 수를 몰래 줄여 "통과"로 보고하지 않는다(table-sim `.claude/conventions.md:92-95`, described).

## §5 시드와 결정성
status: described · 근거: `VideoSync/CLAUDE.md:103-105`, `rbvm/.claude/review/2026-10-05-code-review.md:299,420-428`, 후보 O-05·M-16·R-29

- 퍼즈·무작위 시험은 **시드를 고정**하고 실패 메시지에 시드를 찍는다. 재현은 그 시드로 한다.
- 한 시드에서 정확값을 단언하지 않는다. 성질을 단언하고 여러 시드로 돌린다(`assertions.md` §6).
- 해시 테이블 순회 순서(`for k in t`)와 `table.sort` 의 같은 키 순서는 약속되지 않는다(정렬은 안정 정렬이 아님). 같은 입력·같은 삽입 순서에서 같게 나오는 관찰(M-16)은 있지만 계약이 아니다. 출력 비교는 정렬해서 한다.
