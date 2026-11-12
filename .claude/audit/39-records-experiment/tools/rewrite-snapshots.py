import re, sys, os, subprocess, posixpath
from pathlib import Path
R = Path('/code/Projects/claude-doctor'); os.chdir(R)
mp = {}
for ln in Path('.claude/audit/39-records-experiment/move-map.tsv').read_text().splitlines():
    c = ln.split('\t')
    if len(c) >= 2 and not ln.startswith('#') and c[0] != 'old_path' and c[0] != c[1]:
        mp[c[0]] = c[1]
rev = {v: k for k, v in mp.items()}
dirs = {}
for o, n in mp.items():
    po, pn = o.split('/'), n.split('/')
    # drop common tail to get the moved directory prefixes
    for i in range(1, len(po)):
        d_old = '/'.join(po[:i]); k = len(pn) - (len(po) - i)
        if k > 0 and '/'.join(pn[k:]) == '/'.join(po[i:]):
            dirs.setdefault(d_old, '/'.join(pn[:k]))
def mapp(p):
    if p in mp: return mp[p]
    q = p
    while '/' in q:
        q = q.rsplit('/', 1)[0]
        if q in dirs: return dirs[q] + p[len(q):]
    return p
SKIP = lambda f: f.startswith(('.claude/audit/', '.claude/handoff/', '.claude/sessions/', '.claude/archive/'))
MANUAL = {'plugins/qwreey-conventions/skills/agent-records/SKILL.md', 'plugins/qwreey-conventions/skills/agent-docs/SKILL.md',
          'plugins/qwreey-conventions/hooks/conventions-check.py', 'CLAUDE.md'}
files = [f for f in subprocess.check_output(['git', 'ls-files'], text=True).split('\n') if f and SKIP(f) and not f.startswith('.claude/audit/39-records-experiment/')]
files = [f for f in files if f.endswith(('.md', '.py', '.sh', '.tsv', '.toml', '.json', '.env', '.fragment', '.template', '.txt', '.luau', '.gitignore')) or '/' not in f or f.startswith('home/')]
tokre = re.compile(r'(?<![\w./~$}:-])((?:audit|decisions|drafts|handoff)/[\w./<>*-]*)')
linkre = re.compile(r'(\]\()([^)\s#]+)(#[^)\s]*)?(\))')
out = []
def fix_tok(m):
    t = m.group(1); trail = ''
    while t and t[-1] in '.,;:': trail = t[-1] + trail; t = t[:-1]
    cand = t
    nt = mapp(cand.rstrip('/'))
    if nt == cand.rstrip('/') and not re.search(r'[<*>]', cand):
        # allow stem like audit/NN-* or partial name: try prefix before <, *
        return m.group(0)
    if not (os.path.exists(nt) or re.match(r'audit/\d', cand)):
        return m.group(0)
    if cand.endswith('/') : nt += '/'
    return nt + trail
def fix_tok2(m):
    t = m.group(1)
    # glob/placeholder: map the directory part
    k = re.search(r'[<*]', t)
    if k:
        head = t[:k.start()]; d = head.rsplit('/', 1)[0] if not head.endswith('/') else head.rstrip('/')
        base = head[len(d):]
        nd = mapp(d)
        if d in dirs: nd = dirs[d]
        if nd != d: return nd + base + t[k.start():]
        return t
    if t.rstrip('/') in ('audit', 'decisions', 'drafts', 'handoff'): return t
    return fix_tok(m)
for f in files:
    p = R / f
    try: s = p.read_text()
    except Exception: continue
    old_dir = posixpath.dirname(rev.get(f, f))
    new_dir = posixpath.dirname(f)
    lines = s.split('\n'); chg = False
    for i, ln in enumerate(lines):
        n = ln
        if f.endswith('.md'):
            def lk(m):
                tgt = m.group(2)
                if re.match(r'[a-z]+:|/', tgt): return m.group(0)
                oldt = posixpath.normpath(posixpath.join(old_dir, tgt))
                newt = mapp(oldt)
                if newt == oldt and old_dir == new_dir: return m.group(0)
                rel = os.path.relpath(newt, new_dir or '.')
                return m.group(1) + rel + (m.group(3) or '') + m.group(4)
            n = linkre.sub(lk, n)
        # skip token rewriting on link targets already handled: tokens with leading ../ are excluded by lookbehind
        n = tokre.sub(fix_tok2, n)
        if n != ln:
            lines[i] = n; chg = True; out.append(f'{f}:{i+1}\n  - {ln.strip()[:300]}\n  + {n.strip()[:300]}')
    if chg and '--dry' not in sys.argv: p.write_text('\n'.join(lines))
Path('/tmp/snap-changes.txt').write_text('\n'.join(out) + '\n')
print(len(out), 'lines')
