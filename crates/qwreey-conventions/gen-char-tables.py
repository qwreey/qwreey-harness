"""src/check/char_tables.rs 를 만든다: conventions-check 가 쓰는 python 문자 분류와 기호 대체 표. 표준 라이브러리만 쓴다.

실행(저장소 루트에서): python3 -I crates/qwreey-conventions/gen-char-tables.py
표는 이 python 의 Unicode 판을 따른다. python 을 올려 판이 바뀌면 다시 만든다(파일 머리에 판이 적힌다).

- LETTER_MARK_DIGIT: `unicodedata.category(ch)` 가 L*, M*, Nd 인 글자(odd_chars 가 통과시키는 자연어 글자와 숫자).
- UPPER: `ch.isupper()`(Go 함수 이름이 공개인지).
- SYMBOL_HINTS: symbol_detail 의 대체 가운데 unicodedata.name, NFKC 로 정해지는 것(원 숫자의 "1)", 호환 글자의 ASCII).
  SYMBOL_FIX 표와 이모지, 그 밖의 "plain ASCII or words" 는 코드가 정한다.
"""
import os
import sys
import unicodedata

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src", "check", "char_tables.rs")
EMOJI_RANGES = ((0x1F000, 0x1FAFF), (0x2600, 0x27BF), (0x2B00, 0x2BFF), (0xFE00, 0xFE0F), (0x20E3, 0x20E3))
FULLWIDTH_RANGES = ((0x3000, 0x3000), (0xFF01, 0xFF5E), (0xFFE0, 0xFFE6))


def chars():
    for c in range(0x80, 0x110000):
        if not 0xD800 <= c < 0xE000:
            yield c, chr(c)


def ranges(pred):
    out = []
    for c in range(0x110000):
        if 0xD800 <= c < 0xE000 or not pred(chr(c)):
            continue
        if out and out[-1][1] == c - 1:
            out[-1][1] = c
        else:
            out.append([c, c])
    return out


def hint(ch):
    """conventions-check.py symbol_detail 가 SYMBOL_FIX 에 없는 글자에 주는 대체 가운데 이름과 NFKC 로 정해지는 것."""
    name = unicodedata.name(ch, "")
    nk = unicodedata.normalize("NFKC", ch)
    if name.startswith(("CIRCLED DIGIT", "CIRCLED NUMBER", "DINGBAT")) and nk.isdigit():
        return nk + ")"
    if nk.isascii() and nk != ch:
        return nk
    return None


def can_be_odd(cp, ch):
    """odd_chars 가 거를 수 있는 글자: 이모지, 전각, 자연어 글자와 숫자가 아닌 것."""
    if any(a <= cp <= b for a, b in EMOJI_RANGES + FULLWIDTH_RANGES):
        return True
    cat = unicodedata.category(ch)
    return not (cat[0] in "LM" or cat == "Nd")


def rust_str(s):
    return '"' + "".join(c if 0x20 <= ord(c) < 0x7F and c not in '"\\' else "\\u{%x}" % ord(c) for c in s) + '"'


def table(name, doc, rows):
    body = "".join("    (0x%04x, 0x%04x),\n" % (a, b) for a, b in rows)
    return "/// %s\npub const %s: &[(u32, u32)] = &[\n%s];\n" % (doc, name, body)


def main():
    letters = ranges(lambda ch: unicodedata.category(ch)[0] in "LM" or unicodedata.category(ch) == "Nd")
    upper = ranges(str.isupper)
    hints = [(cp, h) for cp, ch in chars() if can_be_odd(cp, ch) for h in [hint(ch)] if h is not None]
    hint_rows = "".join("    (0x%04x, %s),\n" % (cp, rust_str(h)) for cp, h in hints)
    text = (
        "// 만든 파일: crates/qwreey-conventions/gen-char-tables.py 가 python %d.%d (Unicode %s)로 만든다. 고치지 말고 다시 만든다.\n"
        "// @structure-exempt: generated data table\n"
        "//! conventions-check 의 문자 분류와 기호 대체 표. 쓰는 곳은 [`super::chars`].\n\n"
        % (sys.version_info[0], sys.version_info[1], unicodedata.unidata_version)
        + table("LETTER_MARK_DIGIT", "일반 범주가 L*, M*, Nd 인 코드 포인트 범위.", letters)
        + "\n"
        + table("UPPER", "`str.isupper()` 가 참인 코드 포인트 범위.", upper)
        + "\n/// 기호 대체(이름이 원 숫자면 `1)`, NFKC 가 다른 ASCII 면 그 글): 코드 포인트 -> 대체 글. 코드 포인트 순.\n"
        + "pub const SYMBOL_HINTS: &[(u32, &str)] = &[\n" + hint_rows + "];\n"
    )
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(text)
    print("wrote %s (%d letter ranges, %d upper ranges, %d hints)" % (OUT, len(letters), len(upper), len(hints)))


if __name__ == "__main__":
    main()
