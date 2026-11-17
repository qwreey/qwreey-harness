#!/usr/bin/env python3
"""Live smoke test: start launcher/luau-lsp with the luau-lsp this machine has, send initialize over stdio,
expect a result, then shutdown and exit. Standard and roblox projects (the latter loads the shipped definitions).
Skips when the launcher finds no binary (exit 127). No model calls.
Usage: python3 -I plugins/luau-lsp/tests/test-lsp-smoke.py
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
SH = PLUGIN / "launcher" / "luau-lsp"
TIMEOUT = 30


def send(proc, msg):
    body = json.dumps(msg).encode()
    proc.stdin.write(b"Content-Length: %d\r\n\r\n" % len(body) + body)
    proc.stdin.flush()


def read(proc, deadline):
    headers = {}
    while True:
        if time.monotonic() > deadline:
            raise TimeoutError("no LSP message")
        line = proc.stdout.readline()
        if not line:
            raise EOFError("server closed stdout")
        line = line.strip()
        if not line:
            break
        k, _, v = line.decode().partition(":")
        headers[k.lower()] = v.strip()
    return json.loads(proc.stdout.read(int(headers["content-length"])))


def wait_for(proc, msg_id, deadline):
    while True:
        m = read(proc, deadline)
        if m.get("id") == msg_id and "method" not in m:
            return m


class Smoke(unittest.TestCase):
    def run_server(self, rojo):
        with tempfile.TemporaryDirectory(prefix="luau-lsp-smoke-") as proj:
            if rojo:
                Path(proj, "default.project.json").write_text('{"name": "smoke", "tree": {"$className": "DataModel"}}')
            Path(proj, "main.luau").write_text("local x: number = 1\nreturn x\n")
            env = dict(os.environ, CLAUDE_PROJECT_DIR=proj, CLAUDE_PLUGIN_ROOT=str(PLUGIN))
            for k in ("LUAU_LSP_PLATFORM", "LUAU_LSP_DEFS", "LUAU_LSP_DOCS", "LUAU_LSP_LOG"):
                env.pop(k, None)
            proc = subprocess.Popen([str(SH)], cwd=proj, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
            try:
                deadline = time.monotonic() + TIMEOUT
                send(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                    "processId": os.getpid(), "rootUri": Path(proj).as_uri(), "capabilities": {},
                    "workspaceFolders": [{"uri": Path(proj).as_uri(), "name": "smoke"}]}})
                try:
                    init = wait_for(proc, 1, deadline)
                except EOFError:
                    proc.wait(timeout=5)
                    err = proc.stderr.read().decode()
                    if proc.returncode == 127:
                        self.skipTest(f"no luau-lsp on this machine: {err.strip()}")
                    raise AssertionError(f"server exited {proc.returncode}: {err}")
                self.assertIn("capabilities", init.get("result", {}), init)
                send(proc, {"jsonrpc": "2.0", "method": "initialized", "params": {}})
                send(proc, {"jsonrpc": "2.0", "id": 2, "method": "shutdown"})
                self.assertIn("result", wait_for(proc, 2, deadline))
                send(proc, {"jsonrpc": "2.0", "method": "exit"})
                proc.stdin.close()
                self.assertEqual(proc.wait(timeout=10), 0)
                return init
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait()
                for f in (proc.stdin, proc.stdout, proc.stderr):
                    f.close()

    def test_standard(self):
        init = self.run_server(rojo=False)
        print(f"standard: {init['result'].get('serverInfo')}", file=sys.stderr)

    def test_roblox(self):
        init = self.run_server(rojo=True)
        print(f"roblox: {init['result'].get('serverInfo')}", file=sys.stderr)


if __name__ == "__main__":
    unittest.main()
