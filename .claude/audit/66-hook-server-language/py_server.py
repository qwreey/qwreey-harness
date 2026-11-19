"""Python http hook server: stdlib only, keep-alive, the same two routes as the Rust one."""
import json, re, sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HISTORY = re.compile(r"\b(?:H-\d+|D-\d+|20\d\d-\d\d-\d\d)\b")
NON_ASCII = re.compile(r"[^\x00-\x7f]")
TODO = re.compile(r"\bTODO\b")


def check(path):
    hits = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            i = line.find("--")
            if i < 0:
                continue
            c = line[i + 2:]
            hits += bool(HISTORY.search(c)) + bool(NON_ASCII.search(c)) + bool(TODO.search(c))
    return hits


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    wbufsize = -1

    def setup(self):
        super().setup()
        import socket
        self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        data = json.loads(body)
        out = b""
        if self.path == "/edit":
            n = check(data["tool_input"]["file_path"])
            out = json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": f"hits {n}"}}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)
        self.wfile.flush()

    def log_message(self, *a):
        pass


ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
