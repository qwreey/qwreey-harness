# 출처와 측정 기록 (luau-perf)

시간에 민감한 서술(날짜, 절대 경로, 원천 문서)을 SKILL.md 본문에서 옮겨 둔 곳이다. 2026-11-11 에 옮겼다.

## 원래 SKILL.md 에 있던 줄
- 벤치: `/code/Projects/claude-doctor/packs/luau-kb/bench/*.luau`(19 개), 실행 `bench/run.sh`, 표 `bench/summarize.py`, 결과 `bench/RESULTS.md`·`bench/results/2026-11-10.tsv`.
- 결정적인 주장: `/code/Projects/claude-doctor/packs/luau-kb/snippets/perf-*.luau`(7 개, `--@run`), 결과는 `snippets/RESULTS.md` 의 perf 절.
- 최적화 수준·native 의 CLI 주장: `snippets/opt-*.luau`, `snippets/native-*.luau`(luau-testing·verify 담당), `claude-doctor .claude/scopes/packs/luau-kb/archive/research/drafts/gaps/tools/run_opt.sh`(58 개 검사).
- 원천: stl-luau-doctor `.claude/base/perf-measurements.md`(0.734 `-O1` 중심), 후보표 claude-doctor `.claude/scopes/packs/luau-kb/audit/08`·`claude-doctor .claude/scopes/packs/luau-kb/audit/09`. 각 절에 후보 ID 를 남겼다.

## 버전
- 수치는 luau 0.742 의 `-O1`·`-O2`·`--codegen` 세 모드로 다시 잰 비율이다. 0.734 `-O1` 열은 원천과 조건을 맞춘 대조 열이다.
