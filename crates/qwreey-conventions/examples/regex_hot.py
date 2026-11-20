"""regex_hot.rs 의 python 짝: 같은 파일의 주석 본문 전부에 conventions-check 패턴 하나씩 search 를 돌린 합(마이크로초, 중앙값).

실행(저장소 루트에서): python3 -I crates/qwreey-conventions/examples/regex_hot.py <파일> [반복 수]
"""
import importlib.util
import os
import statistics
import sys
import time

HOOKS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "plugins", "qwreey-conventions", "hooks")
sys.path.insert(0, HOOKS)
spec = importlib.util.spec_from_file_location("cc", os.path.join(HOOKS, "conventions-check.py"))
cc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cc)
import conv_lex  # noqa: E402


def main():
    path, runs = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 11
    text = open(path, encoding="utf-8").read()
    rows = conv_lex.lex(text, conv_lex.FAMILY[os.path.splitext(path)[1].lower()])
    segs = [" ".join(conv_lex.comment_body(c) for c in r["c"]) for r in rows if r["c"]]
    pats, pub = cc.compile_patterns(dict(cc.DEFAULTS))
    print("%s: %d comment lines, median of %d runs (us per pass)" % (path, len(segs), runs))
    for name, rx in list(pats.items()) + [("public[%d]" % i, r) for i, r in enumerate(pub)]:
        xs = []
        for _ in range(runs):
            t = time.perf_counter()
            sum(1 for s in segs if rx.search(s))
            xs.append((time.perf_counter() - t) * 1e6)
        print("  %-12s %d" % (name, statistics.median(xs)))


if __name__ == "__main__":
    main()
