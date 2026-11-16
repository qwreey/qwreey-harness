"""Bash 명령을 구간으로 나누는 가벼운 도구. heavy-proc-guard.py 와 self-match-guard.py 가 같이 쓴다.

셸 문법을 다 읽지는 않는다: heredoc 본문을 버리고 `&&`, `||`, `;`, `|`, 줄바꿈으로 나눈 뒤 각 구간의 머리 프로그램을 찾는다.
따옴표 안의 구분자도 나누므로 훅은 오탐 쪽으로 기운다.
"""
import re

PREFIX_WORDS = {"(", "{", "time", "nice", "env", "command", "exec", "nohup"}

HEREDOC = re.compile(r"<<(?!<)-?\s*(?:'([A-Za-z_]\w*)'|\"([A-Za-z_]\w*)\"|\\?([A-Za-z_]\w*))")

SPLIT = re.compile(r"&&|\|\||[;|\n]")


def strip_heredocs(cmd, dropped=None):
    """Command without heredoc bodies; the body lines go to `dropped` when a list is given."""
    out, pending = [], []  # pending: (terminator, tab-stripped) for heredocs opened on earlier lines
    for line in cmd.split("\n"):
        if pending:
            term, dash = pending[0]
            if (line.lstrip("\t") if dash else line) == term:
                pending.pop(0)
            elif dropped is not None:
                dropped.append(line)
            continue
        out.append(line)
        for m in HEREDOC.finditer(line):
            pending.append((m.group(1) or m.group(2) or m.group(3), m.group(0).startswith("<<-")))
    return "\n".join(out)


def segments(cmd):
    """(head, segment text) per segment; head is the program after env/time/timeout/... prefixes."""
    for seg in SPLIT.split(strip_heredocs(cmd)):
        words = seg.replace("(", " ( ").split()
        i = 0
        while i < len(words):
            w = words[i]
            if w in PREFIX_WORDS or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=\S*", w):
                i += 1
            elif w == "timeout":
                i += 1
                while i < len(words) and (words[i].startswith("-") or re.fullmatch(r"[\d.]+[smhd]?", words[i])):
                    i += 2 if words[i] in ("-s", "-k", "--signal", "--kill-after") else 1
            elif w == "mise" and i + 1 < len(words) and words[i + 1] == "exec":
                i += 2
                if i < len(words) and words[i] == "--":
                    i += 1
            else:
                break
        if i < len(words):
            yield words[i], seg
