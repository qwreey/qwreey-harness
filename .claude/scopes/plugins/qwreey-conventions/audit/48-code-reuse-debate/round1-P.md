# 48. code-reuse 문구 토론 1회차, P 입장(짧고 정확하게)

> Snapshot 2026-11-12. claude-doctor 5ce4031 의 `.claude/scopes/plugins/qwreey-conventions/archive/research/drafts/code-quality-conventions/`(README, rules/code-reuse.md, skills/code-reuse/SKILL.md, hook-design.md, fp-strategy.md)와 coderag .claude/audit/47-coderag-code-quality 을 읽고 쓴 1회차 의견. 읽기 전용, Q 입장 문서는 읽지 않았다. 사용자 결정(이름, 사본 줄 옮김, 패키지 경계 사본 안내, 타입-목록은 어긋날 때만, 켜는 관문, `@copy-of: <path>[#NAME]` 통일)은 다시 열지 않는다. 토큰은 `0.4×ASCII + 1.6×한글 + 1.5×그 밖` 어림, rule 은 frontmatter 를 뺀 본문만 센다(`rules_inject.py` 가 본문만 싣는다).

## 결론
- rule 본문을 **약 1,130 → 약 620 토큰(30줄 17항목 → 17줄 8항목)** 으로 줄이자. 늘 실리는 rule 에는 "새로 쓸 때 할 일" 과 "하지 말 것" 만 두고, 판별 표·라이브러리 기준·단순화 요령·생태계 팩 규칙은 스킬로 옮긴다.
- 문구가 넓어서 **해로운 리팩터링**을 부를 자리가 다섯 군데 있다: (1) 정책 값 시험이 게임 코드에도 걸림, (2) "ecosystem 목록은 pack 으로" 가 Roblox 저장소에서는 거의 모든 목록에 걸리고 다른 저장소 쓰기를 부름, (3) "search the repo ... and extend it" 이 import 경계를 말하지 않음, (4) "No reason, use the library" 가 기존 직접 구현을 갈아엎거나 의존성을 몰래 더하라는 말로 읽힘, (5) 긴 함수를 표로 쪼개라는 줄이 손댄 파일 전체 리팩터링을 부름.
- 알림 문구는 모두 짧게, 그리고 "Load the skill for the steps" 를 매번 붙이지 말자(알림마다 스킬 약 1k 토큰을 읽게 된다). 사용자 결정 때문에 **새 문구 하나(Luau 타입-목록 어긋남)가 빠져 있고**, `Canonical copy:` 를 말하는 곳 셋이 결정과 어긋난다.

## 1. rule 한 줄씩

| 줄(초안 원문 앞부분) | 판정 | 이유 |
|---|---|---|
| `# Code reuse: values, duplicates, libraries` | 고쳐 씀: `# Code reuse` | 부제는 행동을 바꾸지 않는다 |
| `> A repo's own rules win. Pairs with the PostToolUse hook `reuse-check`, which only informs.` | 앞 문장은 마지막 줄로, 뒤 문장 삭제 | info 수준의 처리법은 q 플러그인 주입문이 이미 말한다. comments rule 과 같은 자리(끝)에 둔다 |
| `Test: could two projects reasonably want a different value, and is it a judgment about the target repo rather than about the program's correctness? Then it is policy.` | 고쳐 씀(범위 좁힘) | "target repo" 는 다른 저장소를 다루는 도구 이야기다. 게임 저장소(동료들이 쓰는 대부분)에서 이 시험을 돌리면 밸런스 상수·UI 크기까지 "정책" 으로 보여 설정 파일을 새로 만들게 된다. 범위를 "다른 저장소·프로젝트를 상대로 도는 코드(도구, 플러그인, 라이브러리)" 로 못 박는다 |
| `Policy (folder and extension lists, ...) lives in config, a data table or a pack; code keeps only a DEFAULT_* fallback that config overrides.` | 위 줄과 합침 | 시험과 처방이 한 문장이면 된다. "a pack" 은 아래 이유로 스킬로 |
| `Values fixed by a format, a spec, an outside tool or correctness (...) stay const.` | 합침, 괄호 예시는 스킬 표로 | 스킬의 정책/불변식 표가 같은 예를 더 자세히 갖고 있다 |
| `A list that names one ecosystem (Roblox, Wally, pesde) belongs to that ecosystem's pack, not to the core.` | 스킬로 | coderag·하네스처럼 "중립 core + 팩" 구조에서만 뜻이 있다. Roblox 게임 저장소에서는 거의 모든 목록이 Roblox 이름이고 "pack" 이 없다. 팩은 대개 다른 저장소(luau-kb, claude-doctor `packs/`)라 이 줄이 형제 저장소 쓰기를 부른다 |
| `Use the DEFAULT_ prefix only when an override exists; readers take the prefix as that promise.` | 짧게 고쳐 씀 | 확인할 수 있는 한 줄이라 남긴다 |
| `Before writing a walker, frontmatter or TOML reader, hash, glob, truncation, token estimate or date helper, search the repo for one and extend it. Copies drift apart silently, ...` | 고쳐 씀 | 예 8개는 coderag 냄새, 5개면 일반화된다. "search the repo" 는 **import 할 수 없는 곳의 구현을 끌어 쓰게** 한다(따로 설치되는 플러그인끼리 공용 모듈을 만들면 설치 뒤 깨진다). "이 패키지가 import 할 수 있는 것" 으로 좁힌다. 이유 문장은 한 줄로 남긴다(agent-docs 허용) |
| `A vocabulary (status names, folder kinds, level names) is defined once and referenced everywhere.` | 위 줄과 합침 | 같은 지시(찾아서 쓰라)의 대상이 함수냐 목록이냐의 차이뿐 |
| `When a copy is unavoidable (...), mark it @copy-of: <path>#<NAME> and keep a test that compares it with the source.` | 고쳐 씀 | 결정대로 `[#NAME]`(파일 사본은 이름 없이). code-structure 에서 옮겨 오는 파일 사본 줄을 여기서 받는다. **"import 경계를 넘는 import 로 바꾸지 말라"** 를 더한다: 사본을 보면 모델이 먼저 합치려 든다 |
| `A runtime list that mirrors a type union: derive ... (TS typeof LIST[number]); where it cannot (Luau), keep them next to each other.` | TS 만 남기고 Luau 절 삭제 | 결정은 "어긋날 때만". "keep them next to each other" 는 table-sim `<비공개>` 처럼 타입을 모아 둔 구조를 흩뜨리는 이동을 부른다. 어긋남은 훅이 알린다 |
| `Prefer the library when the format is correctness-critical ... or when your version would need its own test suite to be trusted.` | 스킬로 | 뒷 조건은 거의 모든 파서에 맞아 "늘 라이브러리" 로 읽힌다. 판단 기준은 스킬 4단계가 이미 갖고 있다 |
| `Hand-written is right when a measured size or startup budget rules the library out, ...` | 스킬로 | 위와 짝 |
| `Either way, put one line at the top ...: why not <library>: <reason>. No reason, use the library.` | 고쳐 씀 | 표시 줄은 남긴다(나중 존재 검사의 고리). **"No reason, use the library" 는 삭제**: 기존 모듈에 이 줄이 없으면 갈아엎으라는 말로 읽히고, 의존성 추가는 사용자 판단이다(하네스 훅은 stdlib 만 쓰고, Wally·npm 의존은 팀 전체에 닿는다) |
| `Claims about cost are measured: binary size delta, cold build time, dependency count.` | 위 줄과 합침 | "의존성은 측정한 비용과 함께 제안" 한 문장으로 |
| `String branches on one variable: see code-structure (Data).` | 삭제 | 같은 paths 라 code-structure 가 같은 문맥에 이미 실려 있다. 가리키기만 하는 줄은 비용만 든다 |
| `A long function that chains independent steps becomes step functions run from a table. A lexer, ... may stay long; ...` | 삭제(원하면 code-structure 로) | 재사용 주제가 아니고, 검사도 없고(H6 그림자), "chains independent steps" 는 판정이 흐리다. 손댄 긴 함수를 통째로 쪼개는 큰 diff 를 부른다 |
| `An arm that maps each value to itself is a membership test; replace the chain with a set lookup.` | 스킬로 | 맞는 말이지만 드물다(`tool_of` 하나). 모든 편집 문맥에 실을 값이 아니다 |
| `Marker syntax, repo settings and what to do with a hook notice: load the skill. Fix only what you added; old duplicates ... not cleaned up unprompted.` | 남김, 범위를 rule 전체로 | "추가한 것만" 은 rule 전체(정책 값, 라이브러리)에 걸려야 한다. 지금은 중복에만 붙어 있어 기존 const 를 설정으로 옮기는 일이 막히지 않는다 |

code-structure 쪽 diff(`Copies, of files or of values, and how they are marked: see code-reuse.`)는 좋다. 다만 같은 paths 라 이것도 가리키기만 하는 줄이니 **그냥 지우는 편**을 권한다(약 20 토큰).

## 2. 스킬(짧게)
- "When a hook notice arrives" 1단계 `If neither place is the right home, move it to one module both import.`: 자기가 추가하지 않은 정의를 옮기는 일이다. "같은 패키지 안에서만, 그리고 옮기면 보고에 한 줄" 로 묶는다.
- 2단계 `add or extend a test that compares the two`: 시험이 없는 저장소(Roblox 게임 대부분)에서 시험 틀을 새로 세우게 한다. `in the repo's existing tests; if it has none, the mark is enough (the hook compares string sets)` 로. 다른 저장소의 사본은 그 기계에 형제가 없으면 실패하는 시험이 되므로 표시만(훅 C1 이 있을 때 대조).
- 3단계 `move it to the repo's config ... An ecosystem list goes to that ecosystem's pack.`: 설정을 읽는 코드가 이미 있을 때만 옮기고, 없으면 `const` 로 두고 보고에 제안. 팩이 다른 저장소면 제안만(q:workspace 규칙).
- 표시 표: `@copy-of: <path>#<NAME>` → `@copy-of: <path>[#NAME]`, "Whole-file copies keep the header line `Canonical copy: <path>`" 줄 삭제, 파일 사본은 `@structure-exempt` 와 같게 "처음 10줄 안". `tools/tests/test-vendored-copies.py` 를 새 표시로 옮기는 것이 설치 순서 2단계에 들어가야 한다.
- 받아 올 것: rule 에서 뺀 생태계 팩 줄, 라이브러리 기준 두 줄, 항등 갈래 줄, Luau 타입-목록(어긋나면 맞추라).
- 지울 것: `Heavy parsers belong in a separate process or provider when the core has a size budget` 는 coderag 구조 이야기라 일반 저장소에서는 프로세스를 새로 세우라는 말이 된다.
- "Library or hand-written" 2단계에 `Adding the dependency is the user's decision; give them the numbers.` 를 더한다.

## 3. 알림 문구(hook-design §6)

공통: 첫 알림 꼬리 `See the code-reuse rule (rules/code-reuse.md in the plugin).` 삭제(그 파일을 편집할 때 rule 은 이미 실려 있다). 끝의 `Load the qwreey-conventions:code-reuse skill for the steps.` 는 `Unsure: qwreey-conventions:code-reuse skill.` 로: 알림 자체가 처방을 담고 있으니 스킬은 애매할 때만.

- N1(같은 패키지): `per-project value, move it to config` 갈래 삭제(편집 하나에 설정 체계를 새로 만들게 한다, 스킬 3단계가 가진다).
  `{rel}:{ln}: string set repeats {name} at {orel}:{oln} ({k}/{n} shared: {shown}). Same knowledge: reference {name} instead. Only alike: put \`{c} @dup-ok: <reason>\` above it. Unsure: qwreey-conventions:code-reuse skill.`
- N2(패키지 경계): 결정대로 사본+시험, 그리고 합치지 말라는 말을 넣는다.
  `{rel}:{ln}: string set repeats {name} at {orel}:{oln} in {opkg}, which this package cannot import ({k}/{n} shared: {shown}). Same knowledge: keep it, mark it \`{c} @copy-of: {orel}#{name}\` and compare the two in the repo's tests; do not add a cross-package import. Only alike: \`{c} @dup-ok: <reason>\`.`
- N3(정본 편집): `{rel}:{ln}: {name} has {m} @copy-of copies: {list}. Update them in this change.` "or run the test" 는 흐려서 삭제. 판정 조건에 "원소가 바뀐 때만" 을 더한다(정의 안 주석만 고쳐도 지금 설계로는 울린다).
- N4: `{rel}:{ln}: @copy-of {target} {does not resolve | differs: missing {a}, extra {b}}. Fix the copy or the mark.`
- N5: `{rel}:{ln}: @dup-ok needs a reason ("{text}" is not one). Say why the lists differ, or remove the mark.`
- N6(TS): `{rel}:{ln}: same strings as type {name} at {orel}:{oln}. Derive the type from the list (\`(typeof X)[number]\`).` 같은 패키지일 때만 낸다(다른 패키지면 타입 패키지가 런타임 패키지를 import 하게 되어 순환을 만들 수 있다). 사용자 결정 "어긋날 때만" 이 Luau 질문(README 열린 질문 3)에 대한 답이라 TS 같음 알림은 그대로 둘 수 있지만, 결정을 TS 까지로 읽는다면 N6 은 아래 N7 로 합친다. 이 해석은 확인이 필요하다.
- **N7(빠져 있음, 결정에서 생김)** Luau·TS 타입-목록 어긋남: `{rel}:{ln}: list and type {name} at {orel}:{oln} hold different strings (missing {a}, extra {b}). Make them match, or put \`{c} @dup-ok: <reason>\` above if they differ on purpose.` hook-design §3 Luau 칸("알리지 않는다")과 §5 조건 4, fp-strategy 의 Luau 줄을 함께 고친다.

## 4. 훅 비용과 거짓 긍정
- 첫 판은 **H1 + C1 + C2 만** 넣고 H2·H6 은 코드에서 뺀다. 그림자만 도는 검사도 코드·시험·표지 붙이는 일감(검토자 둘)을 만든다. H6 은 어차피 structure-reminder 몫이라 여기 넣었다 옮기면 두 번 일한다.
- `Canonical copy:` 를 말하는 §5 조건 5, §7 마지막 줄, 스킬 표 아래 줄은 결정에 맞춰 `@copy-of: <path>` 하나로(머리 700바이트 대신 처음 10줄로 `@structure-exempt` 와 맞춤).
- §8 턴 끝 보고는 좋다(모델 비용 0). 머리말을 "기존 문제" 로 바꾸는 것도 동의.
- 거짓 긍정의 가장 큰 부류(바깥 API 어휘, 7개 중 4개)에 대한 차단은 조건 7(다른 패키지는 양쪽 정의일 때만)인데 probe 로 재지 않았다. 77% 는 관문 밑이라 그림자 먼저가 맞고, 그림자 기록에 `vocab` 후보(여러 패키지에 같은 원소가 나오는 묶음)를 따로 세어 두면 켜기 전에 판단할 수 있다.
- 예산(데운 색인 중앙값 60 ms, 상한 400 ms)은 받아들일 만하다. 다만 Write·Edit 마다 돈다는 점에서 conventions-check 와 같은 프로세스 기동을 공유할 수 없는지(렉서를 옮기는 김에) 검토할 만하다. 지금 설계는 두 프로세스다.

## 5. 토큰

| | 줄 | 항목 | 토큰(본문) |
|---|---|---|---|
| 초안 rule | 30 | 17 | 약 1,130 |
| 제안 rule | 17 | 8 | 약 620 |
| 참고: code-structure / comments | - | - | 약 930 / 약 410 |

rule 은 세션(과 서브에이전트)마다 처음 맞는 편집에 한 번 실리므로, 메인과 서브에이전트 둘이면 약 1.5k 토큰을 아낀다. 스킬은 늘지만 알림을 받거나 애매할 때만 읽는다.

## 6. 제안 rule 전문

```markdown
---
description: Code reuse conventions, all toolkits. Policy values vs invariants, one definition per fact, marked copies, library vs hand-written. Details in the qwreey-conventions:code-reuse skill
paths: ["**/*.{luau,lua,ts,tsx,js,jsx,mjs,astro,rs,py,go,kt}"]
---
# Code reuse

## Values
- In code that runs against other repos or projects (tools, plugins, libraries), a value two projects could reasonably want different (folder or extension lists, size limits, stage ladders, tool names) is policy: read it from config, with a `DEFAULT_*` fallback in code. Values fixed by a format, spec, outside tool or correctness stay `const`.
- `DEFAULT_` promises an override; do not use the prefix for a value nothing overrides.

## One definition
- Before writing a helper (parser, walker, hash, glob, date) or a list of names (statuses, kinds, levels), search for one this package can import, and use or extend it. Two copies of one fact drift apart.
- A copy this package cannot import (separately installed package, another repo): keep it, mark it `@copy-of: <path>[#NAME]` and compare it with the source in a test. Do not replace it with an import across the package boundary.
- TS: derive a union type from its list (`(typeof LIST)[number]`) instead of writing the strings twice.

## Libraries
- Hand-writing a parser or algorithm that a well-known library provides: put `why not <library>: <reason>` at the top of the module. Adding a dependency is the user's call; propose it with measured cost (size, build time, dependency count).

## Scope
- Apply this to code you add. Do not refactor existing code for it unprompted; old duplicates in edited files are reported to the user at turn end.
- Markers, repo settings and hook notices: load the `qwreey-conventions:code-reuse` skill. A repo's own rules win.
```
