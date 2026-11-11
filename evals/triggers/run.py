#!/usr/bin/env python3
"""Skill-trigger eval runner: one `claude -p` call per question, judged by Skill tool_use.

usage: run.py --plugin-dir DIR --cond single|ctx --ids id1,id2,... --out FILE.jsonl [--reps N]
Each call is limited to one turn (--max-turns 1): the first tool call is the trigger decision.
"""
import argparse, csv, json, os, subprocess, sys
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = "/code/.cache/luau-kb-evals"
PREAMBLE = ("지금 Luau 라이브러리 저장소에서 작업 중이야. mise 로 luau 0.742 를 쓰고, src/queue.luau 를 "
            "--!strict 로 고치던 참이야. 그 작업과 별개로 이걸 물어볼게. ")


def load():
    rows = {}
    for line in open(os.path.join(HERE, "questions.tsv"), encoding="utf-8"):
        if line.startswith("#") or not line.strip():
            continue
        qid, kind, lang, exp, q = line.rstrip("\n").split("\t")
        rows[qid] = dict(id=qid, kind=kind, lang=lang, expected=exp, q=q)
    return rows


def run_one(a):
    plugin, cond, row, rep = a
    prompt = (PREAMBLE if cond == "ctx" else "") + row["q"]
    cmd = ["claude", "-p", "--model", "sonnet", "--plugin-dir", plugin, "--setting-sources", "project",
           "--output-format", "stream-json", "--verbose", "--max-turns", "1", "--no-session-persistence",
           "--max-budget-usd", "0.15", "--", prompt]
    p = subprocess.run(cmd, cwd=os.path.join(WORK, cond), capture_output=True, text=True, timeout=300)
    skills, cost = [], None
    for l in p.stdout.splitlines():
        try:
            e = json.loads(l)
        except ValueError:
            continue
        if e.get("type") == "assistant":
            for c in e["message"].get("content", []):
                if c.get("type") == "tool_use":
                    skills.append(c["input"].get("skill") if c["name"] == "Skill" else "tool:" + c["name"])
        if e.get("type") == "result":
            cost = e.get("total_cost_usd")
    return dict(id=row["id"], kind=row["kind"], lang=row["lang"], expected=row["expected"], cond=cond,
                rep=rep, calls=skills, cost=cost)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plugin-dir", required=True)
    ap.add_argument("--cond", required=True, choices=["single", "ctx"])
    ap.add_argument("--ids", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--reps", type=int, default=1)
    ap.add_argument("-j", type=int, default=4)
    o = ap.parse_args()
    rows = load()
    jobs = [(o.plugin_dir, o.cond, rows[i], r) for i in o.ids.split(",") for r in range(o.reps)]
    with ThreadPoolExecutor(o.j) as ex, open(o.out, "a", encoding="utf-8") as f:
        for res in ex.map(run_one, jobs):
            f.write(json.dumps(res, ensure_ascii=False) + "\n")
            f.flush()
            print(res["id"], res["calls"], res["cost"], flush=True)


main()
