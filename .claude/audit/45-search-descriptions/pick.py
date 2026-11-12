"""Model pick check: sonnet names the result it would open first, given the question and one variant's search output.
python3 -I pick.py run <variant-file-tag> <qid> ...   (writes raw/pick-<variant>-<qid>.json)
Prompt text is identical across variants except the search output."""
import json, subprocess, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import RAW
import setup as S

PROMPT = """You are helping decide which search result to open first.

Question: {q}

A document search returned these results (top 8). Each result is a header line (location, estimated tokens, title, tags) and sometimes an indented description line.

{out}

Which ONE result would you open first to answer the question? Do not use any tools. Reply with only that result's path exactly as shown in its header, without the line range, and nothing else."""

def one(variant, qid, budget="0.15"):
    it = next(i for i in S.queries() if i["id"] == qid)
    f = RAW / f"pick-{variant}-{qid}.json"
    if f.exists(): return
    out = (RAW / f"v-{variant}-{qid}.txt").read_text()
    r = subprocess.run(["claude", "-p", "--model", "sonnet", "--tools", "Read", "--max-budget-usd", budget, "--output-format", "json",
                        "--no-session-persistence", PROMPT.format(q=it["question"], out=out.rstrip())],
                       capture_output=True, text=True, cwd="/tmp", stdin=subprocess.DEVNULL)
    f.write_text(r.stdout or json.dumps({"error": r.stderr}))

if __name__ == "__main__":
    for q in sys.argv[3:]:
        one(sys.argv[2], q)
