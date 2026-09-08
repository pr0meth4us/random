"""Tests for the cleaner's safety rules and filesystem measurement.

Stdlib only, no server required: run with `python3 -m unittest` from this
directory. The safety rules decide what may be moved to the Trash, so they are
covered path by path — including the ways a caller might try to escape them.
"""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class SandboxHome(unittest.TestCase):
    """Point HOME at a scratch directory so the real rules run against real dirs."""

    def setUp(self):
        self.home = os.path.realpath(tempfile.mkdtemp(prefix="cleaner-test-"))
        self._real_home = Path.home
        os.environ["HOME"] = self.home
        Path.home = staticmethod(lambda: Path(self.home))

        for rel in ("Library/Caches/AppA", "Library/Caches/AppB", "Downloads",
                    ".ssh", "Documents/nested/deep", "Library/Mobile Documents"):
            os.makedirs(os.path.join(self.home, rel), exist_ok=True)

        # Reload so module-level constants pick up the sandboxed HOME.
        for name in ("safety", "scanner"):
            sys.modules.pop(name, None)
        import safety
        import scanner
        self.safety, self.scanner = safety, scanner

    def tearDown(self):
        Path.home = self._real_home
        shutil.rmtree(self.home, ignore_errors=True)

    def write(self, rel, data):
        path = os.path.join(self.home, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        return path


class TestReadableRoots(SandboxHome):
    def test_accepts_paths_in_home(self):
        self.assertEqual(
            self.safety.resolve_readable("~/Downloads"),
            os.path.join(self.home, "Downloads"),
        )

    def test_rejects_paths_outside_read_roots(self):
        with self.assertRaises(self.safety.PathNotAllowed):
            self.safety.resolve_readable("/etc/passwd")

    def test_rejects_traversal(self):
        with self.assertRaises(self.safety.PathNotAllowed):
            self.safety.resolve_readable("~/../../etc")

    def test_rejects_symlink_that_escapes_home(self):
        os.symlink("/etc", os.path.join(self.home, "escape"))
        with self.assertRaises(self.safety.PathNotAllowed):
            self.safety.resolve_readable("~/escape")

    def test_rejects_empty_path(self):
        with self.assertRaises(self.safety.PathNotAllowed):
            self.safety.resolve_readable("   ")


class TestDeletionGuards(SandboxHome):
    def refused(self, path):
        return self.safety.deletion_refusal(path) is not None

    def test_refuses_structural_directories(self):
        for path in ("/", self.home,
                     os.path.join(self.home, "Library"),
                     os.path.join(self.home, "Library", "Caches"),
                     os.path.join(self.home, "Documents"),
                     os.path.join(self.home, "Downloads")):
            self.assertTrue(self.refused(path), f"should refuse {path}")

    def test_refuses_sensitive_subtrees(self):
        for rel in (".ssh/id_rsa", "Library/Keychains/db",
                    "Library/Mobile Documents/doc.txt",
                    "Library/Application Support/App/state"):
            self.assertTrue(self.refused(os.path.join(self.home, rel)), rel)

    def test_refuses_paths_outside_home(self):
        self.assertTrue(self.refused("/etc/passwd"))
        self.assertTrue(self.refused("/Applications/Safari.app"))

    def test_allows_cache_contents(self):
        self.assertIsNone(
            self.safety.deletion_refusal(os.path.join(self.home, "Library/Caches/AppA"))
        )

    def test_sibling_name_is_not_treated_as_child(self):
        # "Documents-other" must not match the "Documents" guard by prefix.
        self.assertIsNone(
            self.safety.deletion_refusal(os.path.join(self.home, "Documents-other", "f"))
        )


class TestDropNested(SandboxHome):
    def test_child_covered_by_parent_is_dropped(self):
        parent = os.path.join(self.home, "Documents/nested")
        child = os.path.join(self.home, "Documents/nested/deep")
        other = os.path.join(self.home, "Downloads/file.bin")
        self.assertEqual(self.safety.drop_nested([child, parent, other]), [parent, other])

    def test_duplicates_collapse(self):
        p = os.path.join(self.home, "Downloads/a")
        self.assertEqual(self.safety.drop_nested([p, p]), [p])


class TestPlanDeletions(SandboxHome):
    def test_refused_ancestor_does_not_swallow_permitted_children(self):
        # Selecting a protected parent alongside a legitimate child must not
        # silently drop the child — that would make the user's click do nothing.
        child = os.path.join(self.home, "Library/Caches/AppA")
        approved, errors = self.safety.plan_deletions([self.home, child])
        self.assertEqual(approved, [child])
        self.assertEqual([e["path"] for e in errors], [self.home])

    def test_permitted_ancestor_still_collapses_its_children(self):
        parent = os.path.join(self.home, "Library/Caches/AppA")
        child = os.path.join(parent, "inner")
        os.makedirs(child, exist_ok=True)
        approved, errors = self.safety.plan_deletions([child, parent])
        self.assertEqual(approved, [parent])
        self.assertEqual(errors, [])

    def test_expands_tilde_and_reports_each_refusal(self):
        approved, errors = self.safety.plan_deletions(["~/.ssh/id_rsa", "/etc/passwd"])
        self.assertEqual(approved, [])
        self.assertEqual(len(errors), 2)
        self.assertTrue(errors[0]["path"].startswith(self.home))


class TestSizes(SandboxHome):
    def test_hard_links_counted_once(self):
        blob = b"x" * 100_000
        self.write("Downloads/original.bin", blob)
        os.link(os.path.join(self.home, "Downloads/original.bin"),
                os.path.join(self.home, "Downloads/link.bin"))
        self.assertEqual(self.scanner.get_dir_size(os.path.join(self.home, "Downloads")),
                         len(blob))

    def test_symlinked_directory_is_not_followed(self):
        self.write("Downloads/a.bin", b"y" * 1000)
        os.symlink(os.path.join(self.home, "Downloads"),
                   os.path.join(self.home, "Library/Caches/AppA/loop"))
        # Would never terminate, or would double-count, if symlinks were followed.
        self.assertEqual(self.scanner.get_dir_size(os.path.join(self.home, "Library/Caches/AppA")), 0)

    def test_path_size_handles_files_dirs_and_missing(self):
        f = self.write("Downloads/one.bin", b"z" * 500)
        self.assertEqual(self.scanner.path_size(f), 500)
        self.assertEqual(self.scanner.path_size(os.path.join(self.home, "Downloads")), 500)
        self.assertEqual(self.scanner.path_size(os.path.join(self.home, "missing")), 0)

    def test_immediate_children_sorted_largest_first(self):
        self.write("Library/Caches/AppA/blob", b"a" * 5_000)
        self.write("Library/Caches/AppB/blob", b"b" * 9_000)
        items = self.scanner.get_immediate_children(os.path.join(self.home, "Library/Caches"))
        self.assertEqual([i["name"] for i in items], ["AppB", "AppA"])
        self.assertEqual([i["sizeBytes"] for i in items], [9_000, 5_000])


class TestDuplicates(SandboxHome):
    def setUp(self):
        super().setUp()
        self.body = b"A" * 300_000
        self.write("Downloads/copy1.bin", self.body + b"tail")
        self.write("Downloads/copy2.bin", self.body + b"tail")
        # Same size, differs only in the tail — the sample pass must not call it
        # a duplicate, and the full pass must confirm that.
        self.write("Downloads/near-miss.bin", self.body + b"TAIL")

    def find(self):
        return self.scanner.find_duplicates(os.path.join(self.home, "Downloads"), 1000)

    def test_finds_identical_files_only(self):
        groups = self.find()
        self.assertEqual(len(groups), 1)
        self.assertEqual(sorted(os.path.basename(i["path"]) for i in groups[0]["items"]),
                         ["copy1.bin", "copy2.bin"])

    def test_reports_recoverable_space_not_total_size(self):
        group = self.find()[0]
        self.assertEqual(group["totalWastedBytes"], len(self.body) + 4)

    def test_hard_links_are_not_recoverable_waste(self):
        os.link(os.path.join(self.home, "Downloads/copy1.bin"),
                os.path.join(self.home, "Downloads/hardlink.bin"))
        # Three names, two inodes: still exactly one duplicate's worth of waste.
        group = self.find()[0]
        self.assertEqual(len(group["items"]), 2)
        self.assertEqual(group["totalWastedBytes"], len(self.body) + 4)

    def test_respects_minimum_size(self):
        self.assertEqual(self.scanner.find_duplicates(os.path.join(self.home, "Downloads"),
                                                      10 * 1024 * 1024), [])


class TestLargeFiles(SandboxHome):
    def test_threshold_and_installer_rule(self):
        self.write("Downloads/big.bin", b"a" * 2_000_000)
        self.write("Downloads/small.bin", b"a" * 10)
        self.write("Downloads/installer.dmg", b"a" * 500_000)
        items, total = self.scanner.find_large_files(
            os.path.join(self.home, "Downloads"), 1_000_000)
        names = [i["name"] for i in items]
        self.assertIn("big.bin", names)
        self.assertNotIn("small.bin", names)
        self.assertEqual(total, sum(i["sizeBytes"] for i in items))

    def test_skips_hidden_directories(self):
        self.write(".ssh/big-secret", b"a" * 2_000_000)
        items, _ = self.scanner.find_large_files(self.home, 1_000_000)
        self.assertEqual(items, [])


class TestDevArtifacts(SandboxHome):
    def project(self, rel, marker=None, marker_body=b"{}"):
        d = os.path.join(self.home, rel)
        os.makedirs(d, exist_ok=True)
        if marker:
            with open(os.path.join(d, marker), "wb") as f:
                f.write(marker_body)
        return d

    def filled(self, path, size=50_000):
        os.makedirs(path, exist_ok=True)
        with open(os.path.join(path, "blob"), "wb") as f:
            f.write(b"x" * size)
        return path

    def test_finds_marked_node_modules(self):
        proj = self.project("code/app", "package.json")
        self.filled(os.path.join(proj, "node_modules"))
        items, total = self.scanner.find_dev_artifacts(os.path.join(self.home, "code"))
        self.assertEqual([i["name"] for i in items], ["node_modules"])
        self.assertEqual(items[0]["project"], "app")
        self.assertEqual(total, 50_000)

    def test_ignores_unmarked_lookalike(self):
        # A folder called node_modules with no package.json beside it is not
        # something we can prove is regenerable.
        self.filled(os.path.join(self.home, "code/notaproject/node_modules"))
        items, _ = self.scanner.find_dev_artifacts(os.path.join(self.home, "code"))
        self.assertEqual(items, [])

    def test_ignores_handwritten_build_directory(self):
        # `build` with no project marker beside it may well be source.
        self.filled(os.path.join(self.home, "code/docs/build"))
        items, _ = self.scanner.find_dev_artifacts(os.path.join(self.home, "code"))
        self.assertEqual(items, [])

    def test_virtualenv_needs_pyvenv_cfg(self):
        bare = self.filled(os.path.join(self.home, "code/p1/.venv"))
        items, _ = self.scanner.find_dev_artifacts(os.path.join(self.home, "code"))
        self.assertEqual(items, [])
        open(os.path.join(bare, "pyvenv.cfg"), "wb").close()
        items, _ = self.scanner.find_dev_artifacts(os.path.join(self.home, "code"))
        self.assertEqual([i["name"] for i in items], [".venv"])

    def test_does_not_descend_into_a_match(self):
        # A nested node_modules is already counted inside its parent's total;
        # reporting it again would double-count and waste the walk.
        proj = self.project("code/app", "package.json")
        nested = os.path.join(proj, "node_modules/dep")
        self.project("code/app/node_modules/dep", "package.json")
        self.filled(os.path.join(nested, "node_modules"))
        items, total = self.scanner.find_dev_artifacts(os.path.join(self.home, "code"))
        self.assertEqual([i["path"] for i in items], [os.path.join(proj, "node_modules")])
        # The nested tree is counted once, inside its parent's total, not twice.
        self.assertEqual(total, items[0]["sizeBytes"])
        self.assertGreaterEqual(total, 50_000)

    def test_never_enters_git(self):
        self.filled(os.path.join(self.home, "code/app/.git/objects"))
        self.project("code/app", "package.json")
        items, _ = self.scanner.find_dev_artifacts(os.path.join(self.home, "code"))
        self.assertEqual(items, [])

    def test_unconditional_kinds_need_no_marker(self):
        self.filled(os.path.join(self.home, "code/app/__pycache__"))
        items, _ = self.scanner.find_dev_artifacts(os.path.join(self.home, "code"))
        self.assertEqual([i["name"] for i in items], ["__pycache__"])

    def test_respects_minimum_size(self):
        proj = self.project("code/app", "package.json")
        self.filled(os.path.join(proj, "node_modules"), size=100)
        items, _ = self.scanner.find_dev_artifacts(os.path.join(self.home, "code"), 1_000_000)
        self.assertEqual(items, [])

    def test_artifacts_are_deletable_under_the_safety_rules(self):
        proj = self.project("code/app", "package.json")
        nm = self.filled(os.path.join(proj, "node_modules"))
        self.assertIsNone(self.safety.deletion_refusal(nm))


class TestResultCache(unittest.TestCase):
    def test_memoises_until_refresh(self):
        cache = self.scanner_cache()
        calls = []

        def produce():
            calls.append(1)
            return len(calls)

        self.assertEqual(cache.get_or_compute("k", produce), 1)
        self.assertEqual(cache.get_or_compute("k", produce), 1)
        self.assertEqual(cache.get_or_compute("k", produce, refresh=True), 2)
        cache.clear()
        self.assertEqual(cache.get_or_compute("k", produce), 3)

    def test_expires_entries(self):
        cache = self.scanner_cache(ttl_seconds=0)
        self.assertEqual(cache.get_or_compute("k", lambda: "a"), "a")
        self.assertEqual(cache.get_or_compute("k", lambda: "b"), "b")

    def test_evicts_when_full(self):
        cache = self.scanner_cache(max_entries=2)
        for key in "abc":
            cache.get_or_compute(key, lambda: key)
        self.assertLessEqual(len(cache._entries), 2)

    @staticmethod
    def scanner_cache(**kw):
        import scanner
        return scanner.ResultCache(**kw)


if __name__ == "__main__":
    unittest.main(verbosity=2)
