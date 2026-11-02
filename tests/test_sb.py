"""
Tests for system/.brain/sb.py against a throwaway vault made by setup.py.

A stand-in for the Claude Code CLI (tests/fake_claude.py) files each pending
source as one source page, so the bookkeeping can be tested without an AI:
pending → auto → apply → lint, reruns with no changes, changed / moved /
deleted sources, and path keys upgrading to OneNote IDs.

Run:  python -m unittest discover tests
"""
from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FAKE = Path(__file__).resolve().parent / "fake_claude.py"


def snapshot(folder: Path) -> dict[str, str]:
    return {p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(folder.rglob("*")) if p.is_file()}


class SecondBrain(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self.tmp.name) / "Brain"
        r = subprocess.run([sys.executable, str(ROOT / "setup.py"), "--vault", str(self.vault)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        FAKE.chmod(FAKE.stat().st_mode | stat.S_IXUSR)
        self.env = dict(os.environ, CLAUDE_BIN=str(FAKE))
        self.on = self.vault / "OneNote Journals"
        (self.on / "College" / "Biology").mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def sb(self, *args, ok=True):
        r = subprocess.run([sys.executable, str(self.vault / ".brain" / "sb.py"), *args],
                           env=self.env, capture_output=True, text=True, cwd=self.vault)
        if ok is not None:
            self.assertEqual(r.returncode, 0 if ok else 1, r.stdout + r.stderr)
        return r.stdout

    def onenote_page(self, rel: str, text: str, oid: str | None = None):
        """Write a page plus the converter's manifest entry for it."""
        (self.on / rel).write_text(text, encoding="utf-8")
        mf = self.on / ".onenote-manifest.json"
        data = json.loads(mf.read_text(encoding="utf-8")) if mf.exists() else {"schema": 1, "pages": [], "deleted": []}
        data["pages"] = [p for p in data["pages"] if p["path"] != rel]
        data["pages"].append({"id": oid or f"path:{rel}", "id_source": "onenote" if oid else "path",
                              "path": rel, "title": Path(rel).stem,
                              "sha256": hashlib.sha256(text.encode()).hexdigest(), "status": "new"})
        mf.write_text(json.dumps(data), encoding="utf-8")

    def drop_page(self, rel: str):
        (self.on / rel).unlink()
        mf = self.on / ".onenote-manifest.json"
        data = json.loads(mf.read_text(encoding="utf-8"))
        data["pages"] = [p for p in data["pages"] if p["path"] != rel]
        mf.write_text(json.dumps(data), encoding="utf-8")

    def test_full_cycle(self):
        self.onenote_page("College/Biology/Cells.md", "# Cells\n\nMitochondria make ATP.\n", "{A}")
        self.onenote_page("College/Biology/DNA.md", "# DNA\n\nDouble helix.\n", "{B}")
        (self.vault / "raw" / "inbox" / "pairs-trading.md").write_text("# Pairs trading\n\nz-score entry at 2.\n")

        out = self.sb("pending")
        self.assertIn("3 pending", out)

        self.sb("auto")
        self.assertIn("Nothing pending", self.sb("auto"))
        out = self.sb("lint", "--strict")
        self.assertIn("0 error(s)", out)
        self.assertIn("3 sources = 3 filed", out)

        # Rerun with no source changes: nothing in the vault changes.
        before = snapshot(self.vault)
        self.sb("auto")
        self.sb("lint", "--strict")
        after = snapshot(self.vault)
        self.assertEqual(before, after)

        # Changed, moved (same ID, new path) and deleted sources.
        self.onenote_page("College/Biology/Cells.md", "# Cells\n\nMitochondria make ATP. Ribosomes too.\n", "{A}")
        (self.on / "College" / "Genetics").mkdir()
        text = (self.on / "College/Biology/DNA.md").read_text(encoding="utf-8")
        self.drop_page("College/Biology/DNA.md")
        self.onenote_page("College/Genetics/DNA.md", text, "{B}")
        (self.vault / "raw" / "inbox" / "pairs-trading.md").unlink()
        changes = {p["key"]: p["change"] for p in json.loads(self.sb("pending", "--json"))["batch"]}
        self.assertEqual(changes, {"{A}": "changed", "{B}": "moved", "raw:inbox/pairs-trading.md": "deleted"})

        self.sb("auto")
        out = self.sb("lint", "--strict")
        self.assertIn("0 error(s)", out)
        self.assertIn("2 sources = 2 filed", out)
        self.assertFalse((self.vault / "wiki/sources/raw-inbox-pairs-trading.md").exists())

    def test_sections_go_together(self):
        (self.on / "College" / "Chem").mkdir()
        for i in range(3):
            self.onenote_page(f"College/Biology/b{i}.md", f"# b{i}\n", f"{{B{i}}}")
        self.onenote_page("College/Chem/c0.md", "# c0\n", "{C0}")
        out = self.sb("auto", "--dry-run")
        self.assertIn("filing 3", out)
        self.assertNotIn("Chem", out)
        self.sb("auto")
        self.assertIn("0 pending", self.sb("pending"))

    def test_path_keys_upgrade_to_onenote_ids(self):
        self.onenote_page("College/Biology/Cells.md", "# Cells\n\nATP.\n")      # no ID yet
        self.sb("auto")
        self.onenote_page("College/Biology/Cells.md", "# Cells\n\nATP.\n", "{A}")
        self.assertIn("0 pending", self.sb("pending"))
        state = json.loads((self.vault / ".brain" / "state.json").read_text())
        self.assertEqual(list(state["items"]), ["{A}"])

    def test_apply_rejects_bad_reports(self):
        self.onenote_page("College/Biology/Cells.md", "# Cells\n", "{A}")
        self.sb("pending")
        report = {"items": [
            {"key": "{A}", "status": "ingested", "pages": ["wiki/sources/nope.md"]},
            {"key": "{Z}", "status": "ingested", "pages": []},
        ]}
        (self.vault / ".brain" / "ingest-report.json").write_text(json.dumps(report))
        out = self.sb("apply", ok=False)
        self.assertIn("don't exist", out)
        self.assertIn("not a current source", out)
        self.assertIn("1 pending", self.sb("pending"))

    def test_lint_catches_uncited_and_broken(self):
        (self.vault / "wiki/concepts/atp.md").write_text(
            "---\ntype: concept\ntitle: ATP\nsources: []\n---\n\nSee [[nowhere]].\n", encoding="utf-8")
        out = self.sb("lint", ok=False)
        self.assertIn("broken link [[nowhere]]", out)
        self.assertIn("no 'sources'", out)
        self.assertIn("not listed in wiki/index.md", out)

    def test_agreement(self):
        self.onenote_page("College/Biology/Cells.md", "# Cells\n", "{A}")
        self.sb("auto")
        (self.vault / "evals/my-sorting.csv").write_text(
            "path,topic\nOneNote Journals/College/Biology/Cells.md,school\n", encoding="utf-8")
        self.assertIn("1/1 = 100%", self.sb("agreement"))

    def test_eval_ignores_commented_examples(self):
        self.onenote_page("College/Biology/Cells.md", "# Cells\n", "{A}")
        self.sb("auto")
        with (self.vault / "evals/questions.md").open("a", encoding="utf-8") as f:
            f.write("- Q: What makes ATP? | expect: Biology/Cells\n- Q: Pairs? | expect: inbox/pairs\n")
        out = self.sb("eval", ok=False)
        self.assertIn("1/2 answered", out)
        self.assertNotIn("mitochondria in Bio 3", out)

    def test_setup_keeps_user_files_and_connects_converter(self):
        (self.vault / "wiki/index.md").write_text("# my index\n", encoding="utf-8")
        conv = Path(self.tmp.name) / "Converter"
        (conv / "scripts").mkdir(parents=True)
        (conv / "scripts" / "common.ps1").write_text("", encoding="utf-8")
        (conv / "settings.ps1").write_text("# x\n$VaultPath = 'C:\\old'\n", encoding="utf-8")
        r = subprocess.run([sys.executable, str(ROOT / "setup.py"), "--vault", str(self.vault),
                            "--converter", str(conv)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.vault / "wiki/index.md").read_text(encoding="utf-8"), "# my index\n")
        settings = (conv / "settings.ps1").read_text(encoding="utf-8-sig")
        self.assertNotIn("C:\\old", settings)
        self.assertIn(f"$VaultPath = '{self.vault}'", settings)
        self.assertIn("after-sync.bat", settings)


if __name__ == "__main__":
    unittest.main()
