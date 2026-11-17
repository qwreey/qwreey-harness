#!/usr/bin/env python3
"""라이선스 정본 텍스트를 받아 쓰고 대조한다. 표준 라이브러리만 쓴다(Python 3.11 이상, Windows 포함).

사용: python3 -I -X utf8 license_text.py <명령> ...
  fetch <SPDX-id> [--year Y] [--holder NAME] [--out PATH] [--force] [--fill-appendix]
      정본을 받아 연도, 소유자 자리표시를 채운다. --out 이 없으면 stdout. 자리표시가 남으면 쓰지 않는다.
  check [PATH] [--id ID]
      PATH(기본 LICENSE)를 정본과 대조한다(연도, 소유자 자리와 공백은 무시). 같은 폴더의 manifest license 필드도 본다.
  notice --name X --url U --id ID --files a,b [--copyright "..."] [--text-file F] [--out PATH]
      THIRD_PARTY_NOTICES.md(없으면 만든다)에 절 하나를 더한다. 같은 이름의 절이 있으면 더하지 않는다.
종료 코드: 0 성공, 1 거절 또는 불일치, 2 사용법, 3 정본을 받지 못함.

정본은 GitHub licenses API 의 body, 실패하면 SPDX license-list-data 의 text/<ID>.txt 다. 둘 다 실패하면 멈추고
기억으로 쓰지 않는다: 기억으로 쓴 라이선스 글은 한두 단어나 조항이 어긋나도 아무도 대조하지 않는다.

자리표시 채우기는 "적용 방법" 절(Apache 의 APPENDIX, GNU 의 How to Apply These Terms) 앞에서만 한다. 그 절은 파일 머리에 붙일
고지의 틀이라 정본 그대로 두는 것이 Apache 와 FSF 의 배포 방식이고, 채워도 대조는 통과한다(--fill-appendix 로 채운다).
"""
import argparse
import datetime
import difflib
import json
import os
import re
import subprocess
import sys
import tomllib
import urllib.error
import urllib.request

GITHUB_URL = "https://api.github.com/licenses/{key}"
SPDX_URL = "https://raw.githubusercontent.com/spdx/license-list-data/main/text/{id}.txt"
TIMEOUT = 20
USER_AGENT = "qwreey-license"

YEAR_TOKENS = ("[year]", "[yyyy]", "<year>")
HOLDER_TOKENS = ("[fullname]", "[name of copyright owner]", "<copyright holders>", "<owner>")
# 소문자 단어로 된 [..] 나 <..>. URL 과 메일(<https://...>)과 대문자가 섞인 글(<signature of Ty Coon>)은 자리표시가 아니다.
PLACEHOLDER = re.compile(r"\[[a-z][a-z ]{1,38}\]|<(?!https?:)[a-z][a-z ]{1,38}>")
TEMPLATE_SECTION = re.compile(r"^[ \t]*(?:APPENDIX: How to apply|How to Apply These Terms)", re.M)
SENT = "\x00"

# SPDX 는 GNU 계열의 꼬리 없는 id 를 폐기했고 파일도 -only 로만 있다. GitHub 은 꼬리 없는 키만 안다.
BARE_GNU = ("GPL-2.0", "GPL-3.0", "LGPL-2.1", "LGPL-3.0", "AGPL-3.0")
# SPDX 파일 이름은 대소문자를 가리므로 흔한 id 는 정식 표기로 돌린다. 목록에 없는 id 는 받은 그대로 쓴다.
KNOWN_IDS = ("MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "ISC", "0BSD", "Zlib", "MPL-2.0", "Unlicense", "BSL-1.0",
             "CC0-1.0", "CC-BY-4.0", "CC-BY-SA-4.0", "EPL-2.0", "WTFPL") + BARE_GNU + tuple(
    g + s for g in BARE_GNU for s in ("-only", "-or-later"))

# 본문으로 id 를 짐작하는 문구(공백을 하나로 접은 글에서 찾는다). 앞의 것이 먼저 이긴다.
DETECT = (
    ("AGPL-3.0", ("GNU AFFERO GENERAL PUBLIC LICENSE", "Version 3")),
    ("LGPL-3.0", ("GNU LESSER GENERAL PUBLIC LICENSE", "Version 3")),
    ("LGPL-2.1", ("GNU LESSER GENERAL PUBLIC LICENSE", "Version 2.1")),
    ("GPL-3.0", ("GNU GENERAL PUBLIC LICENSE", "Version 3")),
    ("GPL-2.0", ("GNU GENERAL PUBLIC LICENSE", "Version 2")),
    ("Apache-2.0", ("Apache License", "Version 2.0")),
    ("MPL-2.0", ("Mozilla Public License Version 2.0",)),
    ("BSD-3-Clause", ("Redistribution and use in source and binary forms", "Neither the name")),
    ("BSD-2-Clause", ("Redistribution and use in source and binary forms",)),
    ("MIT", ("Permission is hereby granted, free of charge",)),
    ("ISC", ("for any purpose with or without fee is hereby granted, provided that the above copyright notice",)),
    ("0BSD", ("for any purpose with or without fee is hereby granted. THE SOFTWARE",)),
    ("Unlicense", ("This is free and unencumbered software released into the public domain",)),
    ("CC-BY-SA-4.0", ("Attribution-ShareAlike 4.0 International",)),
    ("CC-BY-4.0", ("Attribution 4.0 International",)),
    ("CC0-1.0", ("CC0 1.0 Universal",)),
    ("BSL-1.0", ("Boost Software License - Version 1.0",)),
    ("Zlib", ("This software is provided 'as-is'", "Altered source versions must be plainly marked")),
)


class FetchError(Exception):
    pass


def http_get(url):
    """URL 의 본문(UTF-8). 테스트는 이 이름을 가짜로 바꾼다."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read().decode("utf-8")


def canon_id(spdx_id):
    for k in KNOWN_IDS:
        if k.lower() == spdx_id.lower():
            return k
    return spdx_id


def base_id(spdx_id):
    """비교용: 대소문자와 GNU 의 -only, -or-later 꼬리를 뗀다(본문이 같다)."""
    k = spdx_id.strip().lower()
    for suf in ("-only", "-or-later", "+"):
        if k.endswith(suf):
            k = k[: -len(suf)]
    return k


def tidy(text):
    """줄 끝 공백을 지우고 줄바꿈을 \\n 으로, 끝에 줄바꿈 하나."""
    lines = [ln.rstrip() for ln in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(lines).strip("\n") + "\n"


def sources(spdx_id, errors):
    """(출처 이름, 정본) 을 GitHub, SPDX 순으로 낸다. 실패는 errors 에 모은다."""
    sid = canon_id(spdx_id)
    try:
        data = json.loads(http_get(GITHUB_URL.format(key=base_id(sid))))
        body = data.get("body") if isinstance(data, dict) else None
        if not body:
            raise FetchError("no body in response")
        yield "GitHub licenses API", tidy(body)
    except Exception as e:
        errors.append(f"GitHub licenses API: {describe(e)}")
    fid = sid + "-only" if sid in BARE_GNU else sid
    try:
        yield "SPDX license-list-data", tidy(http_get(SPDX_URL.format(id=fid)))
    except Exception as e:
        errors.append(f"SPDX license-list-data: {describe(e)}")


def describe(e):
    if isinstance(e, urllib.error.HTTPError):
        return f"HTTP {e.code}" + (" (not in this list)" if e.code == 404 else " (rate limit?)" if e.code == 403 else "")
    return f"{type(e).__name__}: {e}"


def fetch_failed(spdx_id, errors):
    print(f"Could not fetch the canonical text of {spdx_id}: " + "; ".join(errors) + ".\n"
          "Stop and tell the user. Do not write license text from memory; retry when the network is back, "
          "or check the SPDX id at https://spdx.org/licenses/.", file=sys.stderr)
    return 3


def split_template(text):
    """(본문, 적용 방법 절). 적용 방법 절이 없으면 둘째는 빈 글."""
    m = TEMPLATE_SECTION.search(text)
    return (text[: m.start()], text[m.start():]) if m else (text, "")


def fill(text, year, holder, fill_appendix=False):
    head, tail = split_template(text)

    def sub(part):
        for t in YEAR_TOKENS:
            part = part.replace(t, year)
        for t in HOLDER_TOKENS:
            part = part.replace(t, holder)
        return part

    return sub(head) + (sub(tail) if fill_appendix else tail)


def leftovers(text):
    """적용 방법 절 앞에 남은 자리표시."""
    return sorted(set(PLACEHOLDER.findall(split_template(text)[0])))


def needs(text, whole=False):
    """(연도 자리가 있나, 소유자 자리가 있나). whole 이 아니면 적용 방법 절 앞만 본다."""
    part = text if whole else split_template(text)[0]
    return any(t in part for t in YEAR_TOKENS), any(t in part for t in HOLDER_TOKENS)


def git_user_name():
    try:
        r = subprocess.run(["git", "config", "user.name"], capture_output=True, text=True, timeout=10)
        return r.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


# ---------- 대조 ----------

def words(text, template=False):
    if template:
        text = PLACEHOLDER.sub(SENT, text)
    return text.split()


def title_len(tmpl_words, text):
    """정본 첫 줄이 제목(자리표시 없는 짧은 줄, License 로 끝남)이면 그 단어 수. 없어도 되는 줄로 본다."""
    first = text.lstrip("\n").split("\n", 1)[0].strip()
    if first and len(first) <= 60 and SENT not in PLACEHOLDER.sub(SENT, first) and re.search(r"licen[sc]e\b", first, re.I):
        return len(first.split())
    return 0


def segment_ok(tmpl_seg, file_seg):
    """자리표시를 담은 정본 조각이 파일 조각과 맞는지(자리표시 자리는 아무 글이나)."""
    if not any(SENT in w for w in tmpl_seg) or not file_seg:
        return False
    rx = r"\s+".join("(.+?)".join(re.escape(p) for p in w.split(SENT)) for w in tmpl_seg)
    return re.fullmatch(rx, " ".join(file_seg), re.S) is not None


def compare(template, text):
    """정본 틀과 파일을 단어 단위로 맞춘다. 자리표시 자리와 공백, 첫 줄 제목의 유무는 차이로 치지 않는다.
    받아들이지 못한 차이의 목록 [(정본 단어들, 파일 단어들, 정본 앞뒤, 파일 앞뒤)] 를 돌려준다(비면 같다)."""
    tw, fw = words(template, True), words(text)
    tl = title_len(tw, template)
    sm = difflib.SequenceMatcher(None, tw, fw, autojunk=False)
    bad = []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            continue
        if op == "delete" and i1 == 0 and i2 == tl:
            continue
        if op == "replace" and segment_ok(tw[i1:i2], fw[j1:j2]):
            continue
        if op == "delete" and i1 == 0 and i2 > tl and tl and segment_ok(tw[tl:i2], fw[j1:j2]):
            continue
        bad.append((tw[i1:i2], fw[j1:j2], (tw[max(0, i1 - 6):i1], tw[i2:i2 + 6]), (fw[max(0, j1 - 6):j1], fw[j2:j2 + 6])))
    return bad


def show(ws):
    return " ".join(w.replace(SENT, "<placeholder>") for w in ws)


def print_diff(bad, limit=8):
    for tseg, fseg, (tb, ta), (fb, fa) in bad[:limit]:
        print(f"  canonical: ...{show(tb)} [{show(tseg)}] {show(ta)}...")
        print(f"  file:      ...{show(fb)} [{show(fseg)}] {show(fa)}...")
    if len(bad) > limit:
        print(f"  ({len(bad) - limit} more differences)")


def detect_id(text):
    flat = " ".join(text.split())
    for sid, phrases in DETECT:
        if all(p in flat for p in phrases):
            return sid
    return None


# ---------- manifest ----------

def manifest_licenses(folder):
    """[(파일, license 값)] : 같은 폴더의 package.json, .claude-plugin/plugin.json, pyproject.toml, Cargo.toml."""
    out = []

    def load_json(rel):
        p = os.path.join(folder, rel)
        if not os.path.isfile(p):
            return None
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError):
            out.append((rel, None))
            return None

    def load_toml(rel):
        p = os.path.join(folder, rel)
        if not os.path.isfile(p):
            return None
        try:
            with open(p, "rb") as f:
                return tomllib.load(f)
        except (OSError, tomllib.TOMLDecodeError):
            out.append((rel, None))
            return None

    for rel in ("package.json", os.path.join(".claude-plugin", "plugin.json")):
        d = load_json(rel)
        if isinstance(d, dict):
            v = d.get("license")
            if isinstance(v, dict):
                v = v.get("type")
            if isinstance(v, str):
                out.append((rel, v))
    d = load_toml("pyproject.toml")
    if isinstance(d, dict):
        for v in ((d.get("project") or {}).get("license"), ((d.get("tool") or {}).get("poetry") or {}).get("license")):
            if isinstance(v, dict):
                v = v.get("text")
            if isinstance(v, str):
                out.append(("pyproject.toml", v))
    d = load_toml("Cargo.toml")
    if isinstance(d, dict):
        v = (d.get("package") or {}).get("license")
        if isinstance(v, str):
            out.append(("Cargo.toml", v))
    return out


def expression_ids(expr):
    return [t for t in re.split(r"\s+(?:OR|AND|WITH)\s+|[()\s]+", expr.strip()) if t]


def check_manifests(folder, sid):
    """불일치 줄들."""
    problems = []
    for rel, value in manifest_licenses(folder):
        if value is None:
            problems.append(f"{rel}: could not parse")
        elif value.startswith("SEE LICENSE IN"):
            continue
        elif value.upper() == "UNLICENSED":
            problems.append(f"{rel}: license is UNLICENSED (npm: proprietary, no use granted) but the file is {sid}")
        elif base_id(sid) not in (base_id(t) for t in expression_ids(value)):
            problems.append(f"{rel}: license \"{value}\" does not name {sid}")
        elif len(expression_ids(value)) > 1:
            print(f"note: {rel}: \"{value}\" names more than one license; this file covers {sid} only")
    return problems


# ---------- 명령 ----------

def cmd_fetch(a):
    errors = []
    src = next(sources(a.id, errors), None)
    if src is None:
        return fetch_failed(a.id, errors)
    name, text = src
    need_year, need_holder = needs(text, a.fill_appendix)
    holder = a.holder
    if need_holder and not holder:
        holder = git_user_name()
        if not holder:
            print("No --holder and no git config user.name. Ask the user who holds the copyright and pass --holder.",
                  file=sys.stderr)
            return 1
        print(f"holder: {holder} (from git config user.name; confirm it with the user)", file=sys.stderr)
    year = a.year or str(datetime.date.today().year)
    text = fill(text, year, holder or "", a.fill_appendix)
    left = leftovers(text)
    if left:
        print(f"Refusing: placeholders remain in the {canon_id(a.id)} text from {name}: {', '.join(left)}. "
              "This license needs a value the script does not fill; tell the user.", file=sys.stderr)
        return 1
    print(f"source: {name} ({canon_id(a.id)})", file=sys.stderr)
    if not (need_year or need_holder):
        print("note: this text has no copyright line to fill, so --year and --holder were not used; put the copyright "
              "notice where the license's own instructions say (file headers, README, NOTICE).", file=sys.stderr)
    if split_template(text)[1] and not a.fill_appendix and PLACEHOLDER.search(split_template(text)[1]):
        print("note: the how-to-apply section keeps its placeholders verbatim (it is a template for file headers).",
              file=sys.stderr)
    if not a.out:
        sys.stdout.write(text)
        return 0
    if os.path.exists(a.out) and not a.force:
        print(f"Refusing: {a.out} exists. Run check on it, or pass --force after the user agrees to replace it.",
              file=sys.stderr)
        return 1
    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(f"wrote {a.out}", file=sys.stderr)
    return 0


def cmd_check(a):
    path = a.path
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError as e:
        print(f"Cannot read {path}: {e}", file=sys.stderr)
        return 1
    folder = os.path.dirname(os.path.abspath(path))
    sid = a.id
    if not sid:
        sid = detect_id(text)
        if not sid:
            ids = {t for _, v in manifest_licenses(folder) if v for t in expression_ids(v)}
            sid = next(iter(ids)) if len(ids) == 1 else None
        if not sid:
            print(f"Cannot tell which license {path} is; pass --id <SPDX-id>.", file=sys.stderr)
            return 1
        print(f"license: {sid} (detected; pass --id to override)")
    status = 0
    errors, first_bad, matched, matched_tmpl = [], None, None, None
    for name, tmpl in sources(sid, errors):
        bad = compare(tmpl, text)
        if not bad:
            matched, matched_tmpl = name, tmpl
            break
        if first_bad is None:
            first_bad = (name, bad)
    if matched:
        print(f"{path}: matches the canonical {canon_id(sid)} text ({matched})")
    elif first_bad:
        name, bad = first_bad
        print(f"{path}: differs from the canonical {canon_id(sid)} text ({name}) in {len(bad)} place(s):")
        print_diff(bad)
        status = 1
    else:
        return fetch_failed(sid, errors)
    left = leftovers(text)
    if left:
        print(f"{path}: placeholders not filled: {', '.join(left)}")
        status = 1
    if matched_tmpl is not None and any(needs(matched_tmpl)):
        for line in (ln.strip() for ln in split_template(text)[0].split("\n")):
            if re.match(r"(?i)copyright\b.*\d", line) and not PLACEHOLDER.search(line):
                print(f"copyright line: {line}")
    problems = check_manifests(folder, sid)
    for p in problems:
        print(f"manifest mismatch: {p}")
    return 1 if problems else status


def fence_for(text):
    longest = max((len(m) for m in re.findall(r"`+", text)), default=0)
    return "`" * max(3, longest + 1)


def section_span(doc, name):
    """'## name' 절의 (시작, 끝). 없으면 None."""
    m = re.search(r"^## " + re.escape(name) + r"[ \t]*$", doc, re.M)
    if not m:
        return None
    n = re.search(r"^## ", doc[m.end():], re.M)
    return m.start(), (m.end() + n.start()) if n else len(doc)


def cmd_notice(a):
    if a.text_file:
        with open(a.text_file, encoding="utf-8", errors="replace") as f:
            text = tidy(f.read())
        name = a.text_file
    else:
        errors = []
        src = next(sources(a.id, errors), None)
        if src is None:
            return fetch_failed(a.id, errors)
        name, text = src
        head, tail = split_template(text)
        lines = head.split("\n")
        idx = [i for i, ln in enumerate(lines) if PLACEHOLDER.search(ln)]
        if idx and not a.copyright:
            print(f"Refusing: the {canon_id(a.id)} text has a copyright line to fill. Copy the upstream project's "
                  "copyright line from its LICENSE and pass it as --copyright.", file=sys.stderr)
            return 1
        if a.copyright:
            if len(idx) > 1:
                print(f"Refusing: the {canon_id(a.id)} text has placeholders on {len(idx)} lines; use --text-file with "
                      "the upstream LICENSE instead.", file=sys.stderr)
                return 1
            if idx:
                lines[idx[0]] = a.copyright
                head = "\n".join(lines)
            else:
                head = a.copyright.rstrip() + "\n\n" + head
            text = head + tail
    left = leftovers(text)
    if left:
        print(f"Refusing: placeholders remain in the notice text: {', '.join(left)}.", file=sys.stderr)
        return 1
    files = [f.strip() for f in a.files.split(",") if f.strip()]
    fence = fence_for(text)
    section = (f"## {a.name}\n\nFiles:\n" + "".join(f"- `{f}`\n" for f in files)
               + f"\nSource: {a.url} ({canon_id(a.id)}).\n\n{fence}\n{text.rstrip()}\n{fence}\n")
    out = a.out
    doc = ""
    if os.path.exists(out):
        with open(out, encoding="utf-8") as f:
            doc = f.read().replace("\r\n", "\n")
    span = section_span(doc, a.name)
    if span:
        if doc[span[0]:span[1]].strip() == section.strip():
            print(f"{out}: section \"{a.name}\" already present, unchanged")
            return 0
        print(f"{out}: a section \"{a.name}\" already exists with different content; not changed. Show the user the "
              "difference; edit or remove that section first if it should be replaced.", file=sys.stderr)
        return 1
    if not doc.strip():
        doc = "# Third-party notices\n"
    doc = doc.rstrip("\n") + "\n\n" + section
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        f.write(doc)
    print(f"{out}: added section \"{a.name}\" ({name})")
    return 0


def parser():
    p = argparse.ArgumentParser(prog="license_text.py", description="Fetch, fill and check canonical license texts.")
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch", help="fetch the canonical text and fill year and holder")
    f.add_argument("id", help="SPDX id, e.g. MIT, Apache-2.0, BSD-3-Clause")
    f.add_argument("--year", help="copyright year (default: this year)")
    f.add_argument("--holder", help="copyright holder (default: git config user.name; confirm with the user)")
    f.add_argument("--out", help="file to write (default: stdout)")
    f.add_argument("--force", action="store_true", help="overwrite --out if it exists")
    f.add_argument("--fill-appendix", action="store_true", help="also fill the how-to-apply section's placeholders")
    c = sub.add_parser("check", help="compare a license file with the canonical text and manifest license fields")
    c.add_argument("path", nargs="?", default="LICENSE")
    c.add_argument("--id", help="SPDX id (default: detect from the text or the manifests)")
    n = sub.add_parser("notice", help="append a third-party notice section")
    n.add_argument("--name", required=True, help="section title, e.g. the upstream project name")
    n.add_argument("--url", required=True, help="upstream source URL")
    n.add_argument("--id", required=True, help="SPDX id of the upstream license")
    n.add_argument("--files", required=True, help="comma-separated paths in this repo that carry the third-party work")
    n.add_argument("--copyright", help="the upstream copyright line, copied from its LICENSE")
    n.add_argument("--text-file", help="use this file (the upstream LICENSE) as the text instead of the canonical one")
    n.add_argument("--out", default="THIRD_PARTY_NOTICES.md")
    return p


def main(argv=None):
    a = parser().parse_args(argv)
    return {"fetch": cmd_fetch, "check": cmd_check, "notice": cmd_notice}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
