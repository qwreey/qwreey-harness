"""src/pylib/unicode_extra.rs 를 만든다: python str.isprintable(repr 의 escape 판정)과 str.isdigit 가운데 십진이 아닌 숫자. 표준 라이브러리만 쓴다.

실행(저장소 루트에서): python3 -I crates/qwreey-advisor/gen-unicode-extra.py
표는 이 python 의 Unicode 판을 따른다. python 을 올려 판이 바뀌면 다시 만든다(파일 머리에 판이 적힌다).
십진 숫자(isdecimal)는 harness-hook 의 DECIMAL 표가 맡는다. 여기에는 isdigit 이 더 보는 것(위 첨자, 동그라미 숫자 등)만 둔다.
"""
import os
import sys
import unicodedata

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src", "pylib", "unicode_extra.rs")


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
    head = ("// 만든 파일: crates/qwreey-advisor/gen-unicode-extra.py 가 쓴다. 손으로 고치지 않는다.\n"
            "// @structure-exempt: generated data table\n"
            "// python %s, Unicode %s.\n\n" %(sys.version.split()[0], unicodedata.unidata_version))
    text = head + table("NOT_PRINTABLE", "python `str.isprintable()` 이 거짓인 글자(서로게이트 제외). `repr` 이 escape 한다.",
                        ranges(lambda c: not c.isprintable()))
    text += "\n" + table("DIGIT_NOT_DECIMAL", "python `str.isdigit()` 은 참이고 `isdecimal()` 은 거짓인 글자.",
                         ranges(lambda c: c.isdigit() and not c.isdecimal()))
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(text)
    print("wrote", OUT)


if __name__ == "__main__":
    main()
