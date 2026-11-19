#!/usr/bin/env python3
"""mise shim 실패 안내: Bash 출력에 mise 의 "No version is set for shim: <이름>" 이 있으면, 설치된 실제 실행 파일 경로를 찾아
모델에게 info 로 알린다(PostToolUseFailure:Bash 만. shim 실패는 exit 1 이라 거기로 오고, 성공한 Bash 마다 python 을 띄우지 않는다).
상시 규약에 한 줄을 두는 대신 그 오류가 났을 때만 싣는다(Q36 a). 파이프 끝이 성공해 exit 0 이 된 경우는 놓친다.

- 설치 폴더: harness.env 층의 HARNESS_TOOL_INSTALLS(기본 ~/.local/share/mise/installs), 비면 $MISE_DATA_DIR/installs.
- <설치 폴더>/<도구>/<버전>/ 아래 바로, 또는 bin/ 에 shim 과 같은 이름(Windows 는 .exe, .cmd 도)이 있으면 후보다.
  `7`, `latest` 같은 별칭 버전 폴더(심볼릭 링크)는 건너뛴다. 오류가 제안한 `mise use -g <도구>@<버전>` 의 버전을 앞에 둔다.
- `mise use -g` 는 사용자의 전역 도구 버전을 바꾸므로 묻고 나서 하라고 적는다.
어떤 실패든 아무것도 내지 않고 exit 0(훅은 세션을 막지 않는다).
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)  # python3 -I 는 스크립트 디렉터리를 path 에 넣지 않는다

SHIM = re.compile(r"No version is set for shim: ([A-Za-z0-9._+-]+)")
SUGGEST = re.compile(r"mise use -g ([A-Za-z0-9._:/+-]+)@([A-Za-z0-9._+-]+)")
EXTS = ("", ".exe", ".cmd")
MAX_PATHS = 3


def output_text(data):
    """훅 입력에서 명령 출력 글: PostToolUseFailure 의 error, PostToolUse 의 tool_response."""
    parts = []
    err = data.get("error")
    if isinstance(err, str):
        parts.append(err)
    resp = data.get("tool_response")
    if isinstance(resp, dict):
        parts.extend(v for k, v in resp.items() if k in ("stdout", "stderr", "output") and isinstance(v, str))
    elif isinstance(resp, str):
        parts.append(resp)
    return "\n".join(parts)


def load_env(cwd=None):
    """harness.env 층({키: 값}). HARNESS_TOOL_INSTALLS 는 USER_ONLY 라 저장소 층이 바꾸지 못한다."""
    import harness_env
    return harness_env.load_layers(harness_env.project_dir(cwd))


def installs_dir(cwd=None):
    """mise 설치 폴더, 없으면 None."""
    try:
        path = str(load_env(cwd).get("HARNESS_TOOL_INSTALLS") or "")
    except Exception:
        path = ""
    if not path and os.environ.get("MISE_DATA_DIR"):
        path = os.path.join(os.environ["MISE_DATA_DIR"], "installs")
    path = os.path.expanduser(path) if path else ""
    return path if path and os.path.isdir(path) else None


def find_binaries(root, shim, prefer=None):
    """[실행 파일 경로]: 제안된 (도구 폴더 꼬리, 버전) 이 먼저, 그다음 이름순, 최대 MAX_PATHS 개."""
    found = []
    for tool in sorted(os.listdir(root)):
        tool_dir = os.path.join(root, tool)
        if not os.path.isdir(tool_dir):
            continue
        for ver in sorted(os.listdir(tool_dir), reverse=True):
            ver_dir = os.path.join(tool_dir, ver)
            if os.path.islink(ver_dir) or not os.path.isdir(ver_dir):
                continue
            for sub in ("", "bin"):
                hit = next((p for p in (os.path.join(ver_dir, sub, shim + e) for e in EXTS) if os.path.isfile(p)), None)
                if hit:
                    found.append((tool, ver, hit))
                    break

    # Suggested tool and version first
    def rank(item):
        tool, ver, _ = item
        if not prefer:
            return (1, 1)
        want_tool = re.sub(r"[^A-Za-z0-9]+", "-", prefer[0]).strip("-").lower()
        return (0 if tool.lower().endswith(want_tool) else 1, 0 if ver == prefer[1] else 1)

    return [p for _, _, p in sorted(found, key=rank)[:MAX_PATHS]]


def message(shim, paths, prefer, nonce_attr=""):
    """info 태그 하나."""
    lines = ['<harness-hook name="mise-hint" level="info"%s>' % nonce_attr,
             "mise found no version for the shim `%s` here (no mise.toml or global default pins it)." % shim]
    if paths:
        lines.append("Installed copies: " + ", ".join("`%s`" % p for p in paths) + ".")
        lines.append("Consider calling one of those paths directly"
                     + (", or `mise exec %s@%s -- %s ...`." % (prefer[0], prefer[1], shim) if prefer else "."))
    else:
        lines.append("No installed copy was found under the mise installs folder; `mise install` may be needed.")
    lines.append("`mise use -g` changes the user's global tool versions; ask before running it.")
    lines.append("</harness-hook>")
    return "\n".join(lines)


def main():
    try:
        data = json.load(sys.stdin)
        if not isinstance(data, dict) or data.get("tool_name") not in (None, "Bash"):
            return

        # Only the mise shim error
        text = output_text(data)
        m = SHIM.search(text)
        if not m:
            return
        shim = m.group(1)
        s = SUGGEST.search(text)
        prefer = (s.group(1), s.group(2)) if s else None

        # Installed copies and the message
        root = installs_dir(data.get("cwd"))
        paths = find_binaries(root, shim, prefer) if root else []
        try:
            import harness_nonce
            attr = harness_nonce.attr(data.get("session_id"))
        except Exception:
            attr = ""
        event = data.get("hook_event_name") or "PostToolUse"
        out = {"hookSpecificOutput": {"hookEventName": event, "additionalContext": message(shim, paths, prefer, attr)}}
        sys.stdout.write(json.dumps(out))
    except Exception:
        return


if __name__ == "__main__":
    main()
