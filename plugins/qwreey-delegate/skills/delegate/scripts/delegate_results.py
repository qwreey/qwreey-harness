"""Collecting, removing and cleaning up delegate runs (delegate.py's collect, remove, list, gc and the automatic
cleanup at the end of run).

Locations: new runs keep their workspace in <state>/work/<key>-<agent>/ and their results in
<state>/runs/<key>/<date>-<name>/. Workspaces beside the repository (<dirname(root)>/<key>-<agent>/, from delegate.sh
and earlier driver runs) are still found for list, collect and remove, but gc only lists them: deleting those is the
user's call.
"""
import datetime
import os
import shutil
import subprocess
from pathlib import Path

import delegate_isolation as iso
import delegate_workspace as ws

note = ws.note
die = ws.die
OLD_LEGACY_RUN_DAYS = 180  # gc mentions legacy runs/ records older than this; they are never deleted automatically


class Place:
    """One task's folders: base is the root-owned agent folder, legacy whether it is the old spot beside the repo."""

    def __init__(self, repo, agent, name, base, legacy):
        self.repo, self.agent, self.name, self.base, self.legacy = repo, agent, name, Path(base), legacy
        self.wt = self.base / name
        self.rec = ws.record_dir(self.base, name)
        self.home = self.base / ".homes" / name


def find(state_dir, repo, agent, name):
    """The task's Place, new location first, or None."""
    for base, legacy in ((ws.work_base(state_dir, repo, agent), False), (repo.legacy_base(agent), True)):
        if (base / name).is_dir() or ws.record_dir(base, name).is_dir():
            return Place(repo, agent, name, base, legacy)
    return None


def legacy_runs_of_uid(repo, uid):
    """Live delegate.sh runs that use uid: it runs every agent of a repository as the registry's third column."""
    return ws.live_legacy_runs([repo]) if uid == repo.uid else 0


def end_leftovers(state_dir, repo, agent):
    """Kill what still runs as the agent's uid before root reads or deletes its files, unless a live task of that uid
    holds its lock (then those processes are that task's)."""
    uid = repo.uid_for(agent)
    backend = iso.UidBackend(uid)
    if backend.unavailable() or not Path(state_dir).is_dir():
        return
    fd = ws.take_lock(ws.uid_lock_path(state_dir, uid))
    if fd is None:
        return
    try:
        if not legacy_runs_of_uid(repo, uid):
            killed = backend.end_task()
            if killed:
                note(f"killed {killed} leftover process(es) of uid {uid}")
    finally:
        os.close(fd)


def copy_probes(place, since, out, manifest):
    """agy writes its probes to brain/<conversation>/scratch under HOME, outside the guard's worktree change list,
    and remove deletes HOME; keep this task's scratch and transcript. HOME is the task's: walked from fds, no links."""
    brain = ws.open_dir_under(place.base, ".homes", place.name, ".gemini", "antigravity-cli", "brain")
    if brain is None:
        return
    try:
        for conv in sorted(os.listdir(brain)):
            cfd = ws.open_dir_under(brain, conv)
            if cfd is None:
                continue
            try:
                newer = os.fstat(cfd).st_mtime > since or any(
                    os.stat(n, dir_fd=tfd, follow_symlinks=False).st_mtime > since
                    for _t, ds, fs, tfd in os.fwalk(".", dir_fd=cfd, follow_symlinks=False) for n in ds + fs)
                if not newer:
                    continue
                dst = out / "agy" / conv
                for d in (out / "agy", dst):
                    os.makedirs(d, mode=ws.PRIVATE_MODE, exist_ok=True)
                sfd = ws.open_dir_under(cfd, "scratch")
                if sfd is not None:
                    try:
                        ws.copy_tree_at(sfd, dst / "scratch", manifest)
                    finally:
                        os.close(sfd)
                data = ws.read_under(cfd, ".system_generated", "logs", "transcript.jsonl")
                if data is not None:
                    ws.write_new(dst / "transcript.jsonl", data, manifest)
            finally:
                os.close(cfd)
    finally:
        os.close(brain)


def make_diff(place, out, manifest):
    """diff.patch of the worktree, new files included, without .delegate/ and the report; '' or the reason it failed.
    git runs as the task uid (git_as_task) while the task's HOME still exists."""
    backend = iso.UidBackend(place.repo.uid_for(place.agent))
    why = backend.unavailable()
    if why:
        return why
    common = (ws.git_out("-C", place.repo.root, "rev-parse", "--path-format=absolute", "--git-common-dir") or "").strip()
    # `add -N` writes the empty blob, and the task uid cannot write the main .git/objects (by design): new objects go
    # to a folder in the task's HOME, the main store is read as an alternate.
    odb = place.home / ".delegate-objects"
    env = iso.task_env(place.home, "", place.base / ".hooks", False, {
        "GIT_OBJECT_DIRECTORY": str(odb), "GIT_ALTERNATE_OBJECT_DIRECTORIES": os.path.join(common, "objects")})
    backend.run(["mkdir", "-p", str(odb)], env)
    spec = ["--", ".", f":!{ws.TASK_OUT}", ":!REPORT.md"]
    arc, _, aerr = iso.git_as_task(backend, env, place.wt, "add", "-N", "--all", *spec)
    drc, diff, derr = iso.git_as_task(backend, env, place.wt, "diff", "--binary", "--no-ext-diff", "--no-textconv",
                                      *spec)
    backend.end_task()
    if arc != 0 or drc != 0:
        return f"git add -N -> {arc} {aerr.strip()}; git diff -> {drc} {derr.strip()}"
    if diff:
        ws.write_new(out / "diff.patch", diff.encode("utf-8", "surrogateescape"), manifest)
    return ""


def collect_into(state_dir, place, mark=True):
    """Copy everything worth keeping into <state>/runs/<key>/<date>-<name>/ and check the copy byte for byte.
    Returns (out folder, problems). With mark the record is marked collected even when problems remain (collect by
    hand reports them as warnings); the automatic cleanup passes mark=False and keeps the workspace on problems."""
    st = ws.read_state(place.rec)
    old_shape = not st
    out = ws.make_runs_dir(state_dir, place.repo) / f"{datetime.datetime.now().strftime('%Y%m%d-%H%M')}-{place.name}"
    os.makedirs(out, mode=ws.PRIVATE_MODE, exist_ok=True)
    os.chmod(out, ws.PRIVATE_MODE)
    manifest, problems = [], []
    if old_shape:
        # delegate.sh kept its record inside the task copy; read it without following links.
        for f in ws.LEGACY_FILES:
            data = ws.read_under(place.base, place.name, ws.TASK_OUT, f)
            if data is not None:
                ws.write_new(out / f, data, manifest)
        data = ws.read_under(place.base, place.name, "REPORT.md")
        if data is not None:
            ws.write_new(out / "report.md", data, manifest)
    else:
        for f in ws.RUN_FILES:
            data = ws.read_under(place.rec, f)
            if data is not None:
                ws.write_new(out / f, data, manifest)
    try:
        if place.agent == "agy":
            copy_probes(place, float("-inf") if old_shape else st.get("started_ts", float("-inf")), out, manifest)
        if ws.exists_under(place.base, place.name, ".git"):
            why = make_diff(place, out, manifest)
            if why:
                problems.append(f"diff.patch not made: {why}")
    except OSError as e:
        problems.append(f"copy failed: {e}")
    problems += [f"copy differs from the source: {p}" for p in ws.verify_manifest(manifest)]
    if mark or not problems:
        ws.root_dir(place.base / ws.RECORDS, ws.PRIVATE_MODE)
        if old_shape:
            os.makedirs(place.rec, mode=ws.PRIVATE_MODE, exist_ok=True)
            ws.save_state(place.rec, {"driver": ws.PROG, "agent": place.agent, "legacy": True, "collected": str(out)})
        else:
            ws.update_state(place.rec, collected=str(out))
    return out, problems


def remove_workspace(place, discard=False, delete_branch=False, check=True):
    """Delete the task copy, its admin dir, HOME and record. check refuses a live run and an uncollected one."""
    if check:
        if ws.is_running(place.base, place.name):
            die(f"still running: {place.agent}/{place.name}")
        if not ws.is_collected(place.base, place.name) and not discard:
            # Workspaces from older scripts (.agy/ and AGY_REPORT.md) have a shape collect does not know.
            die(f"not collected yet - run '{ws.PROG} collect {place.agent} {place.name}' first, or pass --discard to "
                f"throw it away")
    repo = place.repo
    registered, branch = ws.worktree_entry(repo.root, place.wt)
    admin = ws.read_state(place.rec).get("admin")
    # Removed by root without running git inside the task's tree; shutil.rmtree does not follow links.
    if os.path.lexists(place.wt):
        shutil.rmtree(place.wt)
    worktrees = os.path.join(repo.root, ".git", "worktrees") + os.sep
    if admin and admin.startswith(worktrees) and os.path.lexists(admin):
        shutil.rmtree(admin)
    if registered or admin:
        subprocess.run(["git", "-C", repo.root, "worktree", "prune"], check=False)
    for p in (place.home, place.rec):
        if os.path.lexists(p):
            shutil.rmtree(p)
    if branch:
        if delete_branch:
            subprocess.run(["git", "-C", repo.root, "branch", "-D", branch], check=False)
        else:
            note(f"branch '{branch}' (old style) left in place; --delete-branch removes it, after the user confirms")


def auto_cleanup(state_dir, place):
    """End of run: collect, check the copy, then delete the workspace. (out, problems); on problems nothing is
    deleted. The caller still holds the run's locks, so no other task of this uid can start in between."""
    try:
        out, problems = collect_into(state_dir, place, mark=False)
    except (OSError, ws.DelegateError) as e:
        return None, [f"collect failed: {e}"]
    if problems:
        return out, problems
    try:
        remove_workspace(place, check=False)
    except OSError as e:
        return out, [f"remove failed: {e}"]
    return out, []


# ---------- list / gc ----------
def prune_preview(root):
    p = subprocess.run(["git", "-C", root, "worktree", "prune", "--dry-run", "-v"], capture_output=True, text=True)
    return (p.stdout + p.stderr).strip()


def list_repo(state_dir, repo):
    # The section for the old location beside the repository prints exactly as delegate.sh's list does.
    for agent in ws.AGENTS:
        base = repo.legacy_base(agent)
        if not base.is_dir():
            continue
        print(f"== {base} ({ws.du_h(base)})")
        for w in ws.workspaces(base):
            print(f"  {w.name:<28} {ws.state_of(base, w.name):<10} {ws.du_h(w):>6}  {ws.mtime_str(w)}")
        runs = base / "runs"
        if runs.is_dir():
            print(f"  runs/: {sum(1 for p in runs.iterdir() if p.is_dir())} ({ws.du_h(runs)})")
        if (base / ".home").is_dir():
            print(f"  .home (old shared HOME): {ws.du_h(base / '.home')}")
    for agent in ws.AGENTS:
        base = ws.work_base(state_dir, repo, agent)
        if not base.is_dir():
            continue
        print(f"== {base} ({ws.du_h(base)})")
        for w in ws.workspaces(base):
            print(f"  {w.name:<28} {ws.state_of(base, w.name):<10} {ws.du_h(w):>6}  {ws.mtime_str(w)}")
    runs = ws.runs_dir(state_dir, repo)
    if runs.is_dir():
        print(f"== {runs} ({ws.du_h(runs)})")
        for r in sorted(p for p in runs.iterdir() if p.is_dir()):
            print(f"  {r.name:<40} {ws.du_h(r):>6}  {ws.mtime_str(r)}")
    for line in prune_preview(repo.root).splitlines():
        print(f"  prune? {line}")


def gc_work(state_dir, repo, agent, apply):
    """New location: every workspace without a live run goes, after its results are safely in runs/."""
    base = ws.work_base(state_dir, repo, agent)
    if not base.is_dir():
        return
    tag = f"work/{repo.key}-{agent}"
    if ws.busy_inside(base):
        print(f"held       {tag} (a process is running inside this workspace - retry after it ends)")
        return
    names = {w.name for w in ws.workspaces(base)}
    recs = base / ws.RECORDS
    names |= {r.name for r in recs.iterdir() if r.is_dir()} if recs.is_dir() else set()
    for n in sorted(names):
        place = Place(repo, agent, n, base, False)
        st = ws.state_of(base, n)
        if st == "running":
            print(f"running    {tag}/{n}")
            continue
        print(f"delete     {tag}/{n} ({st}{'' if st == 'collected' else ', collected first'})")
        if not apply:
            continue
        end_leftovers(state_dir, repo, agent)
        if st != "collected":
            out, problems = collect_into(state_dir, place, mark=False)
            if problems:
                print(f"kept       {tag}/{n} (collect into {out} failed: {'; '.join(problems)})")
                continue
            print(f"collected  {tag}/{n} -> {out}")
        remove_workspace(place, check=False)
    homes = base / ".homes"
    for h in sorted(homes.iterdir()) if homes.is_dir() else ():
        if h.is_dir() and h.name not in names:
            print(f"delete     {tag}/.homes/{h.name} (HOME without an owner, {ws.du_h(h)})")
            if apply:
                shutil.rmtree(h)


def gc_runs(state_dir, repo, days, apply):
    runs = ws.runs_dir(state_dir, repo)
    for r in sorted(runs.iterdir()) if runs.is_dir() else ():
        if r.is_dir() and ws.age_days(r) > days:
            print(f"delete     runs/{repo.key}/{r.name} (results, {ws.age_days(r)}d old; older than {days}d)")
            if apply:
                shutil.rmtree(r)


def gc_legacy(repo, days):
    """Old location beside the repository: listed only, never deleted here."""
    for agent in ws.AGENTS:
        base = repo.legacy_base(agent)
        if not base.is_dir():
            continue
        tag = f"{repo.key}-{agent}"
        print(f"legacy     {base} (older location; gc lists it but never deletes there - use remove, or delete by "
              f"hand after reading)")
        for w in ws.workspaces(base):
            st, age, n = ws.state_of(base, w.name), ws.age_days(w), w.name
            hint = {"collected": "collected - remove it",
                    "finished": "finished but not collected - collect it, then remove",
                    "aborted": f"run ended without a result - read {ws.RECORDS}/{n}/, then remove --discard",
                    "legacy-record": "prompt/answer of an older script",
                    "legacy": "workspace of an older script - decide whether to keep AGY_REPORT.md, then remove --discard",
                    "running": "running"}.get(st, "unknown shape - inspect by hand")
            if st != "finished" or age >= days:
                print(f"  stale    {tag}/{n} ({age}d, {ws.du_h(w)}) - {hint}")
        homes = base / ".homes"
        for h in sorted(homes.iterdir()) if homes.is_dir() else ():
            if h.is_dir() and not (base / h.name).is_dir():
                print(f"  stale    {tag}/.homes/{h.name} (HOME without an owner, {ws.du_h(h)})")
        if (base / ".home").is_dir():
            print(f"  stale    {tag}/.home (old shared HOME, {ws.du_h(base / '.home')})")
        runs = base / "runs"
        for r in sorted(runs.iterdir()) if runs.is_dir() else ():
            if r.is_dir() and ws.age_days(r) > OLD_LEGACY_RUN_DAYS:
                print(f"  old      {r} ({OLD_LEGACY_RUN_DAYS}d+, kept record - a person decides whether to delete)")


def gc_repo(state_dir, repo, days, apply):
    for agent in ws.AGENTS:
        gc_work(state_dir, repo, agent, apply)
    gc_runs(state_dir, repo, days, apply)
    gc_legacy(repo, days)
    p = prune_preview(repo.root)
    if p:
        print(f"prune      {repo.key}: {p}")
        if apply:
            subprocess.run(["git", "-C", repo.root, "worktree", "prune", "-v"], check=False)
