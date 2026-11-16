#!/usr/bin/env python3
"""settings.json 마이그레이션 적용기. 표준 라이브러리만 쓴다.

정본은 settings.json 전체 사본이 아니라 home/settings-migrations/NNNN-<slug>.json 이다.
  {"id": "0001-harness-base", "why": "...", "ops": [ {...}, ... ]}
각 마이그레이션은 실제 settings.json 에 **한 번만** 적용하고, id 를 기록 파일(줄 단위)에 남긴다.
적용 뒤 사용자가 값을 바꾸거나 꺼도 되돌리지 않는다. 마이그레이션에 없는 항목은 건드리지 않는다.

연산(모두 멱등). path 는 키 배열(["enabledPlugins","x@y"]) 또는 점 문자열("a.b")
  set          path, value [, keep_existing:true]  값 설정(keep_existing 이면 이미 있을 때 둔다)
  add          path, items   문자열 배열에 없는 항목만 추가(배열이 없으면 만든다)
  remove       path, items   배열에서 뺀다
  delete       path [, if_value]  키 삭제(if_value 가 있으면 현재 값이 같을 때만. 사용자가 바꾼 값은 둔다)
  hook-upsert  event, command [, matcher, fields]  같은 command 의 훅이 있으면 교체, 없으면 추가
               훅 = {"type":"command","command":command, **fields}. command 의 $HOME 은 풀어 같은지 본다
  hook-remove  event, command   그 command 의 훅 제거(빈 그룹·이벤트도 정리)

태그(소유 판별, 보고용): 훅 command 가 $HOME/.claude/hooks/ 나 $CLAUDE_HOME/hooks/ 아래면 관리 훅,
  플러그인 이름이 @<관리 마켓> 으로 끝나면 관리 플러그인(HOME_SYNC_MARKETS, 기본 claude-doctor-market).

사용:
  settings-migrate.py run    --settings S --dir D --records R [--dry-run] [--out O] [--quiet]
  settings-migrate.py status --settings S --dir D --records R
exit: 0 정상 / 1 마이그레이션 실패(그 마이그레이션은 되돌림, 앞선 것은 적용) / 2 JSON·사용 오류
"""
import argparse, copy, glob, json, os, shutil, sys, time


class OpError(Exception):
    pass


def split_path(p):
    if isinstance(p, str):
        return p.split(".")
    if isinstance(p, list) and p and all(isinstance(x, str) for x in p):
        return p
    raise OpError(f"path 형식 오류: {p!r}")


def dumps(v):
    return json.dumps(v, sort_keys=True, ensure_ascii=False)


def parent(d, parts, create):
    for p in parts[:-1]:
        nxt = d.get(p)
        if nxt is None:
            if not create:
                return None
            nxt = d[p] = {}
        if not isinstance(nxt, dict):
            raise OpError(f"{'.'.join(parts)}: 중간 값 {p!r} 가 객체가 아니다")
        d = nxt
    return d


def cmd_key(c, home):
    if not isinstance(c, str):
        return repr(c)
    for pre in ("${HOME}", "$HOME"):
        c = c.replace(pre, home)
    return c


def op_set(d, o, ctx):
    parts = split_path(o["path"])
    par = parent(d, parts, True)
    if o.get("keep_existing") and parts[-1] in par:
        return
    par[parts[-1]] = copy.deepcopy(o["value"])


def get_list(d, parts, create):
    par = parent(d, parts, create)
    if par is None:
        return None, None
    cur = par.get(parts[-1])
    if cur is None:
        if not create:
            return par, None
        cur = par[parts[-1]] = []
    if not isinstance(cur, list):
        raise OpError(f"{'.'.join(parts)}: 배열이 아니다")
    return par, cur


def op_add(d, o, ctx):
    parts = split_path(o["path"])
    _, lst = get_list(d, parts, True)
    for x in o["items"]:
        if x not in lst:
            lst.append(x)


def op_remove(d, o, ctx):
    parts = split_path(o["path"])
    par, lst = get_list(d, parts, False)
    if lst is None:
        return
    lst[:] = [x for x in lst if x not in o["items"]]


def op_delete(d, o, ctx):
    parts = split_path(o["path"])
    par = parent(d, parts, False)
    if par is None or parts[-1] not in par:
        return
    if "if_value" in o and par[parts[-1]] != o["if_value"]:
        return
    del par[parts[-1]]


def event_list(d, ev, create):
    hooks = d.get("hooks")
    if hooks is None:
        if not create:
            return None
        hooks = d["hooks"] = {}
    if not isinstance(hooks, dict):
        raise OpError("hooks 가 객체가 아니다")
    lst = hooks.get(ev)
    if lst is None:
        if not create:
            return None
        lst = hooks[ev] = []
    if not isinstance(lst, list):
        raise OpError(f"hooks.{ev} 가 배열이 아니다")
    return lst


def prune(d, ev):
    lst = d.get("hooks", {}).get(ev)
    if isinstance(lst, list):
        lst[:] = [g for g in lst if not (isinstance(g, dict) and isinstance(g.get("hooks"), list) and not g["hooks"])]
        if not lst:
            del d["hooks"][ev]
    if d.get("hooks") == {}:
        del d["hooks"]


def find_hooks(lst, key, home):
    for gi, g in enumerate(lst):
        if not isinstance(g, dict) or not isinstance(g.get("hooks"), list):
            continue
        for hi, h in enumerate(g["hooks"]):
            if isinstance(h, dict) and cmd_key(h.get("command"), home) == key:
                yield gi, hi


def op_hook_upsert(d, o, ctx):
    ev, cmd, matcher = o["event"], o["command"], o.get("matcher", "")
    hook = {"type": "command", "command": cmd, **o.get("fields", {})}
    lst = event_list(d, ev, True)
    key = cmd_key(cmd, ctx["home"])
    placed = False
    for gi, hi in list(find_hooks(lst, key, ctx["home"])):
        g = lst[gi]
        if g.get("matcher", "") == matcher and not placed:
            g["hooks"][hi] = hook; placed = True
        else:
            g["hooks"][hi] = None  # 다른 그룹, 중복은 제거 표시
    for g in lst:
        if isinstance(g, dict) and isinstance(g.get("hooks"), list):
            g["hooks"] = [h for h in g["hooks"] if h is not None]
    if not placed:
        for g in lst:
            if isinstance(g, dict) and g.get("matcher", "") == matcher and isinstance(g.get("hooks"), list):
                g["hooks"].append(hook); placed = True; break
    if not placed:
        lst.append(({"matcher": matcher} if matcher else {}) | {"hooks": [hook]})
    lst[:] = [g for g in lst if not (isinstance(g, dict) and g.get("hooks") == [])]


def op_hook_remove(d, o, ctx):
    ev = o["event"]
    lst = event_list(d, ev, False)
    if lst is None:
        return
    key = cmd_key(o["command"], ctx["home"])
    for g in lst:
        if isinstance(g, dict) and isinstance(g.get("hooks"), list):
            g["hooks"] = [h for h in g["hooks"] if not (isinstance(h, dict) and cmd_key(h.get("command"), ctx["home"]) == key)]
    prune(d, ev)


OPS = {"set": op_set, "add": op_add, "remove": op_remove, "delete": op_delete,
       "hook-upsert": op_hook_upsert, "hook-remove": op_hook_remove}
REQ = {"set": ("path", "value"), "add": ("path", "items"), "remove": ("path", "items"), "delete": ("path",),
       "hook-upsert": ("event", "command"), "hook-remove": ("event", "command")}


def describe(o):
    t = o.get("path") or f"{o.get('event')}:{o.get('command')}"
    t = ".".join(t) if isinstance(t, list) else t
    extra = f" {o['items']}" if "items" in o else ""
    return f"{o.get('op')} {t}{extra}"


def apply_migration(settings, mig, ctx):
    """settings 사본에 ops 를 적용해 (새 settings, [(op, 변경 여부)]) 를 돌려준다. 실패하면 OpError."""
    cur = copy.deepcopy(settings)
    res = []
    for i, o in enumerate(mig.get("ops", [])):
        name = o.get("op")
        if name not in OPS:
            raise OpError(f"ops[{i}]: 알 수 없는 op {name!r}")
        for r in REQ[name]:
            if r not in o:
                raise OpError(f"ops[{i}] {name}: {r} 필요")
        before = dumps(cur)
        try:
            OPS[name](cur, o, ctx)
        except OpError as e:
            raise OpError(f"ops[{i}] {describe(o)}: {e}")
        res.append((o, dumps(cur) != before))
    return cur, res


def load_json(p, what, default=None):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        if default is not None:
            return default
        raise SystemExit(f"중단: {what} 없음: {p}")
    except ValueError as e:
        print(f"중단: {what} JSON 오류 ({p}): {e}", file=sys.stderr)
        sys.exit(2)


def load_migrations(d):
    out = []
    for p in sorted(glob.glob(os.path.join(d, "*.json"))):
        m = load_json(p, "마이그레이션")
        if not isinstance(m, dict) or "id" not in m or not isinstance(m.get("ops", []), list):
            print(f"중단: 마이그레이션 형식 오류: {p}", file=sys.stderr); sys.exit(2)
        out.append(m)
    ids = [m["id"] for m in out]
    if len(set(ids)) != len(ids):
        print("중단: 마이그레이션 id 중복", file=sys.stderr); sys.exit(2)
    return out


def read_records(p):
    try:
        with open(p, encoding="utf-8") as f:
            return [l.strip() for l in f if l.strip()]
    except FileNotFoundError:
        return None


def ownership(settings, home, claude_home):
    markets = [m for m in os.environ.get("HOME_SYNC_MARKETS", "claude-doctor-market").split(",") if m]
    mh = tuple(cmd_key(x, home) for x in ("$HOME/.claude/hooks/", ))+ (claude_home.rstrip("/") + "/hooks/",)
    hm = hu = 0
    for groups in (settings.get("hooks") or {}).values():
        for g in groups if isinstance(groups, list) else []:
            for h in (g.get("hooks") or []) if isinstance(g, dict) else []:
                c = cmd_key(h.get("command"), home) if isinstance(h, dict) else ""
                if any(m in c for m in mh):
                    hm += 1
                else:
                    hu += 1
    pl = settings.get("enabledPlugins") or {}
    pm = sum(1 for k in pl if any(k.endswith("@" + m) for m in markets))
    return f"훅 관리 {hm} / 그 밖 {hu}, 플러그인 관리 {pm} / 그 밖 {len(pl) - pm}"


def plan(a):
    home = os.environ.get("HOME", "")
    migs = load_migrations(a.dir)
    recs = read_records(a.records)
    done = set(recs or [])
    settings = load_json(a.settings, "실제 settings.json", default={})
    if not isinstance(settings, dict):
        print("중단: settings.json 최상위가 객체가 아니다", file=sys.stderr); sys.exit(2)
    return home, migs, recs, done, settings


def cmd_status(a):
    home, migs, recs, done, _ = plan(a)
    pend = [m["id"] for m in migs if m["id"] not in done]
    print(f"{len(migs) - len(pend)}/{len(migs)} 적용" + ("" if recs is not None else " (기록 파일 없음 — 첫 apply)") + (f", 미적용: {', '.join(pend)}" if pend else ""))
    return 0


def cmd_run(a):
    home, migs, recs, done, settings = plan(a)
    claude_home = os.path.dirname(os.path.abspath(a.settings))
    ctx = {"home": home}
    pend = [m for m in migs if m["id"] not in done]
    log = (lambda *x: None) if a.quiet else print
    log(f"# 마이그레이션 {len(migs) - len(pend)}/{len(migs)} 적용됨" + ("" if recs is not None else " (기록 파일 없음 — 첫 apply: 모두 미적용으로 본다)"))
    cur, applied, failed = settings, [], None
    for m in pend:
        try:
            new, res = apply_migration(cur, m, ctx)
        except OpError as e:
            failed = (m["id"], str(e))
            log(f"## {m['id']}  실패 -> 이 마이그레이션 전체를 되돌림: {e}")
            break
        n = sum(1 for _, ch in res if ch)
        log(f"## {m['id']}  ({n} 변경 / {len(res) - n} no-op)  {m.get('why', '')}")
        for o, ch in res:
            log(f"   {'변경' if ch else 'no-op'}  {describe(o)}")
        cur = new
        applied.append(m["id"])
    changed = dumps(cur) != dumps(settings)
    log(f"# 소유: 지금 {ownership(settings, home, claude_home)} -> 이후 {ownership(cur, home, claude_home)}")
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(cur, f, indent=2, ensure_ascii=False); f.write("\n")
    if not a.dry_run:
        if changed:
            if os.path.exists(a.settings):
                shutil.copy2(a.settings, f"{a.settings}.bak-{time.strftime('%Y%m%d%H%M%S')}")
            tmp = a.settings + ".tmp"
            os.makedirs(os.path.dirname(os.path.abspath(a.settings)), exist_ok=True)
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(cur, f, indent=2, ensure_ascii=False); f.write("\n")
            os.replace(tmp, a.settings)
            print("applied settings.json (마이그레이션 " + ", ".join(applied) + ")")
        if applied:
            with open(a.records, "a", encoding="utf-8") as f:
                for i in applied:
                    f.write(i + "\n")
    if failed:
        print(f"실패: {failed[0]}: {failed[1]}", file=sys.stderr)
        return 1
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    for n in ("run", "status"):
        p = sp.add_parser(n)
        p.add_argument("--settings", required=True); p.add_argument("--dir", required=True); p.add_argument("--records", required=True)
        if n == "run":
            p.add_argument("--dry-run", action="store_true"); p.add_argument("--out"); p.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    return cmd_run(a) if a.cmd == "run" else cmd_status(a)


if __name__ == "__main__":
    sys.exit(main())
