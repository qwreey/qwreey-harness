# D-04 type function — 결정 (2026-11-10)

원문: `claude-doctor .claude/base/decisions/D-04-type-functions.md` 끝의 "사용자 결정" 절. 이 파일은 요약이다.

## 맥락
quad 는 '진단 전용'(결과 타입 합성 금지), stl 페이퍼는 '쓰지 않는다', stl 규약은 '주의해서, 시제품으로 재고 사용자에게', tbox 는 핵심 API(`Static`/`Merge`/`Union`/`Tuple`)에 쓴다.

## 결정
- 기본 금지가 아니고 '진단 전용' 구분도 쓰지 않는다(경계가 애매하다. strip-nil 은 결과를 합성하지만 type function 없이는 불가능하다).
- 판단 기준은 **부작용이 이득보다 큰가, 아니면 이것 없이는 표현할 수 없는가**다. 사안별로 판단한다.
- 부작용이 큰 쪽이면 스파이크로 재고 사용자 승인을 받는다.
- 이미 운영 중인 합성(tbox, quad 3.4.0)은 그 저장소의 승인된 결정이다.

## 반영한 곳
- `skills/luau-types/references/type-functions.md` §0(정책), §1(판단 절차), §2(대안이 없는 패턴), §3(체크리스트)
- `skills/luau-types/references/type-functions-limits.md`(제약·부작용, 버전 열)

## 되돌릴 조건
type function 의 직렬화·프라이밍·too complex 제약이 상류에서 크게 풀리면 §1 의 저울을 다시 잰다.
