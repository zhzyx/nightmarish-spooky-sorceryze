"""Scoped view boundary fixtures and real-process cross-candidate reuse."""

import unittest
from pathlib import Path
from unittest.mock import patch

from native_check_inputs import CheckInputView
from native_store import Conflict, NativeStoreError, _digest, _json
from native_workspace import Limits
from test_native_check_runner import RunnerTests


class InputTests(unittest.TestCase):
    setUp = RunnerTests.setUp
    make_candidate = RunnerTests.make_candidate
    runner = RunnerTests.runner
    run_check = RunnerTests.run_check

    def update(self, key, module, edits, dependencies=None):
        change = dict(module=module, base=self.store.head("test", module), reads=[], edits=edits)
        if dependencies is not None:
            change["dependencies"] = dependencies
        return self.store.submit("test", "producer", key, [change])["revisions"][module]

    def scoped(self, reads):
        self.cache.policies["check"]["reads"] = reads
        return self.runner()

    def view(self, runner, limits=None):
        return CheckInputView.from_binding(
            self.store,
            "test",
            self.cache.binding("test", self.candidate, "check", **runner.context("check", self.candidate)),
            limits,
        )

    def test_scope_process_counts_and_absence(self):
        core = self.update("extra", "core", {"hidden": b"secret"})
        other = self.update("other", "other", {"secret": b"outside"})
        self.candidate = self.store.compose("test", {"core": core, "other": other})["id"]
        runner = self.scoped({"core": ["code", "missing"]})
        runner = self.runner(
            "import os,pathlib; p=pathlib.Path(os.environ['DUOBAO_INPUT']); "
            "assert sorted(x.relative_to(p).as_posix() for x in p.rglob('*'))==['core','core/code']; print('ran')"
        )
        with patch.object(runner.helper, "run_owned", wraps=runner.helper.run_owned) as process:
            first = self.run_check(runner, "initial")
            self.assertEqual(first["outcome"], "passed")
            original = self.candidate
            other = self.update("other2", "other", {"secret": b"changed"})
            self.candidate = self.store.compose("test", {"core": core, "other": other})["id"]
            self.assertEqual(self.run_check(runner, "other-change")["state"], "cached")
            with self.assertRaises(Conflict):
                self.run_check(runner, "initial")
            core = self.update("hidden2", "core", {"hidden": b"changed"})
            self.candidate = self.store.compose("test", {"core": core, "other": other})["id"]
            self.assertEqual(self.run_check(runner, "hidden-change")["state"], "cached")
            self.assertEqual(process.call_count, 1)
            self.assertEqual(runner.context("check", original), runner.context("check", self.candidate))
            core = self.update("code2", "core", {"code": b"changed"})
            self.candidate = self.store.compose("test", {"core": core, "other": other})["id"]
            self.assertEqual(self.run_check(runner, "code-change")["state"], "complete")
            self.assertEqual(process.call_count, 2)
            core = self.update("missing-created", "core", {"missing": b"now exists"})
            self.candidate = self.store.compose("test", {"core": core})["id"]
            self.assertEqual(self.run_check(runner, "absence-change")["outcome"], "failed")
            self.assertEqual(process.call_count, 3)

    def test_empty_scope_and_exact_dependency_closure(self):
        dep = self.update("dep", "dep", {"file": b"dependency"})
        core = self.update("pin", "core", {}, {"dep": dep})
        self.candidate = self.store.compose("test", {"core": core})["id"]
        runner = self.scoped({"core": []})
        view = self.view(runner)
        dest = self.root / "view"
        view.materialize(self.store, "test", dest)
        self.assertEqual(sorted(p.relative_to(dest).as_posix() for p in dest.rglob("*")), ["core", "dep", "dep/file"])
        self.assertEqual((dest / "dep/file").read_bytes(), b"dependency")
        self.run_check(runner)
        dep = self.update("dep2", "dep", {"file": b"changed"})
        core = self.update("pin2", "core", {}, {"dep": dep})
        self.candidate = self.store.compose("test", {"core": core})["id"]
        self.assertEqual(self.run_check(runner, "dependency-change")["state"], "complete")

    def test_unknown_scope_conservative(self):
        for index, reads in enumerate((None, {"core": None})):
            with self.subTest(reads=reads):
                runner = self.scoped(reads)
                self.run_check(runner, "before-" + str(index))
                self.candidate = self.make_candidate("after-" + str(index))
                self.assertEqual(self.run_check(runner, "after-" + str(index))["state"], "complete")

    def test_view_limits_portability_and_transactional_cleanup(self):
        runner = self.scoped({"core": ["code"]})
        with self.assertRaises(NativeStoreError):
            self.view(runner, Limits(file_bytes=1))
        core = self.update("nested", "core", {"a/b/c": b"x", "Code": b"alias"})
        self.candidate = self.store.compose("test", {"core": core})["id"]
        self.scoped({"core": ["code", "Code"]})
        with self.assertRaises(NativeStoreError):
            self.view(runner)
        self.scoped({"core": ["a/b/c"]})
        with self.assertRaises(NativeStoreError):
            self.view(runner, Limits(entries=2))
        self.scoped({"core": ["code"]})
        view = self.view(runner)
        dest = self.root / "view"
        with patch.object(Path, "rename", side_effect=OSError("test failure")):
            with self.assertRaises(OSError):
                view.materialize(self.store, "test", dest)
        self.assertFalse(dest.exists())
        self.assertFalse(list(self.root.glob(".duobao-check-stage-*")))
        view.materialize(self.store, "test", dest)
        before = view.snapshot(dest)
        (dest / "core/code").touch()
        self.assertNotEqual(view.snapshot(dest), before)

    def test_frozen_binding_limits_and_corrupt_blob_cleanup(self):
        runner = self.scoped({"core": ["code"]})
        bound = self.cache.binding("test", self.candidate, "check", **runner.context("check", self.candidate))
        view = CheckInputView.from_binding(self.store, "test", bound)
        bound["binding"]["inputs"]["core"]["objects"].clear()
        self.assertIn("code", view.descriptor)
        with self.assertRaises(NativeStoreError):
            CheckInputView.from_binding(self.store, "test", bound)
        core = self.update("more", "core", {"extra": b"two"})
        other = self.update("other", "other", {"file": b"two"})
        self.candidate = self.store.compose("test", {"core": core, "other": other})["id"]
        self.scoped(None)
        for limits in (Limits(files=1), Limits(total_bytes=1), Limits(modules=1), Limits(request_bytes=1)):
            with self.subTest(limits=limits):
                with self.assertRaises(NativeStoreError):
                    self.view(runner, limits)
        with self.store._connection(write=True) as db:
            db.execute("UPDATE native_blobs SET content=? WHERE digest=?", (b"corrupt", _digest(b"first")))
        dest = self.root / "broken"
        with self.assertRaises(NativeStoreError):
            view.materialize(self.store, "test", dest)
        self.assertFalse(dest.exists())
        self.assertFalse(list(self.root.glob(".duobao-check-stage-*")))

    def test_dependency_conflict_and_integrity(self):
        dep = self.update("dep-one", "dep", {"file": b"first"})
        core = self.update("core-dep", "core", {}, {"dep": dep})
        other_dep = self.update("dep-two", "dep", {"file": b"second"})
        self.candidate = self.store.compose("test", {"core": core})["id"]
        runner = self.scoped({"core": ["code"]})
        bound = self.cache.binding("test", self.candidate, "check", **runner.context("check", self.candidate))
        bound["binding"]["inputs"]["other"] = {"objects": {}, "dependencies": {"dep": other_dep}}
        bound["key"] = _digest(_json(bound["binding"]).encode())
        with self.assertRaises(NativeStoreError):
            CheckInputView.from_binding(self.store, "test", bound)
        with self.store._connection(write=True) as db:
            db.execute("UPDATE native_blobs SET content=? WHERE digest=?", (b"corrupt", _digest(b"first")))
        with self.assertRaises(NativeStoreError):
            self.view(runner)

    def test_stable_release_policy_requires_separate_reviews(self):
        from native_release import NativeRelease

        self.cache.policies["whole"] = dict(version="v1", reads=None, max_age_seconds=3600)
        self.registry["whole"] = dict(self.registry["check"])
        runner = self.scoped({"core": ["code"]})
        first = self.run_check(runner)
        whole_a = runner.execute("test", "runner", "whole-a", self.candidate, "whole")
        release = NativeRelease(self.cache, lambda *a: True, lambda *a: {"producer"})
        release.configure(
            "test",
            "publisher",
            "product",
            dict(checks={c: runner.context(c, self.candidate) for c in ("check", "whole")}, review_max_age_seconds=60),
        )
        a = self.candidate
        review_a = release.approve(
            "test",
            "reviewer",
            "review-a",
            "product",
            a,
            {"check": first["evidence"], "whole": whole_a["evidence"]},
            "Independent A review",
        )
        core = self.update("unselected", "core", {"hidden": b"new"})
        self.candidate = self.store.compose("test", {"core": core})["id"]
        b = self.candidate
        self.assertEqual(self.run_check(runner, "b")["state"], "cached")
        whole_b = runner.execute("test", "runner", "whole-b", b, "whole")
        self.assertEqual(whole_b["state"], "complete")
        review_b = release.approve(
            "test",
            "reviewer",
            "review-b",
            "product",
            b,
            {"check": first["evidence"], "whole": whole_b["evidence"]},
            "Independent B review",
        )
        selected_a = release.publish("test", "publisher", "a", "product", "stable", review_a["id"], None)
        with self.assertRaises(Conflict):
            release.publish("test", "publisher", "bad-cas", "product", "stable", review_b["id"], None)
        release.publish("test", "publisher", "b", "product", "stable", review_b["id"], selected_a["id"])
        self.assertEqual(self.run_check(runner, "after-channel")["state"], "cached")
        clock = self.cache.clock
        self.cache.clock = lambda: clock() + 4000
        with self.assertRaises(NativeStoreError):
            release.selected("test", "publisher", "product", "stable")
        self.cache.clock = clock
        self.cache.revoke("test", "runner", first["evidence"], "revoked")
        with self.assertRaises(NativeStoreError):
            release.selected("test", "publisher", "product", "stable")


del RunnerTests
