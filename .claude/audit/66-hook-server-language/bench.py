import http.client, json, os, statistics, subprocess, sys, time
FILE = "/code/Projects/quad/quad-base/test/mock.luau"
TICK = os.sysconf("SC_CLK_TCK")
small = json.dumps({"session_id": "s", "hook_event_name": "PreToolUse", "cwd": "/code/Projects/quad", "tool_name": "Bash", "tool_input": {"command": "ls -la src"}}).encode()
big = json.dumps({"session_id": "s", "hook_event_name": "PostToolUse", "cwd": "/code/Projects/quad", "tool_name": "Bash", "tool_input": {"command": "cat x"}, "tool_response": {"stdout": "한글 출력 줄 abc\n" * 1500, "stderr": ""}}).encode()
edit = json.dumps({"session_id": "s", "hook_event_name": "PostToolUse", "cwd": "/code/Projects/quad", "tool_name": "Edit", "tool_input": {"file_path": FILE, "old_string": "a", "new_string": "b"}}).encode()
cases = [("quiet, small payload (0.2 KB)", "/quiet", small, 3000), ("quiet, big payload (35 KB)", "/quiet", big, 1500), ("edit check (42 KB file)", "/edit", edit, 1000)]


def cpu(pid):
    f = open(f"/proc/{pid}/stat").read().rsplit(")", 1)[1].split()
    return (int(f[11]) + int(f[12])) / TICK


def run(name, cmd, port):
    p = subprocess.Popen(cmd + [str(port)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(0.6)
    print(f"== {name}")
    conn = http.client.HTTPConnection("127.0.0.1", port)
    for label, path, body, n in cases:
        for _ in range(50):
            conn.request("POST", path, body, {"Content-Type": "application/json"}); conn.getresponse().read()
        c0 = cpu(p.pid); lat = []
        for _ in range(n):
            t = time.perf_counter()
            conn.request("POST", path, body, {"Content-Type": "application/json"}); conn.getresponse().read()
            lat.append((time.perf_counter() - t) * 1e6)
        c1 = cpu(p.pid)
        print(f"  {label:32} server CPU {(c1 - c0) / n * 1e6:7.0f} us/req   latency p50 {statistics.median(lat):6.0f} us")
    rss = int([l for l in open(f"/proc/{p.pid}/status") if l.startswith("VmRSS")][0].split()[1]) // 1024
    print(f"  resident memory {rss} MB")
    p.kill()


run("python http.server", ["python3", "-I", "py_server.py"], 47501)
run("rust std + serde_json", ["rs/target/release/hookbench"], 47502)

print("== spawn python per call (today)")
script = open("py_server.py").read().split("class H")[0] + "d=json.load(sys.stdin)\nif d['tool_name']=='Edit': check(d['tool_input']['file_path'])\n"
open("spawn_hook.py", "w").write(script)
for label, body in (("quiet, small payload", small), ("edit check (42 KB file)", edit)):
    cs = []
    for _ in range(40):
        q = subprocess.Popen(["python3", "-I", "-X", "utf8", "spawn_hook.py"], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL)
        q.stdin.write(body); q.stdin.close(); _, _, ru = os.wait4(q.pid, 0)
        cs.append((ru.ru_utime + ru.ru_stime) * 1e6)
    print(f"  {label:32} CPU {statistics.median(cs):7.0f} us/call")
