"""src/py/unicode_tables.rs 를 만든다: python 의 문자 분류(정규식 \\w, \\d)와 IGNORECASE 의 대소문자 짝. 표준 라이브러리만 쓴다.

실행(저장소 루트에서): python3 -I crates/harness-hook/gen-unicode-tables.py
표는 이 python 의 Unicode 판을 따른다. python 을 올려 판이 바뀌면 다시 만든다(파일 머리에 판이 적힌다).
"""
import os
import sys
import unicodedata
from re import _casefix

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src", "py", "unicode_tables.rs")


def ranges(pred):
    """pred 가 참인 코드 포인트의 [(첫, 끝)] (서로게이트 제외)."""
    out = []
    for c in range(0x110000):
        if 0xD800 <= c < 0xE000 or not pred(chr(c)):
            continue
        if out and out[-1][1] == c - 1:
            out[-1][1] = c
        else:
            out.append([c, c])
    return out


def table(name, doc, rows):
    body = "".join("    (0x%04x, 0x%04x),\n" % (a, b) for a, b in rows)
    return "/// %s\npub const %s: &[(u32, u32)] = &[\n%s];\n" % (doc, name, body)


def main():
    # Tables from this python
    word = ranges(lambda ch: ch.isalnum() or ch == "_")
    decimal = ranges(str.isdecimal)
    # unicode::decimal_value 는 범위마다 0 부터 열 개씩이라고 본다
    assert all((b - a + 1) % 10 == 0 and unicodedata.decimal(chr(a)) == 0 for a, b in decimal)
    fixes = sorted(_casefix._EXTRA_CASES.items())
    fix_rows = "".join("    (0x%04x, &[%s]),\n" % (k, ", ".join("0x%04x" % v for v in vs)) for k, vs in fixes)

    # Rust source
    text = (
        "// 만든 파일: crates/harness-hook/gen-unicode-tables.py 가 python %d.%d (Unicode %s)로 만든다. 고치지 말고 다시 만든다.\n"
        "// @structure-exempt: generated data table\n"
        "//! python 문자 분류 표. 쓰는 곳은 [`super::unicode`].\n\n"
        % (sys.version_info[0], sys.version_info[1], unicodedata.unidata_version)
        + table("WORD", "정규식 `\\w`(`str.isalnum()` 또는 `_`)인 코드 포인트 범위.", word)
        + "\n"
        + table("DECIMAL", "정규식 `\\d`(`str.isdecimal()`)인 코드 포인트 범위.", decimal)
        + "\n/// IGNORECASE 에서 소문자가 같지 않아도 같게 보는 짝(`re._casefix._EXTRA_CASES`): 소문자 -> 같게 볼 소문자들.\n"
        + "pub const CASE_FIXES: &[(u32, &[u32])] = &[\n" + fix_rows + "];\n"
    )

    with open(OUT, "w", encoding="utf-8") as f:
        f.write(text)
    print("wrote %s: %d word ranges, %d decimal ranges, %d case fixes" % (OUT, len(word), len(decimal), len(fixes)))


if __name__ == "__main__":
    main()
