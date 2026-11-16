"""Agent adapters of the delegate driver: agy (Gemini, print mode) and codex (OpenAI, `codex exec`).

Each adapter knows its executable, how to fill a task HOME with credentials, the argv of one run and where its
answer lands. An agy ACP adapter is planned next to AgyPrint; print mode then stays as the uid backend's fallback.
"""
import json
import os
import shutil
import tempfile
from pathlib import Path

import delegate_workspace as ws

PRINT_TIMEOUT_MARGIN = 60  # seconds the driver waits past the agent's own time limit before killing it
CODEX_SANDBOXES = ("read-only", "workspace-write", "danger-full-access")
# What the driver passes as `-s` when HARNESS_DELEGATE_CODEX_SANDBOX is empty. Permission profiles replace it later.
DEFAULT_CODEX_SANDBOX = "read-only"


def _inside(path, folder):
    path, folder = os.path.realpath(path), os.path.realpath(folder)
    return path == folder or path.startswith(folder.rstrip(os.sep) + os.sep)


def temp_dirs():
    """Temp folders agy's default preset opens fully: /tmp, this platform's temp dir, $TMPDIR. Each given as written
    and resolved (a rule names a path, and /tmp may be a link, as on macOS), without repeats."""
    out = []
    for d in ("/tmp", tempfile.gettempdir(), os.environ.get("TMPDIR")):
        for p in (d, os.path.realpath(d) if d else None):
            if p and p.rstrip(os.sep) not in out:
                out.append(p.rstrip(os.sep) or os.sep)
    return out


def _is_shim(path):
    # A mise or asdf shim resolves the tool from the caller's environment, which the task's empty environment drops.
    return Path(path).parent.name == "shims"


def find_bin(configured, name, installs, install_rel):
    """configured path, else `name` on PATH (not a shim), else <installs>/<install_rel>. None when not executable."""
    if configured:
        return configured if os.access(configured, os.X_OK) else None
    found = shutil.which(name)
    if found and not _is_shim(found):
        return found
    p = Path(installs) / install_rel if installs else None
    return str(p) if p and os.access(p, os.X_OK) else None


class AgyPrint:
    name = "agy"
    default_mode = "worktree"
    bin_key, model_key, home_key = "HARNESS_DELEGATE_AGY_BIN", "HARNESS_DELEGATE_AGY_MODEL", "HARNESS_DELEGATE_AGY_HOME"
    install_rel = "antigravity-cli/latest/agy"
    separate_stderr = True  # stdout is one JSON object (--output-format json); stderr has the headless denial notes
    # The user's own agy history (other repositories' brain/ and conversations/) must not reach the task uid.
    # Credentials (antigravity-oauth-token), settings.json and config/ stay.
    HISTORY = ("brain", "conversations", "annotations", "implicit", "log", "crashes", "history.jsonl",
               "jetbox_summaries_proto.pb")
    HISTORY_PREFIXES = ("conversation_summaries.db",)

    def credentials(self, cfg):
        return Path(cfg[self.home_key])

    def check_mode(self, mode, cfg, backend):
        if mode == "empty":
            ws.note("warning: agy empty mode is unverified (only worktree mode has been exercised)")

    def prepare_home(self, cfg, home):
        src = self.credentials(cfg)

        def skip(directory, names):
            if Path(directory).name != "antigravity-cli":
                return []
            return [n for n in names if n in self.HISTORY or n.startswith(self.HISTORY_PREFIXES)]

        shutil.copytree(src, home / ".gemini", symlinks=True, ignore=skip)

    def policy(self, mode, backend, workspace):
        """(--settings object, notes). Print mode without --dangerously-skip-permissions denies, headless, file tools
        outside the workspace and a shell that has no sandbox, but its default preset opens the temp folders fully:
        those get explicit deny rules (Deny beats Ask and Allow). A temp folder that holds the workspace cannot be
        denied without denying the workspace too; it is skipped and named in the notes."""
        deny, allow, notes = [], [], []
        for d in temp_dirs():
            if _inside(workspace, d):
                notes.append(f"temp folder {d} holds the workspace, so it is not denied")
                continue
            deny += [f"read_file({d})", f"write_file({d})"]
        if mode == "worktree" and backend.name == "uid":
            allow.append("command(*)")  # tests and checks in its own worktree, as the task uid
        else:
            # empty mode never runs a shell; where agy has a shell sandbox its default would allow one inside it
            deny.append("command(*)")
        perms = {"deny": deny}
        if allow:
            perms["allow"] = allow
        return {"permissions": perms}, notes

    def report_rel(self, mode):
        return ("REPORT.md",) if mode == "worktree" else (ws.TASK_OUT, "report.md")

    def last_path(self, wt, mode):
        return None

    def argv(self, bin_path, model, effort, timeout, prompt, wt, last, cfg, settings):
        return [bin_path, "--model", model, "--print-timeout", f"{timeout}s", "--output-format", "json",
                "--settings", json.dumps(settings, separators=(",", ":")), "-p", prompt]

    def stdin(self, rec):
        return None

    def extra_env(self, home):
        return {}

    def fallback(self, mode):
        return None

    def outcome(self, rec):
        """{'response', 'denied', 'status'} from the JSON agy printed, or {} when stdout holds no JSON object."""
        data = ws.read_under(rec, "stdout.txt") or b""
        text = data.decode("utf-8", "replace").strip()
        obj = None
        for cand in [text] + [ln for ln in reversed(text.splitlines()) if ln.lstrip().startswith("{")]:
            try:
                obj = json.loads(cand)
                break
            except ValueError:
                continue
        if not isinstance(obj, dict):
            return {}
        denied = [d.get("action") or d.get("display_name") or "?" if isinstance(d, dict) else str(d)
                  for d in obj.get("denied_actions") or []]
        resp = obj.get("response")
        return {"response": resp if isinstance(resp, str) else "", "denied": denied, "status": obj.get("status")}


class Codex:
    name = "codex"
    default_mode = "empty"
    bin_key, model_key, home_key = "HARNESS_DELEGATE_CODEX_BIN", "HARNESS_DELEGATE_CODEX_MODEL", "HARNESS_DELEGATE_CODEX_HOME"
    install_rel = "codex/latest/bin/codex"
    separate_stderr = False

    def credentials(self, cfg):
        home = cfg.get(self.home_key) or os.environ.get("CODEX_HOME") or str(Path.home() / ".codex")
        return Path(home) / "auth.json"

    def sandbox(self, cfg):
        return cfg.get("HARNESS_DELEGATE_CODEX_SANDBOX") or DEFAULT_CODEX_SANDBOX

    def check_mode(self, mode, cfg, backend):
        sb = self.sandbox(cfg)
        if sb not in CODEX_SANDBOXES:
            ws.die(f"HARNESS_DELEGATE_CODEX_SANDBOX must be one of {', '.join(CODEX_SANDBOXES)} (or empty): {sb}")
        if sb == "danger-full-access" and backend.name != "uid":
            ws.die("HARNESS_DELEGATE_CODEX_SANDBOX=danger-full-access leaves no isolation without the uid backend",
                   ws.EXIT_REFUSED)
        if mode == "worktree" and sb == "read-only":
            ws.die("codex worktree mode cannot run a shell on this host (bubblewrap cannot create a namespace under an "
                   "unprivileged uid). Use --mode empty with the context in the prompt; turning the sandbox off with "
                   "HARNESS_DELEGATE_CODEX_SANDBOX=danger-full-access (user layer, ~/.claude/harness.env) leaves the uid "
                   "as the only isolation and is the user's decision", ws.EXIT_REFUSED)

    def prepare_home(self, cfg, home):
        dst = home / ".codex"
        dst.mkdir(parents=True)
        shutil.copyfile(self.credentials(cfg), dst / "auth.json")
        os.chmod(dst / "auth.json", 0o600)

    def report_rel(self, mode):
        return (ws.TASK_OUT, "report.md")

    def last_path(self, wt, mode):
        # In worktree mode the model writes report.md itself, and -o on the same file would overwrite it.
        return wt / ws.TASK_OUT / ("last-message.md" if mode == "worktree" else "report.md")

    def policy(self, mode, backend, workspace):
        return None, []

    def argv(self, bin_path, model, effort, timeout, prompt, wt, last, cfg, settings):
        return [bin_path, "exec", "-m", model, "-c", f"model_reasoning_effort={effort}", "-c", "approval_policy=never",
                "-s", self.sandbox(cfg), "--skip-git-repo-check", "--ephemeral", "--ignore-user-config",
                "--color", "never", "-C", str(wt), "-o", str(last), "-"]

    def stdin(self, rec):
        return rec / "prompt.md"

    def extra_env(self, home):
        return {"CODEX_HOME": str(home / ".codex")}

    def fallback(self, mode):
        return (ws.TASK_OUT, "last-message.md") if mode == "worktree" else None

    def outcome(self, rec):
        return {}


ADAPTERS = {a.name: a for a in (AgyPrint(), Codex())}
