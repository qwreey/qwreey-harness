#!/usr/bin/env python3
"""license_text.py 회귀. 실행: python3 -I -X utf8 tests/test_license_text.py  (exit 0 = 통과)

네트워크를 쓰지 않는다: http_get 을 fixtures/ 를 읽는 가짜로 바꾼다. fixtures/api 는 GitHub licenses API 의 body,
fixtures/spdx 는 SPDX license-list-data 의 text 를 받은 그대로 둔 것이다.
LICENSE_TEXT_LIVE=1 이면 MIT 와 Apache-2.0 을 실제로 받아 쓰고 대조하는 시험도 돈다(GitHub 이 rate limit 이면 SPDX 로 넘어간다).
"""
import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures")
SCRIPT = os.path.join(os.path.dirname(HERE), "scripts", "license_text.py")

spec = importlib.util.spec_from_file_location("license_text", SCRIPT)
lt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lt)
REAL_GET = lt.http_get


def fixture(*parts):
    with open(os.path.join(FIX, *parts), encoding="utf-8") as f:
        return f.read()


def not_found(url):
    return urllib.error.HTTPError(url, 404, "Not Found", None, None)


def fake_get(api=True, spdx=True, override=None):
    """fixtures 를 돌려주는 http_get. override 는 {URL 끝 조각: 본문}."""
    def get(url):
        tail = url.rsplit("/", 1)[1]
        if override and tail in override:
            return override[tail]
        if url.startswith("https://api.git" + "hub.com/licenses/"):
            p = os.path.join(FIX, "api", tail + ".txt")
            if not api:
                raise urllib.error.URLError("offline")
            if not os.path.exists(p):
                raise not_found(url)
            return json.dumps({"body": fixture("api", tail + ".txt")})
        if not spdx:
            raise urllib.error.URLError("offline")
        p = os.path.join(FIX, "spdx", tail)
        if not os.path.exists(p):
            raise not_found(url)
        return fixture("spdx", tail)
    return get


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = os.getcwd()
        os.chdir(self.tmp.name)
        lt.http_get = fake_get()
        self.git_name = lt.git_user_name
        lt.git_user_name = lambda: "Git User"

    def tearDown(self):
        os.chdir(self.old)
        lt.http_get = REAL_GET
        lt.git_user_name = self.git_name
        self.tmp.cleanup()

    def run_cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = lt.main(list(argv))
        return rc, out.getvalue(), err.getvalue()

    def write(self, name, text):
        os.makedirs(os.path.dirname(name) or ".", exist_ok=True)
        with open(name, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

    def read(self, name):
        with open(name, encoding="utf-8") as f:
            return f.read()

    def fetch(self, sid, *extra):
        rc, out, err = self.run_cli("fetch", sid, "--year", "2026", "--holder", "Acme Games", *extra)
        self.assertEqual(rc, 0, err)
        return out


class Fill(Base):
    def test_mit(self):
        out = self.fetch("MIT")
        self.assertIn("\nCopyright (c) 2026 Acme Games\n", out)
        self.assertEqual(out, lt.tidy(fixture("api", "mit.txt").replace("[year] [fullname]", "2026 Acme Games")))

    def test_bsd(self):
        for sid in ("BSD-2-Clause", "BSD-3-Clause"):
            out = self.fetch(sid)
            self.assertIn("\nCopyright (c) 2026, Acme Games\n", out, sid)
            self.assertEqual(lt.PLACEHOLDER.findall(out), [], sid)

    def test_isc(self):
        self.assertIn("\nCopyright (c) 2026 Acme Games\n", self.fetch("isc"))

    def test_apache_appendix_kept_verbatim(self):
        rc, out, err = self.run_cli("fetch", "Apache-2.0", "--year", "2026", "--holder", "Acme Games")
        self.assertEqual(rc, 0, err)
        self.assertEqual(out, lt.tidy(fixture("api", "apache-2.0.txt")))
        self.assertIn("Copyright [yyyy] [name of copyright owner]", out)
        self.assertIn("--year and --holder were not used", err)

    def test_apache_fill_appendix(self):
        out = self.fetch("Apache-2.0", "--fill-appendix")
        self.assertIn("Copyright 2026 Acme Games", out)
        self.assertNotIn("[yyyy]", out)

    def test_spdx_fallback(self):
        lt.http_get = fake_get(api=False)
        rc, out, err = self.run_cli("fetch", "MIT", "--year", "2026", "--holder", "Acme Games")
        self.assertEqual(rc, 0, err)
        self.assertIn("SPDX license-list-data", err)
        self.assertIn("Copyright (c) 2026 Acme Games", out)

    def test_holder_default_from_git(self):
        rc, out, err = self.run_cli("fetch", "MIT", "--year", "2026")
        self.assertEqual(rc, 0, err)
        self.assertIn("Copyright (c) 2026 Git User", out)
        self.assertIn("confirm it with the user", err)

    def test_no_holder_refuses(self):
        lt.git_user_name = lambda: ""
        rc, out, err = self.run_cli("fetch", "MIT", "--out", "LICENSE")
        self.assertEqual(rc, 1)
        self.assertFalse(os.path.exists("LICENSE"))

    def test_leftover_placeholder_refuses(self):
        body = fixture("api", "mit.txt").replace("[fullname]", "[fullname] for [project]")
        lt.http_get = fake_get(override={"mit": json.dumps({"body": body})})
        rc, out, err = self.run_cli("fetch", "MIT", "--year", "2026", "--holder", "A", "--out", "LICENSE")
        self.assertEqual(rc, 1)
        self.assertIn("[project]", err)
        self.assertFalse(os.path.exists("LICENSE"))

    def test_offline_stops(self):
        lt.http_get = fake_get(api=False, spdx=False)
        rc, out, err = self.run_cli("fetch", "MIT", "--holder", "A", "--out", "LICENSE")
        self.assertEqual(rc, 3)
        self.assertIn("Do not write license text from memory", err)
        self.assertFalse(os.path.exists("LICENSE"))

    def test_out_exists_needs_force(self):
        self.write("LICENSE", "old\n")
        rc, _, err = self.run_cli("fetch", "MIT", "--holder", "A", "--out", "LICENSE")
        self.assertEqual(rc, 1)
        self.assertEqual(self.read("LICENSE"), "old\n")
        rc, _, err = self.run_cli("fetch", "MIT", "--holder", "A", "--out", "LICENSE", "--force")
        self.assertEqual(rc, 0, err)
        self.assertIn("MIT License", self.read("LICENSE"))


class Check(Base):
    def make(self, sid="MIT", *extra):
        rc, _, err = self.run_cli("fetch", sid, "--year", "2026", "--holder", "Acme Games", "--out", "LICENSE", *extra)
        self.assertEqual(rc, 0, err)
        return self.read("LICENSE")

    def test_match(self):
        self.make()
        rc, out, _ = self.run_cli("check")
        self.assertEqual(rc, 0, out)
        self.assertIn("license: MIT (detected", out)
        self.assertIn("copyright line: Copyright (c) 2026 Acme Games", out)

    def test_one_word_change(self):
        self.write("LICENSE", self.make().replace("merge, publish,", "merge, sell,"))
        rc, out, _ = self.run_cli("check", "LICENSE", "--id", "MIT")
        self.assertEqual(rc, 1)
        self.assertIn("in 1 place(s)", out)
        self.assertIn("[publish,]", out)
        self.assertIn("[sell,]", out)

    def test_rewrap_and_no_title_and_multi_holder(self):
        text = self.make()
        body = text.split("\n", 2)[2]  # 제목 줄을 뺀다
        body = body.replace("Acme Games", "Acme Games\nCopyright (c) 2025 Other Person")
        self.write("LICENSE", " ".join(body.split()) + "\n")
        rc, out, _ = self.run_cli("check", "--id", "MIT")
        self.assertEqual(rc, 0, out)

    def test_unfilled_placeholder(self):
        self.write("LICENSE", fixture("api", "mit.txt"))
        rc, out, _ = self.run_cli("check")
        self.assertEqual(rc, 1)
        self.assertIn("placeholders not filled: [fullname], [year]", out)

    def test_apache_both_forms(self):
        self.make("Apache-2.0")
        self.assertEqual(self.run_cli("check")[0], 0)
        self.make("Apache-2.0", "--force", "--fill-appendix")
        rc, out, _ = self.run_cli("check")
        self.assertEqual(rc, 0, out)
        self.assertIn("license: Apache-2.0", out)

    def test_spdx_form_matches_when_api_text_differs(self):
        # SPDX 의 BSD-3-Clause 는 제목이 없고 저작권 줄 끝에 마침표가 있다.
        self.write("LICENSE", fixture("spdx", "BSD-3-Clause.txt").replace("<year> <owner>", "2026 Acme Games"))
        rc, out, _ = self.run_cli("check")
        self.assertEqual(rc, 0, out)
        self.assertIn("SPDX license-list-data", out)

    def test_detect_ids(self):
        for key, sid in (("mit", "MIT"), ("bsd-2-clause", "BSD-2-Clause"), ("bsd-3-clause", "BSD-3-Clause"),
                         ("apache-2.0", "Apache-2.0"), ("isc", "ISC")):
            self.assertEqual(lt.detect_id(fixture("api", key + ".txt")), sid)

    def test_manifest_mismatch(self):
        self.make()
        self.write("package.json", json.dumps({"name": "x", "license": "Apache-2.0"}))
        self.write(os.path.join(".claude-plugin", "plugin.json"), json.dumps({"license": "ISC"}))
        self.write("Cargo.toml", '[package]\nname = "x"\nlicense = "MIT OR Apache-2.0"\n')
        self.write("pyproject.toml", '[project]\nname = "x"\nlicense = "MIT"\n')
        rc, out, _ = self.run_cli("check")
        self.assertEqual(rc, 1)
        self.assertIn('manifest mismatch: package.json: license "Apache-2.0" does not name MIT', out)
        self.assertIn("plugin.json: license \"ISC\"", out)
        self.assertNotIn("manifest mismatch: Cargo.toml", out)
        self.assertNotIn("manifest mismatch: pyproject.toml", out)
        self.assertIn("names more than one license", out)

    def test_manifest_match_and_unlicensed(self):
        self.make()
        self.write("package.json", json.dumps({"license": "MIT"}))
        self.assertEqual(self.run_cli("check")[0], 0)
        self.write("package.json", json.dumps({"license": "UNLICENSED"}))
        rc, out, _ = self.run_cli("check")
        self.assertEqual(rc, 1)
        self.assertIn("UNLICENSED", out)


class Notice(Base):
    ARGS = ("notice", "--name", "luau-lsp Roblox type definitions", "--url", "https://example.com/luau-lsp",
            "--id", "MIT", "--files", "a/globalTypes.d.luau,b/globalTypes.d.luau",
            "--copyright", "Copyright (c) 2022 JohnnyMorganz")

    def test_create_and_format(self):
        rc, out, err = self.run_cli(*self.ARGS)
        self.assertEqual(rc, 0, err)
        doc = self.read("THIRD_PARTY_NOTICES.md")
        self.assertTrue(doc.startswith("# Third-party notices\n\n## luau-lsp Roblox type definitions\n\nFiles:\n"
                                       "- `a/globalTypes.d.luau`\n- `b/globalTypes.d.luau`\n\n"
                                       "Source: https://example.com/luau-lsp (MIT).\n\n```\nMIT License\n\n"
                                       "Copyright (c) 2022 JohnnyMorganz\n"), doc)
        self.assertTrue(doc.endswith("SOFTWARE.\n```\n"), doc)

    def test_idempotent(self):
        self.write("THIRD_PARTY_NOTICES.md", "# Third-party notices\n\n## Other\n\nkept\n")
        self.assertEqual(self.run_cli(*self.ARGS)[0], 0)
        first = self.read("THIRD_PARTY_NOTICES.md")
        rc, out, _ = self.run_cli(*self.ARGS)
        self.assertEqual(rc, 0)
        self.assertIn("already present", out)
        self.assertEqual(self.read("THIRD_PARTY_NOTICES.md"), first)
        self.assertEqual(first.count("## luau-lsp"), 1)
        self.assertIn("## Other\n\nkept\n\n## luau-lsp", first)

    def test_same_name_different_content(self):
        self.run_cli(*self.ARGS)
        first = self.read("THIRD_PARTY_NOTICES.md")
        rc, _, err = self.run_cli(*self.ARGS[:-1], "Copyright (c) 2023 Someone Else")
        self.assertEqual(rc, 1)
        self.assertIn("different content", err)
        self.assertEqual(self.read("THIRD_PARTY_NOTICES.md"), first)

    def test_needs_copyright(self):
        rc, _, err = self.run_cli(*self.ARGS[:-2])
        self.assertEqual(rc, 1)
        self.assertIn("--copyright", err)
        self.assertFalse(os.path.exists("THIRD_PARTY_NOTICES.md"))

    def test_text_file(self):
        self.write("UPSTREAM_LICENSE", "Custom terms\n\nCopyright 2020 Upstream\n")
        rc, _, err = self.run_cli("notice", "--name", "Up", "--url", "u", "--id", "MIT", "--files", "x",
                                  "--text-file", "UPSTREAM_LICENSE")
        self.assertEqual(rc, 0, err)
        self.assertIn("```\nCustom terms\n\nCopyright 2020 Upstream\n```\n", self.read("THIRD_PARTY_NOTICES.md"))


@unittest.skipUnless(os.environ.get("LICENSE_TEXT_LIVE") == "1", "set LICENSE_TEXT_LIVE=1 to fetch for real")
class Live(Base):
    def setUp(self):
        super().setUp()
        lt.http_get = REAL_GET

    def test_mit_and_apache(self):
        for sid, key in (("MIT", "mit"), ("Apache-2.0", "apache-2.0")):
            rc, _, err = self.run_cli("fetch", sid, "--year", "2026", "--holder", "Acme Games", "--out", "LICENSE",
                                      "--force")
            self.assertEqual(rc, 0, err)
            source = err.split("source: ", 1)[1].split(" (", 1)[0]
            rc, out, _ = self.run_cli("check", "--id", sid)
            self.assertEqual(rc, 0, out)
            print(f"\nlive {sid}: fetched from {source}; check: {out.splitlines()[0]}", file=sys.stderr)
            if source.startswith("GitHub"):
                self.assertEqual(self.read("LICENSE"), lt.tidy(lt.fill(fixture("api", key + ".txt"), "2026", "Acme Games")),
                                 f"{sid}: the API text changed; refresh tests/fixtures/api/{key}.txt")


if __name__ == "__main__":
    unittest.main(verbosity=1)
