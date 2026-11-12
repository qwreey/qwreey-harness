import json, sys, collections
p = sys.argv[1]
types = collections.Counter(); sub = collections.Counter(); keys = collections.Counter()
blocks = collections.Counter(); flags = collections.Counter(); sizes = collections.Counter()
examples = {}
n = 0
with open(p, encoding='utf-8', errors='replace') as f:
    for line in f:
        n += 1
        try: o = json.loads(line)
        except Exception: types['<bad>'] += 1; continue
        t = o.get('type'); types[t] += 1
        sizes[t] += len(line)
        for k in o: keys[k] += 1
        st = o.get('subtype')
        if st: sub[(t, st)] += 1
        for fl in ('isMeta','isSidechain','isCompactSummary','isVisibleInTranscriptOnly','toolUseResult','compactMetadata','isApiErrorMessage','attachment'):
            if o.get(fl): flags[fl] += 1
        m = o.get('message') or {}
        c = m.get('content') if isinstance(m, dict) else None
        if isinstance(c, list):
            for b in c:
                if isinstance(b, dict): blocks[(t, b.get('type'))] += 1
        elif isinstance(c, str):
            blocks[(t, 'str')] += 1
        key = (t, st, bool(o.get('isCompactSummary')))
        if key not in examples:
            examples[key] = {k: (str(v)[:160]) for k, v in o.items()}
print('lines', n)
print('types', types.most_common())
print('bytes_by_type', {k: v for k, v in sizes.most_common()})
print('subtypes', sub.most_common(30))
print('flags', flags.most_common())
print('blocks', blocks.most_common())
print('keys', keys.most_common(60))
if len(sys.argv) > 2:
    for k, v in examples.items():
        print('---', k); print(json.dumps(v, ensure_ascii=False)[:900])
