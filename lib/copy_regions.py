"""Copy markers in comments: parse them, render a copy region from its canon. Standard library only.
@copy-of: lib/copy_regions.py
Used by tools/sync-copies.py (imported from lib/) and by the qwreey-conventions reuse-check hook (a synced copy).

Markers sit on a line of their own: indentation, a comment prefix (`#`, `//`, `///`, `//!`, `--`), the marker, nothing else.
- whole file: a copy-of marker followed by a repo-relative path within the first 10 lines; the canon may name itself.
- region: a start-replace marker with `<path>#<NAME> [key=value ...]`, then the copied lines, then an end-replace marker.
  The region whose path names its own file is the canon. Paths are relative to the repo root of the file holding the marker.
Options: `value=string` takes the one string literal in the canon region and writes `template` (default `{value}`) with
`{value}` replaced by that string as a double-quoted literal. Without options the canon lines are copied, re-indented.
"""
import ast
import os
import re
import shlex

HEADER_LINES = 10
MARK = re.compile(r"^(?P<indent>[ \t]*)(?:#+|//[/!]?|--)[ \t]*@(?P<kind>start-replace|end-replace)(?![\w-])(?P<rest>.*?)[ \t]*$")
# A path must start like a path, so prose such as "the `@copy-of:` marker" or "<path>" placeholders is not a mark.
FILE_MARK = re.compile(r"@copy-of:[ \t]*([A-Za-z0-9_.][^\s`'\"<>#]*)(#\S*)?")
OPTIONS = {"value", "template"}
STR_LIT = re.compile(r'"((?:[^"\\\n]|\\.)*)"')
SIMPLE_ESC = {"n": "\n", "t": "\t", "r": "\r", "0": "\0", "\\": "\\", '"': '"', "'": "'"}


class MarkError(Exception):
    pass


def file_copy_target(text):
    """Path named by a whole-file copy-of marker in the first 10 lines, or None (a `#NAME` mark is a value copy, not ours)."""
    for line in text.split("\n", HEADER_LINES)[:HEADER_LINES]:
        m = FILE_MARK.search(line)
        if m and not m.group(2):
            return m.group(1).rstrip(".,;)")
    return None


def parse_regions(text):
    """(regions, errors). region: {name, path, opts, start, end, indent, line}; start/end are 0-based marker line indexes.
    errors: [(1-based line, message)] for unpaired or nested markers, bad specs and duplicate names."""
    regions, errors, open_ = [], [], None
    seen = {}
    for i, line in enumerate(text.split("\n")):
        m = MARK.match(line)
        if not m:
            continue
        if m.group("kind") == "end-replace":
            if open_ is None:
                errors.append((i + 1, "end-replace without a start-replace"))
                continue
            open_["end"] = i
            regions.append(open_)
            open_ = None
            continue
        if open_ is not None:
            errors.append((open_["line"], "start-replace without an end-replace before the next start-replace"))
        open_ = None
        rest = m.group("rest")
        if not rest.startswith(":"):
            errors.append((i + 1, "start-replace needs `: <path>#<NAME>`"))
            continue
        try:
            words = shlex.split(rest[1:])
        except ValueError as e:
            errors.append((i + 1, "cannot parse the options: %s" % e))
            continue
        if not words or "#" not in words[0] or words[0].endswith("#"):
            errors.append((i + 1, "start-replace needs `<path>#<NAME>`"))
            continue
        path, name = words[0].rsplit("#", 1)
        opts = {}
        for w in words[1:]:
            k, eq, v = w.partition("=")
            if not eq or k not in OPTIONS:
                errors.append((i + 1, "unknown option %r (known: %s)" % (w, ", ".join(sorted(OPTIONS)))))
            opts[k] = v
        if "value" in opts and opts["value"] != "string":
            errors.append((i + 1, "value=%s is not supported (only value=string)" % opts["value"]))
        if "template" in opts and "value" not in opts:
            errors.append((i + 1, "template needs value=string"))
        if name in seen:
            errors.append((i + 1, "duplicate region name %s (first at line %d)" % (name, seen[name])))
        seen[name] = i + 1
        open_ = {"name": name, "path": path, "opts": opts, "start": i, "end": None, "indent": m.group("indent"), "line": i + 1}
    if open_ is not None:
        errors.append((open_["line"], "start-replace without an end-replace"))
    return regions, errors


def body(lines, region):
    return lines[region["start"] + 1:region["end"]]


def _unescape(s):
    out, i = [], 0
    while i < len(s):
        c = s[i]
        if c != "\\" or i + 1 >= len(s):
            out.append(c)
            i += 1
            continue
        e = s[i + 1]
        if e in SIMPLE_ESC:
            out.append(SIMPLE_ESC[e])
            i += 2
        elif e == "x":
            out.append(chr(int(s[i + 2:i + 4], 16)))
            i += 4
        elif e == "u" and s[i + 2:i + 3] == "{":
            j = s.index("}", i)
            out.append(chr(int(s[i + 3:j], 16)))
            i = j + 1
        elif e == "u":
            out.append(chr(int(s[i + 2:i + 6], 16)))
            i += 6
        else:
            raise MarkError("unknown escape \\%s" % e)
    return "".join(out)


def string_value(lines, suffix):
    """The one string literal in a canon region. Python canon is read with ast (so implicit concatenation is one literal);
    other languages take one double-quoted literal with C-style escapes."""
    src = "\n".join(lines)
    if suffix == ".py":
        indent = min((len(x) - len(x.lstrip()) for x in lines if x.strip()), default=0)
        try:
            tree = ast.parse("\n".join(x[indent:] for x in lines))
        except SyntaxError as e:
            raise MarkError("canon region is not valid Python: %s" % e)
        found = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)]
    else:
        code = "\n".join(x for x in src.split("\n") if not MARK.match(x) and not x.lstrip().startswith(("//", "--", "#")))
        try:
            found = [_unescape(m.group(1)) for m in STR_LIT.finditer(code)]
        except (ValueError, MarkError) as e:
            raise MarkError("cannot read the string literal: %s" % e)
    if len(found) != 1:
        raise MarkError("value=string needs exactly one string literal in the canon region, found %d" % len(found))
    return found[0]


def quote(value):
    """Double-quoted literal valid in Python, Rust, JS/TS and Luau: only escapes all four share (no \\b, \\f or \\uXXXX,
    which Rust rejects); other control characters as \\xHH, which Rust allows up to 0x7F. Non-ASCII stays as UTF-8."""
    out = []
    for c in value:
        if c == "\\":
            out.append("\\\\")
        elif c == '"':
            out.append('\\"')
        elif c == "\n":
            out.append("\\n")
        elif c == "\t":
            out.append("\\t")
        elif c == "\r":
            out.append("\\r")
        elif ord(c) < 0x20 or ord(c) == 0x7F:
            out.append("\\x%02x" % ord(c))
        else:
            out.append(c)
    return '"' + "".join(out) + '"'


def render(region, canon_lines, canon_region, canon_suffix):
    """The lines a copy region should hold."""
    src = body(canon_lines, canon_region)
    ind = region["indent"]
    if region["opts"].get("value") == "string":
        text = region["opts"].get("template", "{value}").replace("{value}", quote(string_value(src, canon_suffix)))
        return [ind + x if x.strip() else x for x in text.split("\n")]
    cind = canon_region["indent"]
    out = []
    for x in src:
        if not x.strip():
            out.append(x)
        else:
            out.append(ind + (x[len(cind):] if x.startswith(cind) else x.lstrip()))
    return out


def repo_root(path, roots=()):
    """The repo root a file's marker paths are relative to: a given root that holds it, else the nearest folder with .git."""
    path = os.path.abspath(path)
    for r in roots:
        r = os.path.abspath(r)
        if path.startswith(r.rstrip(os.sep) + os.sep):
            return r
    d = os.path.dirname(path)
    while True:
        if os.path.exists(os.path.join(d, ".git")):
            return d
        up = os.path.dirname(d)
        if up == d:
            return os.path.dirname(path)
        d = up


def resolve(root, rel):
    return os.path.normpath(os.path.join(root, rel))


def is_canon(region, path, roots=()):
    return resolve(repo_root(path, roots), region["path"]) == os.path.normpath(os.path.abspath(path))


def expected(region, path, roots=(), read=None):
    """Lines a copy region in `path` should hold. Raises MarkError when the canon file or region is missing or is itself a copy."""
    read = read or (lambda p: open(p, encoding="utf-8").read())
    cpath = resolve(repo_root(path, roots), region["path"])
    try:
        ctext = read(cpath)
    except (OSError, UnicodeDecodeError):
        raise MarkError("canon file %s not found" % region["path"])
    cregions, cerr = parse_regions(ctext)
    if cerr:
        raise MarkError("canon file %s has bad markers (line %d: %s)" % (region["path"], cerr[0][0], cerr[0][1]))
    canon = next((r for r in cregions if r["name"] == region["name"]), None)
    if canon is None:
        raise MarkError("canon region %s#%s not found" % (region["path"], region["name"]))
    if not is_canon(canon, cpath, roots):
        raise MarkError("canon region %s#%s is itself a copy of %s" % (region["path"], region["name"], canon["path"]))
    return render(region, ctext.split("\n"), canon, os.path.splitext(cpath)[1].lower())


def sync_text(text, path, roots=(), read=None):
    """(new text, errors). Rewrites only the lines between each copy region's markers. errors: [(line, message)]."""
    regions, errors = parse_regions(text)
    if errors:
        return text, errors
    lines = text.split("\n")
    for r in sorted(regions, key=lambda r: r["start"], reverse=True):
        if is_canon(r, path, roots):
            continue
        try:
            want = expected(r, path, roots, read)
        except MarkError as e:
            errors.append((r["line"], str(e)))
            continue
        lines[r["start"] + 1:r["end"]] = want
    return "\n".join(lines), sorted(errors)
