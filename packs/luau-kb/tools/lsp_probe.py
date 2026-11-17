#!/usr/bin/env python3
"""luau-lsp DX 프로브. luau-lsp 에는 hover/자동완성을 CLI 로 묻는 명령이 없어서, 서버를 stdio 로 잠깐 띄워
initialize -> didOpen -> 요청 -> shutdown 을 한 번 돈다. 표준 라이브러리만 쓴다.

사용:
  python3 -I tools/lsp_probe.py FILE [질의...] [옵션]
질의 (여러 번 줄 수 있다, 순서대로 실행):
  --hover POS        그 자리의 hover 내용(추론 타입, 문서 주석)
  --complete POS     그 자리의 자동완성 목록(label, kind, detail)
  --inlay            파일 전체의 inlay hint(변수·매개변수·반환의 추론 타입)
  --diagnostics      pull 진단(textDocument/diagnostic)
  --symbols          문서 심볼
POS 형식:
  12:7               1부터 세는 줄:열 (에디터 표시와 같다)
  'text'             파일에서 처음 나오는 text. hover 는 text 의 시작, complete 는 text 의 끝 자리
  'text'@N           N 번째(1부터) 등장
옵션:
  --lsp VER|PATH     luau-lsp 버전(기본 1.70.1, $MISE_DATA_DIR/installs/github-johnny-morganz-luau-lsp/<VER>)이나 바이너리 경로
  --platform standard|roblox   기본 standard
  --defs PATH        정의 파일(roblox 면 보통 typedefs/globalTypes.d.luau). 여러 번 가능
  --sourcemap PATH   Rojo sourcemap.json (workspace 루트에 복사하지 않고 설정으로 넘긴다)
  --root DIR         workspace 루트(기본: FILE 의 디렉터리). .luaurc 는 여기서 찾는다
  --old-solver       옛 솔버로 (기본은 LuauSolverV2=true)
  --flag K=V         Luau FFlag 추가
  --no-config        설정을 보내지 않는다(workspace/configuration 에 null). 서버 기본값과 --settings 파일만 쓰는
                     클라이언트(예: Claude Code 의 .lsp.json 에 settings 가 없을 때)를 흉내 낸다
  --raw-argv         --lsp 로 준 실행 파일을 인자 없이 부른다(.sh 래퍼 시험용; 아니면 `lsp --stdio` 만 붙임).
                     --defs/--platform/--flag 는 무시된다
  --json             결과를 JSON 으로
  --limit N          자동완성 표시 개수(기본 40)
  --no-filter        자동완성을 커서 앞 식별자로 거르지 않는다(서버는 접두어와 무관한 전체 후보를 준다)
종료 코드: 0 정상, 2 서버 오류/시간 초과, 3 질의 결과가 비어 있음(--expect-nonempty 일 때).
mise shim 은 쓰지 않는다(버전 미지정 디렉터리에서 실패한다).
"""
import argparse
import json
import os
import re
import subprocess
import sys
import threading
import time
import queue

MISE = os.environ.get("MISE_DATA_DIR") or os.path.expanduser("~/.local/share/mise")
DEFAULT_LSP = os.environ.get("LUAU_LSP_VERSION", "1.70.1")

COMPLETION_KIND = {
    1: "Text", 2: "Method", 3: "Function", 4: "Constructor", 5: "Field", 6: "Variable", 7: "Class",
    8: "Interface", 9: "Module", 10: "Property", 11: "Unit", 12: "Value", 13: "Enum", 14: "Keyword",
    15: "Snippet", 16: "Color", 17: "File", 18: "Reference", 19: "Folder", 20: "EnumMember",
    21: "Constant", 22: "Struct", 23: "Event", 24: "Operator", 25: "TypeParameter",
}


def resolve_lsp(spec):
    if os.sep in spec:
        return spec
    return os.path.join(MISE, "installs", "github-johnny-morganz-luau-lsp", spec, "luau-lsp")


def file_uri(path):
    return "file://" + os.path.abspath(path)


class Server:
    def __init__(self, argv, settings, cwd):
        self.p = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, cwd=cwd)
        self.settings = settings
        self.next_id = 0
        self.pending = {}
        self.notes = queue.Queue()
        self.stderr = []
        threading.Thread(target=self._read, daemon=True).start()
        threading.Thread(target=self._drain_err, daemon=True).start()

    def _drain_err(self):
        for line in self.p.stderr:
            self.stderr.append(line.decode("utf-8", "replace"))

    def _send(self, msg):
        body = json.dumps(msg).encode("utf-8")
        self.p.stdin.write(b"Content-Length: %d\r\n\r\n" % len(body) + body)
        self.p.stdin.flush()

    def _read(self):
        f = self.p.stdout
        while True:
            headers = {}
            while True:
                line = f.readline()
                if not line:
                    return
                line = line.strip()
                if not line:
                    break
                k, _, v = line.decode("ascii", "replace").partition(":")
                headers[k.strip().lower()] = v.strip()
            n = int(headers.get("content-length", "0"))
            msg = json.loads(f.read(n).decode("utf-8"))
            if "id" in msg and "method" in msg:
                self._answer_server_request(msg)
            elif "id" in msg:
                slot = self.pending.get(msg["id"])
                if slot is not None:
                    slot.put(msg)
            else:
                self.notes.put(msg)

    def _answer_server_request(self, msg):
        method = msg["method"]
        result = None
        if method == "workspace/configuration" and self.settings is None:
            result = [None for _ in msg.get("params", {}).get("items", [])]
        elif method == "workspace/configuration":
            result = []
            for item in msg.get("params", {}).get("items", []):
                section = item.get("section")
                result.append(self.settings.get(section, {}) if section else self.settings)
        self._send({"jsonrpc": "2.0", "id": msg["id"], "result": result})

    def request(self, method, params, timeout=60):
        self.next_id += 1
        rid = self.next_id
        slot = queue.Queue()
        self.pending[rid] = slot
        self._send({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        try:
            msg = slot.get(timeout=timeout)
        except queue.Empty:
            raise TimeoutError(f"{method}: {timeout}s 안에 응답 없음")
        finally:
            self.pending.pop(rid, None)
        if "error" in msg:
            raise RuntimeError(f"{method}: {msg['error']}")
        return msg.get("result")

    def notify(self, method, params):
        self._send({"jsonrpc": "2.0", "method": method, "params": params})

    def close(self):
        try:
            self.request("shutdown", None, timeout=10)
            self.notify("exit", None)
        except Exception:
            pass
        try:
            self.p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.p.kill()


def to_position(text, spec, for_completion):
    """반환: (0 기반 line, 0 기반 UTF-16 character). 입력 줄:열은 1 기반."""
    m = re.fullmatch(r"(\d+):(\d+)", spec)
    lines = text.split("\n")
    if m:
        line, col = int(m.group(1)) - 1, int(m.group(2)) - 1
    else:
        m2 = re.fullmatch(r"(.*?)(?:@(\d+))?", spec, re.S)
        needle, nth = m2.group(1), int(m2.group(2) or 1)
        idx = -1
        for _ in range(nth):
            idx = text.find(needle, idx + 1)
            if idx < 0:
                raise SystemExit(f"lsp_probe: '{needle}' 를 {nth}번째로 찾지 못했다")
        if for_completion:
            idx += len(needle)
        line = text.count("\n", 0, idx)
        col = idx - (text.rfind("\n", 0, idx) + 1)
    if line >= len(lines):
        raise SystemExit(f"lsp_probe: {line + 1}번째 줄이 없다")
    prefix = lines[line][:col]
    return line, len(prefix.encode("utf-16-le")) // 2


def hover_text(result):
    if not result:
        return ""
    c = result.get("contents")
    if isinstance(c, dict):
        return c.get("value", "")
    if isinstance(c, list):
        return "\n".join(x if isinstance(x, str) else x.get("value", "") for x in c)
    return str(c)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file")
    ap.add_argument("--hover", action="append", default=[], dest="hover")
    ap.add_argument("--complete", action="append", default=[])
    ap.add_argument("--inlay", action="store_true")
    ap.add_argument("--diagnostics", action="store_true")
    ap.add_argument("--symbols", action="store_true")
    ap.add_argument("--lsp", default=DEFAULT_LSP)
    ap.add_argument("--platform", choices=["standard", "roblox"], default="standard")
    ap.add_argument("--defs", action="append", default=[])
    ap.add_argument("--sourcemap")
    ap.add_argument("--root")
    ap.add_argument("--old-solver", action="store_true")
    ap.add_argument("--flag", action="append", default=[])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--no-filter", action="store_true")
    ap.add_argument("--no-config", action="store_true")
    ap.add_argument("--raw-argv", action="store_true")
    ap.add_argument("--expect-nonempty", action="store_true")
    ap.add_argument("--timeout", type=int, default=60)
    a = ap.parse_args()

    path = os.path.abspath(a.file)
    text = open(path, encoding="utf-8").read()
    root = os.path.abspath(a.root or os.path.dirname(path))
    lsp = resolve_lsp(a.lsp)
    if not os.path.isfile(lsp):
        print(f"lsp_probe: luau-lsp 가 없다: {lsp}", file=sys.stderr)
        return 2

    solver = "false" if a.old_solver else "true"
    argv = [lsp, "lsp", "--stdio", f"--flag:LuauSolverV2={solver}"]
    argv += [f"--flag:{f}" for f in a.flag]
    for d in a.defs:
        argv.append(f"--definitions=@roblox={os.path.abspath(d)}" if a.platform == "roblox"
                    else f"--definitions={os.path.abspath(d)}")

    settings = {
        "luau-lsp": {
            "platform": {"type": a.platform},
            "sourcemap": {"enabled": bool(a.sourcemap), "autogenerate": False,
                          "sourcemapFile": os.path.relpath(os.path.abspath(a.sourcemap), root) if a.sourcemap else "sourcemap.json"},
            "fflags": {"enableNewSolver": not a.old_solver, "sync": False},
            "inlayHints": {"variableTypes": True, "parameterTypes": True, "functionReturnTypes": True,
                           "parameterNames": "none", "hideHintsForErrorTypes": False},
            "diagnostics": {"workspace": False},
            "completion": {"enabled": True, "autocompleteEnd": False, "suggestImports": False},
            "hover": {"enabled": True, "showTableKinds": False, "multilineFunctionDefinitions": False,
                      "strictDatamodelTypes": True, "includeStringLength": True},
        }
    }

    if a.raw_argv:
        argv = [lsp] + (["lsp", "--stdio"] if not lsp.endswith(".sh") else [])
    srv = Server(argv, None if a.no_config else settings, root)
    out = {"server": lsp, "platform": a.platform, "solver": "old" if a.old_solver else "new", "file": path, "results": []}
    uri = file_uri(path)
    rc = 0
    try:
        init = srv.request("initialize", {
            "processId": os.getpid(),
            "rootUri": file_uri(root),
            "workspaceFolders": [{"uri": file_uri(root), "name": os.path.basename(root)}],
            "capabilities": {
                "workspace": {"configuration": True, "didChangeConfiguration": {"dynamicRegistration": False}},
                "textDocument": {
                    "hover": {"contentFormat": ["markdown", "plaintext"]},
                    "completion": {"completionItem": {"snippetSupport": False, "documentationFormat": ["markdown", "plaintext"]}},
                    "inlayHint": {}, "diagnostic": {}, "documentSymbol": {"hierarchicalDocumentSymbolSupport": True},
                },
            },
            "initializationOptions": {},
        }, timeout=a.timeout)
        out["serverInfo"] = (init or {}).get("serverInfo")
        srv.notify("initialized", {})
        if not a.no_config:
            srv.notify("workspace/didChangeConfiguration", {"settings": settings})
        srv.notify("textDocument/didOpen", {"textDocument": {"uri": uri, "languageId": "luau", "version": 1, "text": text}})
        doc = {"textDocument": {"uri": uri}}

        for spec in a.hover:
            line, ch = to_position(text, spec, False)
            r = srv.request("textDocument/hover", {**doc, "position": {"line": line, "character": ch}}, a.timeout)
            out["results"].append({"kind": "hover", "at": spec, "pos": f"{line + 1}:{ch + 1}", "value": hover_text(r)})
        for spec in a.complete:
            line, ch = to_position(text, spec, True)
            r = srv.request("textDocument/completion", {**doc, "position": {"line": line, "character": ch},
                                                        "context": {"triggerKind": 1}}, a.timeout)
            items = r.get("items", []) if isinstance(r, dict) else (r or [])
            total = len(items)
            # 서버는 접두어와 무관한 전체 후보를 준다. 에디터처럼 커서 앞 식별자로 거른다(--no-filter 로 끔).
            word = re.search(r"[A-Za-z_][A-Za-z0-9_]*$", text.split("\n")[line][:ch])
            if word and not a.no_filter:
                pre = word.group(0).lower()
                items = [it for it in items if (it.get("filterText") or it.get("label", "")).lower().startswith(pre)]
            items = sorted(items, key=lambda it: (it.get("sortText") or it.get("label", "")))
            out["results"].append({"kind": "complete", "at": spec, "pos": f"{line + 1}:{ch + 1}", "count": len(items),
                                   "serverCount": total,
                                   "value": [{"label": it.get("label"), "kind": COMPLETION_KIND.get(it.get("kind"), it.get("kind")),
                                              "detail": it.get("detail")} for it in items]})
        if a.inlay:
            n = len(text.split("\n"))
            r = srv.request("textDocument/inlayHint", {**doc, "range": {"start": {"line": 0, "character": 0},
                                                                         "end": {"line": n, "character": 0}}}, a.timeout) or []
            hints = []
            for h in r:
                label = h.get("label")
                if isinstance(label, list):
                    label = "".join(p.get("value", "") for p in label)
                hints.append({"pos": f"{h['position']['line'] + 1}:{h['position']['character'] + 1}", "label": label})
            out["results"].append({"kind": "inlay", "value": hints})
        if a.diagnostics:
            r = srv.request("textDocument/diagnostic", doc, a.timeout) or {}
            diags = [{"pos": f"{d['range']['start']['line'] + 1}:{d['range']['start']['character'] + 1}",
                      "code": d.get("code"), "message": d.get("message")} for d in r.get("items", [])]
            out["results"].append({"kind": "diagnostics", "value": diags})
        if a.symbols:
            r = srv.request("textDocument/documentSymbol", doc, a.timeout) or []

            def flat(syms, depth=0):
                for s in syms:
                    yield {"name": s.get("name"), "detail": s.get("detail"), "depth": depth}
                    yield from flat(s.get("children") or [], depth + 1)
            out["results"].append({"kind": "symbols", "value": list(flat(r))})
    except (TimeoutError, RuntimeError) as e:
        out["error"] = str(e)
        rc = 2
    finally:
        srv.close()
    out["stderr"] = "".join(srv.stderr[-20:])

    if a.expect_nonempty and rc == 0 and any(not r["value"] for r in out["results"]):
        rc = 3
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        info = out.get("serverInfo") or {}
        print(f"# {info.get('name', 'luau-lsp')} {info.get('version', '?')} · platform={a.platform} · solver={out['solver']}")
        for r in out["results"]:
            if r["kind"] == "hover":
                print(f"## hover {r['at']} ({r['pos']})\n{r['value'] or '(없음)'}")
            elif r["kind"] == "complete":
                print(f"## complete {r['at']} ({r['pos']}) — {r['count']}개 (서버 후보 {r['serverCount']}개)")
                for it in r["value"][: a.limit]:
                    print(f"  {it['label']:<28} {it['kind']!s:<10} {it['detail'] or ''}")
            elif r["kind"] == "inlay":
                print("## inlay")
                for h in r["value"]:
                    print(f"  {h['pos']:<8} {h['label']}")
            elif r["kind"] == "diagnostics":
                print(f"## diagnostics — {len(r['value'])}건")
                for d in r["value"]:
                    print(f"  {d['pos']:<8} {d['code']}: {d['message']}")
            elif r["kind"] == "symbols":
                print("## symbols")
                for s in r["value"]:
                    print(f"  {'  ' * s['depth']}{s['name']}  {s['detail'] or ''}")
        if "error" in out:
            print(f"## 오류: {out['error']}\n{out['stderr']}", file=sys.stderr)
    return rc


if __name__ == "__main__":
    sys.exit(main())
