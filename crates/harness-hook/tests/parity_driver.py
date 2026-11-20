"""harness-hook 바이트 대조 시험(tests/parity.rs)의 python 쪽. 표준 라이브러리만 쓴다.

stdin: {"repo": <저장소 루트>, "cases": [{"op": ..., "env": {...}, "args": {...}}, ...]}
stdout: 경우마다 결과 하나씩 담은 JSON 목록. 정본 모듈(lib/harness_nonce.py, home/.claude/lib/harness_env.py)을
경로로 직접 불러, 경우마다 os.environ 을 그 경우의 환경으로 바꾸고 모듈 캐시를 비운 뒤 부른다.
float 는 JSON 십진 표기를 거치면 1 ULP 어긋날 수 있어 비트(u64)로 주고받는다.
"""
import importlib.util
import json
import os
import struct
import sys


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def from_bits(bits):
    return struct.unpack("<d", struct.pack("<Q", bits))[0]


def run(nonce_mod, env_mod, case):
    os.environ.clear()
    os.environ.update(case.get("env") or {})
    nonce_mod._cache.clear()
    env_mod._JSON.clear()
    env_mod._MANIFEST.clear()
    op, a = case["op"], case.get("args") or {}

    if op == "isspace":
        return [c for c in range(0x110000) if chr(c).isspace()]
    if op == "splitlines":
        return a["text"].splitlines()
    if op == "float_repr":
        return [repr(from_bits(b)) for b in a["bits"]]
    if op == "int_text":
        return [str(int(from_bits(b))) for b in a["bits"]]
    if op == "floor_div":
        return [int(from_bits(b) // nonce_mod.BUCKET_SEC) for b in a["bits"]]
    if op == "dumps":
        return json.dumps(a["value"], ensure_ascii=a["ascii"])
    if op == "expanduser":
        return [os.path.expanduser(p) for p in a["paths"]]
    if op == "pathlib":
        import pathlib
        return [str(pathlib.PurePosixPath(p)) for p in a["paths"]]

    # nonce
    if op == "nonce":
        return [nonce_mod.nonce(sid) for sid in a["sids"]]
    if op == "attr":
        return nonce_mod.attr(a["sid"])
    if op == "claim_path":
        return nonce_mod.claim_path(a["sid"], a.get("agent"), a.get("source"), from_bits(a["now"]))
    if op == "rule_for":
        now = from_bits(a["now"])
        nonce_mod.time.time = lambda: now
        return [nonce_mod.rule_for(ev, data) for ev, data in a["calls"]]
    if op == "redact":
        return nonce_mod.redact_text(a["text"], a.get("sid"))

    # 훅 출력: python 훅이 쓰는 꼴 그대로(self-match-guard 의 tag, heavy-proc-guard 의 deny, lib/ambient.py 의 블록)
    if op == "tag":
        nonce = nonce_mod.attr(a["sid"])
        tag = '<harness-hook name="%s" level="%s"%s>\n%s\n</harness-hook>' % (a["name"], a["level"], nonce, a["body"])
        deny = json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": tag,
        }})
        context = json.dumps({"hookSpecificOutput": {"hookEventName": a["event"], "additionalContext": tag}}, ensure_ascii=False)
        block = '<plugin name="%s"%s>\n' % (a["name"], nonce) + a["body"] + "\n</plugin>"
        return [tag, deny, context, block]

    # 설정 층
    if op == "parse":
        return env_mod.parse(a["text"], a["base"])
    if op == "option_value":
        return [env_mod.option_value(v) for v in a["values"]]
    if op == "load_layers":
        env_mod.__file__ = a["module_file"]  # plugin_manifest() 가 여기서 위로 찾는다
        project = a["project"]
        if isinstance(project, dict):
            project = __import__("pathlib").Path(project["dir"])
        try:
            vals = env_mod.load_layers(project, a.get("candidates"), a.get("defaults"), a.get("user_only") or (), a.get("options"))
        except RuntimeError as e:
            return {"error": str(e)}
        return vals
    if op == "heavy_wrap":
        return env_mod.heavy_wrap(a["values"])
    raise ValueError("unknown op %r" % op)


def main():
    req = json.load(sys.stdin)
    nonce_mod = load("harness_nonce", os.path.join(req["repo"], "lib", "harness_nonce.py"))
    env_mod = load("harness_env", os.path.join(req["repo"], "home", ".claude", "lib", "harness_env.py"))
    json.dump([run(nonce_mod, env_mod, c) for c in req["cases"]], sys.stdout)


if __name__ == "__main__":
    main()
