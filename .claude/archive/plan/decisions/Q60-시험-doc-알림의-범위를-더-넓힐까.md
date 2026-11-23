---
format: 1
title: 시험 doc 알림의 범위를 더 넓힐까? (#[rstest] 같은 속성, __main__ 이 있는 Python 시험 파일)
description: "시험 doc 알림의 범위를 더 넓힐까? (#[rstest] 같은 속성, __main__ 이 있는 Python 시험 파일) 답 b) 1 만: 흔한 Rust 시험 속성(rstest, test_case, quickcheck)을 더한다"
status: "archived; answered b) 1 만: 흔한 Rust 시험 속성(rstest, test_case, quickcheck)을 더한다"
id: Q60
urgency: later
blocks: 없음
recommended: b
created: 2026-11-23T00:44:59.401Z
answered: 2026-11-23T00:45:43.336Z
answer: b
---

# Q60. 시험 doc 알림의 범위를 더 넓힐까? (#[rstest] 같은 속성, __main__ 이 있는 Python 시험 파일)

## 맥락

Q58 b 로 conventions-check 의 doc 알림이 Rust `#[test]`, `#[<path>::test]` 를 본다(98d3c3a). 남은 둘:

1. `#[rstest]`, `#[test_case(...)]`, `#[quickcheck]` 처럼 마지막 이름이 `test` 가 아닌 시험 속성. 이 저장소에는 없다. 다른 저장소에서 쓰면 그 시험은 알림에서 빠진다.
2. Python `test_*`: 지금은 "공개 함수" 규칙으로만 잡혀서, `if __name__ == "__main__"` 블록이 있는 모듈에서는 빠진다. 이 저장소의 Python 시험 파일 23개가 모두 그 블록을 가져 하나도 잡히지 않는다. Python 시험 메서드 458개 가운데 docstring 은 13개다.
   - 넓히면 이 저장소의 Python 시험을 고칠 때마다 알림이 많이 뜬다(편집이 쓰거나 키운 함수에만 뜨므로 옛 시험은 그대로 두면 조용하다).
   - Python 판은 python 이 물러나면 지울 것들이다(계획 "python 이 물러날 때 걷어낼 것").

## 선택지

- a) 둘 다 지금은 두지 않는다
  이 저장소에 그런 속성이 없고, python 시험은 물러날 쪽이다. 다른 저장소에서 필요하면 그때
- b) 1 만: 흔한 Rust 시험 속성(rstest, test_case, quickcheck)을 더한다
  작고 유지 비용이 거의 없다
- c) 1 과 2 둘 다
  Python 시험도 같은 규약을 따르게. 이 저장소 python 시험 편집마다 알림이 늘어난다

**권장 b) 1 만: 흔한 Rust 시험 속성(rstest, test_case, quickcheck)을 더한다**
1 은 다른 저장소의 Rust 시험에서 빠지는 구멍을 싸게 막고, 2 는 노이즈에 비해 이 저장소에서 얻는 것이 적다

## 답

b
