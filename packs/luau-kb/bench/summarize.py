#!/usr/bin/env python3
"""bench/run.sh 출력(TSV)을 마크다운 표로 바꾼다.

사용: python3 -I bench/summarize.py results/latest.tsv [--group 접두] [--stat min] > 표.md
칸: 프로세스별 '중앙값 비율'의 중앙값, 괄호 안은 프로세스 사이 최소~최대.
--stat min: 프로세스별 '최소값 비율'(케이스 최소 ms / 기준 최소 ms)로 바꾼다. 할당이 많아 분포가 둘로 갈리는 그룹용.
첫 줄(기준 ms)은 기준 케이스의 중앙값 ms 를 프로세스 중앙값으로 적는다. 절대 시간은 기계마다 다르므로 참고용이다.
"""
import collections
import statistics
import sys


def main(argv):
    path = argv[1]
    prefix = None
    if "--group" in argv:
        prefix = argv[argv.index("--group") + 1]
    use_min = "--stat" in argv and argv[argv.index("--stat") + 1] == "min"
    rows = []
    res = collections.defaultdict(list)  # (file, group, case, mode) -> [ratio]
    base_ms = collections.defaultdict(list)  # (file, group, mode) -> [ms]
    mem = collections.defaultdict(list)
    order = collections.OrderedDict()  # (file, group) -> [case...]
    modes = []
    for line in open(path, encoding="utf-8"):
        cols = line.rstrip("\n").split("\t")
        if len(cols) < 6:
            continue
        ver, flags, proc, fname, kind = cols[:5]
        mode = f"{ver} {flags}"
        if mode not in modes:
            modes.append(mode)
        if kind == "RESULT":
            group, case, med, mn, ratio = cols[5:10]
            if prefix and not group.startswith(prefix):
                continue
            key = (fname, group)
            order.setdefault(key, [])
            if case not in order[key]:
                order[key].append(case)
            rows.append((fname, group, case, mode, proc, float(med), float(mn), float(ratio)))
            if case == order[key][0]:
                base_ms[(fname, group, mode)].append(float(mn) if use_min else float(med))
        elif kind == "MEM":
            group, case, b = cols[5:8]
            if prefix and not group.startswith(prefix):
                continue
            key = (fname, group)
            order.setdefault(key, [])
            if case not in order[key]:
                order[key].append(case)
            mem[(fname, group, case, mode)].append(float(b))

    base_min = {(r[0], r[1], r[3], r[4]): r[6] for r in rows if r[2] == order[(r[0], r[1])][0]}
    for fname, group, case, mode, proc, med, mn, ratio in rows:
        if use_min:
            ratio = mn / base_min[(fname, group, mode, proc)]
        res[(fname, group, case, mode)].append(ratio)

    canon = ["0.734 -O1", "0.742 -O1", "0.742 -O2", "0.742 -O2 --codegen"]
    modes.sort(key=lambda m: (canon.index(m) if m in canon else len(canon), m))

    def fmt(xs):
        if not xs:
            return "—"
        m = statistics.median(xs)
        if len(xs) == 1:
            return f"{m:.2f}"
        return f"{m:.2f} ({min(xs):.2f}–{max(xs):.2f})"

    print("| 그룹 / 케이스 | " + " | ".join(modes) + " |")
    print("|---|" + "---|" * len(modes))
    for (fname, group), cases in order.items():
        is_mem = any((fname, group, c, md) in mem for c in cases for md in modes)
        if is_mem:
            for c in cases:
                cells = []
                for md in modes:
                    xs = mem.get((fname, group, c, md), [])
                    cells.append(f"{statistics.median(xs):.0f} B" if xs else "—")
                print(f"| `{group}` {c} | " + " | ".join(cells) + " |")
            continue
        cells = []
        for md in modes:
            xs = base_ms.get((fname, group, md), [])
            cells.append(f"{statistics.median(xs):.2f} ms" if xs else "—")
        print(f"| **`{group}`** 기준 {cases[0]} | " + " | ".join(cells) + " |")
        for c in cases[1:]:
            print(f"| ↳ {c} | " + " | ".join(fmt(res.get((fname, group, c, md), [])) for md in modes) + " |")


if __name__ == "__main__":
    main(sys.argv)
