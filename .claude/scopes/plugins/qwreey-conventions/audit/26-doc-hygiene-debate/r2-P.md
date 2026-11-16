# P 2라운드

## 양보
1. 타이포그래피(→ — · §)는 주석에서도 통과시킨다. 해가 된다는 증거를 내지 못했다. 반대로 소음 증거는 직접 냈다(이 문자가 들어간 커밋 74~89%). sibling 저장소마다 opt-out 을 쓰는 계획은 철회한다(그 저장소들은 읽기 전용이다).
   - 남는 의심은 구분선(─ 11715개)의 토큰 비용 하나다. count_tokens 로 비교해 의미 있는 차이가 나올 때만 다시 제안하고, 그전에는 규칙에 넣지 않는다.
   - 사용자가 요청한 "non-ASCII 위생" 은 셋으로 채운다: invisible/bidi 문자, 이모지, 언어 불일치. 타이포그래피는 검토했으나 해가 보이지 않아 뺐다고 사용자에게 밝힌다.
2. Q 의 invisible/bidi 검사를 받아들인다. 줄 전체를 본다. 해가 문서로 확인된 유일한 non-ASCII 범주다(Trojan Source, CVE-2021-42574).
3. 새 파일의 기본 언어는 Q 안을 받는다: 저장소 설정, 없으면 같은 폴더 형제 파일의 다수 언어, 그것도 없으면 검사하지 않는다. `en` 기본값은 동료(한국어 사용자)가 새로 만든 저장소에서 첫 편집부터 거짓 알림을 낸다.

## 부분 수용과 반박
4. references 를 느슨하게 보는 것은 받는다(날짜·id 통과). 다만 변경 서술("previously", "as of", "지난번")과 정정 배너("사실 정정", "fact fix")는 references 에서도 잡는다. 공식 "Avoid time-sensitive information" 이 겨냥하는 본문 서술이고, Q 도 "`status:` 가 변경 이력으로 자란다" 를 위험으로 인정했다. `status:` 줄은 형식을 고정해서(`status: … · last-confirmed: <version>`) 통과시킨다.
5. 원장 id 는 Q 안(해소되는 경로가 있으면 통과)을 고르되, 경로가 실제로 있는지 stat 으로 확인한다. 해소되지 않으면 맨 id 와 같게 잡는다. 그러면 플러그인으로 설치해 decisions/ 가 따라오지 않는 경우가 저절로 걸린다(추론).
6. 세션당 3회 상한 뒤 침묵하는 안에는 반대한다. 긴 세션 후반의 이력 줄이 모르게 빠진다. 대안:
   - 세션·에이전트 단위로 센다.
   - 처음 3회는 본문을 다 보이고, 그 뒤로는 한 줄 축약만 낸다(약 25토큰, 추정). 예: `<harness-hook name="doc-hygiene" level="info">L12 date, L30 decision phrase in x.md; see rules</harness-hook>`
   - 소음은 줄이고 누락은 0으로 둔다.

## 최종 문안: 1라운드 대비 바뀐 줄
A (model-facing-docs.md)
```
-- Public ids and standard numbers. A ledger id only on a line that also names the ledger file.
+- Public ids and standard numbers. A ledger id only on a line with a path that resolves in this repo.
+## In `skills/**/references/*.md`
+- Dates, ids, and one fixed `status: … · last-confirmed: <version>` line per section pass.
+- Still move out: decision phrases, round numbers, `audit/N §` provenance, change narration, correction banners.
```
A 훅: 대상이 references 면 date/ledger 패턴을 끈다.

B (comments.md)
```
-- Default: plain ASCII. ...
-- No decorative typography ...
--- Language: ... (default `en`).
-- Repo opt-outs ... "allow_chars": ["typography", "emoji"]
+- Never add invisible or direction-control characters (U+00A0, U+200B-U+200F, U+202A-U+202E, U+2060-U+2069, U+FEFF after byte 0): reader and parser see different text. Checked on whole lines, code and docs too.
+- Typographic punctuation and divider lines are fine.
+- Language: follow the file's comment majority; in a new file, the repo's `comment_language`, else sibling files; else no check. Korean is a normal comment language.
+- A public library that wants English-only sets `"comment_language": "en"`; a repo may set `"allow_chars": ["emoji"]`.
```
훅 공통: (세션, 에이전트)당 처음 3회만 본문을 다 보이고, 그 뒤로는 한 줄 축약으로 낸다. 침묵하지 않는다.
