"""Agent adapters of the delegate driver: agy (Gemini, print mode) and codex (OpenAI, `codex exec`).

Each adapter knows its executable, how to fill a task HOME with credentials, the argv of one run and where its
answer lands. An agy ACP adapter is planned next to AgyPrint; print mode then stays as the uid backend's fallback.
"""
import os
import shutil
from pathlib import Path

import delegate_workspace as ws

PRINT_TIMEOUT_MARGIN = 60  # seconds the driver waits past the agent's own time limit before killing it
CODEX_SANDBOXES = ("read-only", "workspace-write", "danger-full-access")
# What the driver passes as `-s` when HARNESS_DELEGATE_CODEX_SANDBOX is empty. Permission profiles replace it later.
DEFAULT_CODEX_SANDBOX = "read-only"


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

    def report_path(self, wt, d, mode):
        return wt / "REPORT.md" if mode == "worktree" else d / "report.md"

    def last_path(self, d, mode):
        return None

    def argv(self, bin_path, model, effort, timeout, prompt, wt, last, cfg):
        return [bin_path, "--model", model, "--dangerously-skip-permissions", "--print-timeout", f"{timeout}s",
                "-p", prompt]

    def stdin(self, d):
        return None

    def extra_env(self, home):
        return {}

    def fallback(self, report, d, mode):
        # agy empty mode has no instruction to write a file; the answer arrives on stdout.
        if mode == "empty" and ws.has_content(d / "stdout.txt"):
            ws.write_safe(report, (ws.read_safe(d / "stdout.txt") or b"").decode("utf-8", "replace"))


class Codex:
    name = "codex"
    default_mode = "empty"
    bin_key, model_key, home_key = "HARNESS_DELEGATE_CODEX_BIN", "HARNESS_DELEGATE_CODEX_MODEL", "HARNESS_DELEGATE_CODEX_HOME"
    install_rel = "codex/latest/bin/codex"

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

    def report_path(self, wt, d, mode):
        return d / "report.md"

    def last_path(self, d, mode):
        # In worktree mode the model writes report.md itself, and -o on the same file would overwrite it.
        return d / "last-message.md" if mode == "worktree" else d / "report.md"

    def argv(self, bin_path, model, effort, timeout, prompt, wt, last, cfg):
        return [bin_path, "exec", "-m", model, "-c", f"model_reasoning_effort={effort}", "-c", "approval_policy=never",
                "-s", self.sandbox(cfg), "--skip-git-repo-check", "--ephemeral", "--ignore-user-config",
                "--color", "never", "-C", str(wt), "-o", str(last), "-"]

    def stdin(self, d):
        return d / "prompt.md"

    def extra_env(self, home):
        return {"CODEX_HOME": str(home / ".codex")}

    def fallback(self, report, d, mode):
        last = self.last_path(d, mode)
        if last != report and ws.has_content(last):
            ws.write_safe(report, (ws.read_safe(last) or b"").decode("utf-8", "replace"))


ADAPTERS = {a.name: a for a in (AgyPrint(), Codex())}
