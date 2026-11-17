#!/usr/bin/env python3
"""Launcher tests with fake binaries and stores in a temporary HOME. No model calls, no real luau-lsp.

Runs launcher/luau-lsp (sh) for every case. With a PowerShell 7 binary in $LUAU_LSP_TEST_PWSH (or pwsh on PATH)
the same cases also run find-luau-lsp.ps1, so the Windows search is checked against the same expectations;
without one those runs are skipped and only the static checks of luau-lsp.cmd and the .ps1 run.
Usage: python3 -I plugins/luau-lsp/tests/test-launcher.py
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
SH = PLUGIN / "launcher" / "luau-lsp"
CMD = PLUGIN / "launcher" / "luau-lsp.cmd"
PS1 = PLUGIN / "launcher" / "find-luau-lsp.ps1"


def find_pwsh():
    """A PowerShell that starts; a version manager shim without a pinned version does not."""
    p = os.environ.get("LUAU_LSP_TEST_PWSH") or shutil.which("pwsh")
    if not p:
        return None
    try:
        ok = subprocess.run([p, "-NoProfile", "-NonInteractive", "-Command", "exit 0"], stdin=subprocess.DEVNULL,
                            capture_output=True, timeout=30).returncode == 0
    except OSError:
        ok = False
    return p if ok else None


PWSH = find_pwsh()
SYS_PATH = "/usr/bin:/bin"
TAGS = ["rokit", "aftman", "foreman", "mise", "editor", "env", "mise-pin", "path", "stores", "fail"]
EXT = "johnnymorganz.luau-lsp"


def fake(path, label, version_rc=0):
    """A stand-in binary: `--version` exits with version_rc, otherwise prints its label and each argument."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "#!/bin/sh\n"
        f'if [ "$1" = --version ]; then echo 0.0.0; exit {version_rc}; fi\n'
        f"echo BIN={label}\n"
        'for a in "$@"; do echo "ARG=$a"; done\n'
    )
    path.chmod(0o755)
    return path


class Env:
    def __init__(self, tmp):
        self.root = Path(tmp)
        self.home = self.root / "home"
        self.proj = self.root / "proj"
        self.bindir = self.root / "bin"
        for d in (self.home, self.proj, self.bindir):
            d.mkdir()
        self.extra = {}

    def env(self, windows_names=False):
        e = {
            "PATH": f"{self.bindir}:{SYS_PATH}",
            "HOME": str(self.home),
            "CLAUDE_PROJECT_DIR": str(self.proj),
            "CLAUDE_PLUGIN_ROOT": str(PLUGIN),
        }
        if windows_names:
            e.update(USERPROFILE=str(self.home), LOCALAPPDATA=str(self.home / ".local" / "share"), APPDATA=str(self.home / ".config"))
        e.update(self.extra)
        return e

    # stores, laid out as each tool writes them
    def rokit(self, ver):
        return fake(self.home / ".rokit" / "tool-storage" / "johnnymorganz" / "luau-lsp" / ver / "luau-lsp", f"rokit-{ver}")

    def aftman(self, ver):
        return fake(self.home / ".aftman" / "tool-storage" / "JohnnyMorganz" / "luau-lsp" / ver / "luau-lsp", f"aftman-{ver}")

    def foreman(self, ver):
        return fake(self.home / ".foreman" / "tools" / f"github.com__johnnymorganz__luau-lsp-{ver}", f"foreman-{ver}")

    def mise(self, ver):
        return fake(self.home / ".local" / "share" / "mise" / "installs" / "github-johnny-morganz-luau-lsp" / ver / "luau-lsp", f"mise-{ver}")

    def editor(self, ver):
        return fake(self.home / ".vscode" / "extensions" / f"{EXT}-{ver}-linux-x64" / "bin" / "server", f"editor-{ver}")

    def storage(self, name):
        p = self.home / ".config" / "Code" / "User" / "globalStorage" / EXT / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("-- stub\n")
        return p


def run_sh(env):
    p = subprocess.run([str(SH)], env=env.env(), stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30)
    out = p.stdout.splitlines()
    label = next((line[4:] for line in out if line.startswith("BIN=")), None)
    args = [line[4:] for line in out if line.startswith("ARG=")]
    return p.returncode, label, args, p.stderr


def split_cmdline(s):
    """Splits the LLSP_ARGS line the way the C runtime would for these simple quoted arguments."""
    return [a.replace('"', "") for a in re.findall(r'(?:"[^"]*"|[^\s"])+', s)]


def run_ps1(env):
    p = subprocess.run([PWSH, "-NoLogo", "-NoProfile", "-NonInteractive", "-File", str(PS1)], env=env.env(windows_names=True),
                       cwd=env.proj, stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=60)
    vals = dict(line.split("=", 1) for line in p.stdout.splitlines() if "=" in line)
    bad = [line for line in p.stdout.splitlines() if line and not line.startswith("LLSP_")]
    label = None
    if "LLSP_BIN" in vals:
        q = subprocess.run([vals["LLSP_BIN"]], capture_output=True, text=True, timeout=10)
        label = next((line[4:] for line in q.stdout.splitlines() if line.startswith("BIN=")), None)
    rc = p.returncode if p.returncode else (0 if "LLSP_BIN" in vals else 127)
    return rc, label, split_cmdline(vals.get("LLSP_ARGS", "")), p.stderr, bad


class Launcher(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="luau-lsp-launcher-")
        self.e = Env(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def check(self, label=None, rc=0, args_has=(), args_lacks=(), err=None):
        """Asserts the sh launcher's result, then the .ps1 result for the same setup when PowerShell is available."""
        runs = [("sh",) + run_sh(self.e)]
        if PWSH:
            r = run_ps1(self.e)
            self.assertEqual(r[4], [], "ps1 printed lines cmd would also `set`")
            runs.append(("ps1",) + r[:4])
        for who, got_rc, got_label, args, stderr in runs:
            with self.subTest(launcher=who):
                self.assertEqual(got_rc, rc, f"{who} stderr: {stderr}")
                if label is not None:
                    self.assertEqual(got_label, label, f"{who} stderr: {stderr}")
                for a in args_has:
                    self.assertIn(a, args, who)
                for a in args_lacks:
                    self.assertFalse(any(x.startswith(a) for x in args), f"{who}: {a} in {args}")
                if err:
                    self.assertIn(err, stderr, who)
                    self.assertEqual(len(stderr.strip().splitlines()), 1, f"{who}: one stderr line, got {stderr!r}")

    # binary search order
    def test_env_override_wins(self):
        self.e.rokit("9.9.9")
        fake(self.e.bindir / "luau-lsp", "path")
        self.e.extra["LUAU_LSP_BIN"] = str(fake(self.e.root / "pinned" / "luau-lsp", "env"))
        self.check(label="env")

    def test_env_override_missing_fails(self):
        self.e.rokit("1.70.1")
        self.e.extra["LUAU_LSP_BIN"] = str(self.e.root / "nope")
        self.check(rc=127, err="LUAU_LSP_BIN")

    def test_mise_pin_beats_path_and_stores(self):
        pinned = fake(self.e.root / "pin" / "luau-lsp", "mise-pin")
        fake(self.e.bindir / "luau-lsp", "path")
        self.e.rokit("9.9.9")
        (self.e.bindir / "mise").write_text(f'#!/bin/sh\n[ "$1" = which ] && echo "{pinned}"\n')
        (self.e.bindir / "mise").chmod(0o755)
        self.check(label="mise-pin")

    def test_mise_shim_answer_skipped(self):
        shim = fake(self.e.root / "mise" / "shims" / "luau-lsp", "shim")
        (self.e.bindir / "mise").write_text(f'#!/bin/sh\n[ "$1" = which ] && echo "{shim}"\n')
        (self.e.bindir / "mise").chmod(0o755)
        self.e.aftman("1.70.1")
        self.check(label="aftman-1.70.1")

    def test_path_used_when_version_works(self):
        fake(self.e.bindir / "luau-lsp", "path")
        self.e.rokit("9.9.9")
        self.check(label="path")

    def test_path_shim_failing_version_skipped(self):
        fake(self.e.bindir / "luau-lsp", "trampoline", version_rc=1)
        self.e.mise("1.69.0")
        self.check(label="mise-1.69.0")

    def test_highest_version_across_stores(self):
        self.e.rokit("1.68.0")
        self.e.aftman("1.69.0")
        self.e.foreman("1.70.1")
        self.e.mise("1.69.5")
        self.e.editor("1.65.0")
        self.check(label="foreman-1.70.1")

    def test_versions_compare_numerically(self):
        self.e.mise("1.9.0")
        self.e.mise("1.10.0")
        self.check(label="mise-1.10.0")

    def test_tie_goes_to_earlier_store(self):
        self.e.mise("1.70.1")
        self.e.rokit("1.70.1")
        self.check(label="rokit-1.70.1")

    def test_mise_alias_dirs_ignored(self):
        self.e.mise("1.69.0")
        alias = self.e.home / ".local" / "share" / "mise" / "installs" / "github-johnny-morganz-luau-lsp" / "latest"
        fake(alias / "luau-lsp", "mise-latest")
        self.check(label="mise-1.69.0")

    def test_editor_server_found(self):
        self.e.editor("1.70.1")
        self.check(label="editor-1.70.1")

    def test_nothing_found_fails_with_one_line(self):
        self.check(rc=127, err="luau-lsp not found")

    # platform and arguments
    def test_standard_without_rojo_files(self):
        self.e.rokit("1.70.1")
        self.check(label="rokit-1.70.1",
                   args_has=["lsp", "--stdio", "--flag:LuauSolverV2=true", f"--settings={PLUGIN}/lsp-settings/standard.json"],
                   args_lacks=["--definitions", "--docs"])

    def test_rojo_project_file_selects_roblox(self):
        self.e.rokit("1.70.1")
        (self.e.proj / "default.project.json").write_text("{}")
        self.check(args_has=[f"--settings={PLUGIN}/lsp-settings/roblox.json",
                             f"--definitions=@roblox={PLUGIN}/definitions/globalTypes.d.luau"])

    def test_sourcemap_alone_selects_roblox(self):
        self.e.rokit("1.70.1")
        (self.e.proj / "sourcemap.json").write_text("{}")
        self.check(args_has=[f"--settings={PLUGIN}/lsp-settings/roblox.json"])

    def test_platform_override_and_bad_value(self):
        self.e.rokit("1.70.1")
        (self.e.proj / "default.project.json").write_text("{}")
        self.e.extra["LUAU_LSP_PLATFORM"] = "standard"
        self.check(args_has=[f"--settings={PLUGIN}/lsp-settings/standard.json"], args_lacks=["--definitions"])
        self.e.extra["LUAU_LSP_PLATFORM"] = "rbx"
        self.check(rc=2)

    def test_defs_and_docs_overrides(self):
        self.e.rokit("1.70.1")
        (self.e.proj / "default.project.json").write_text("{}")
        self.e.extra.update(LUAU_LSP_DEFS="/x/defs.d.luau", LUAU_LSP_DOCS="/x/docs.json")
        self.check(args_has=["--definitions=@roblox=/x/defs.d.luau", "--docs=/x/docs.json"])

    def test_editor_files_used_with_editor_server(self):
        self.e.editor("1.70.1")
        defs = self.e.storage("globalTypes.PluginSecurity.d.luau")
        docs = self.e.storage("api-docs.json")
        (self.e.proj / "default.project.json").write_text("{}")
        self.check(label="editor-1.70.1", args_has=[f"--definitions=@roblox={defs}", f"--docs={docs}"])

    def test_editor_definitions_not_mixed_with_other_server(self):
        self.e.rokit("1.70.1")
        self.e.storage("globalTypes.PluginSecurity.d.luau")
        docs = self.e.storage("api-docs.json")
        (self.e.proj / "default.project.json").write_text("{}")
        self.check(args_has=[f"--definitions=@roblox={PLUGIN}/definitions/globalTypes.d.luau", f"--docs={docs}"])

    def test_standard_uses_editor_luau_docs(self):
        self.e.rokit("1.70.1")
        docs = self.e.storage("luau-api-docs.json")
        self.check(args_has=[f"--docs={docs}"], args_lacks=["--definitions"])


class WindowsFiles(unittest.TestCase):
    """luau-lsp.cmd cannot run here; these check the shape that makes it work on Windows."""

    def test_search_order_matches(self):
        sh = re.findall(r"\[find:([\w-]+)\]", SH.read_text())
        ps = re.findall(r"\[find:([\w-]+)\]", PS1.read_text())
        self.assertEqual(sh, TAGS)
        self.assertEqual(ps, TAGS)

    def test_cmd_shape(self):
        raw = CMD.read_bytes()
        self.assertNotIn(b"\n", raw.replace(b"\r\n", b""), "luau-lsp.cmd needs CRLF line endings")
        lines = raw.decode("ascii").split("\r\n")
        self.assertEqual(lines[0], "@echo off")
        code = [ln for ln in lines if ln and not ln.lower().startswith("rem ")]
        server = code[1:code.index(":which")]
        self.assertFalse([ln for ln in server if re.match(r"\s*@?echo\b", ln, re.I)], "the server path may not print to stdout")
        joined = "\n".join(server)
        self.assertRegex(joined, r'for /f "usebackq delims=" %%L in \(`powershell\.exe [^`]*-NoProfile[^`]*-ExecutionPolicy Bypass -File "%~dp0find-luau-lsp\.ps1" \^<NUL`\) do set "%%L"')
        self.assertIn("if not defined LLSP_BIN exit /b 127", joined)
        self.assertEqual(server[-2:], ['"%LLSP_BIN%" %LLSP_ARGS%', "exit /b %ERRORLEVEL%"])
        self.assertEqual(code[-1], "exit /b 0")

    def test_which_prints_command(self):
        with tempfile.TemporaryDirectory(prefix="luau-lsp-which-") as tmp:
            e = Env(tmp)
            b = e.rokit("1.70.1")
            p = subprocess.run([str(SH), "--which"], env=e.env(), stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(p.stdout.split()[:3], [str(b), "lsp", "--stdio"])

    def test_ps1_runs_on_windows_powershell(self):
        text = PS1.read_text(encoding="utf-8")
        text.encode("ascii")  # Windows PowerShell 5.1 reads a BOM-less file as the ANSI code page
        code = "\n".join(ln.split("#", 1)[0] for ln in text.splitlines())
        self.assertNotIn("??", code, "?? needs PowerShell 7")
        self.assertNotRegex(code, r"\s\?\s.*\s:\s", "ternary needs PowerShell 7")
        self.assertNotIn("$IsWindows", code, "undefined on Windows PowerShell 5.1")
        outputs = re.findall(r"Write-Output \('([A-Z_]+)=", text)
        self.assertEqual(outputs, ["LLSP_BIN", "LLSP_ARGS"])

    def test_lsp_json_points_at_extensionless_launcher(self):
        import json
        cfg = json.loads((PLUGIN / ".lsp.json").read_text())
        self.assertEqual(cfg["luau"]["command"], "${CLAUDE_PLUGIN_ROOT}/launcher/luau-lsp")
        self.assertTrue(os.access(SH, os.X_OK), "launcher/luau-lsp must be executable")
        self.assertFalse((PLUGIN / "bin").exists(), "a top-level bin/ blocks claude.ai and Cowork installs")


if __name__ == "__main__":
    if not PWSH:
        print("note: no PowerShell (LUAU_LSP_TEST_PWSH or pwsh); find-luau-lsp.ps1 runs are skipped", file=sys.stderr)
    unittest.main()
