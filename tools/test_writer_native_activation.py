"""Fresh writer CLI with real private Git/App validation and a read-only GH fixture."""

import hashlib
import json
import os
import shlex
import subprocess
import sys
import unittest
from pathlib import Path

import editor_candidate_activation as activation
import editor_native_app as native
import test_editor_candidate_activation as activation_fixture

INSTALLATION = Path(__file__).resolve().parents[1]
WRITER = INSTALLATION / "customizations/components/issue-workorders/writer_submit.py"


@unittest.skipUnless(sys.platform == "darwin", "real native App signature validation")
class WriterNativeActivationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = activation_fixture.ActivationTests("test_native_tampered_resource_preserves_original_entry")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        f = self.fixture
        renamed = f.folder / "source 引号' ; data"
        f.root.rename(renamed)
        f.root = renamed
        f.common = renamed / ".git"
        f.binding.update(
            source_root=str(renamed),
            common_dir=str(f.common),
            binding_path=str(f.common / "gonggong-engine-candidates/fixture.json"),
        )
        (f.root / "work-items.json").write_text(
            json.dumps({"repository": "fixture/repo", "category_labels": ".github/labels.json"})
        )
        (f.root / ".github").mkdir()
        (f.root / ".github/labels.json").write_text('[{"name":"type:bug"}]')
        base = f.head
        f.git("switch", "-c", "fixture-candidate")
        f.git("add", "work-items.json", ".github/labels.json")
        f.git("commit", "-m", "private candidate")
        candidate = f.git("rev-parse", "HEAD")
        tree = f.git("rev-parse", "HEAD^{tree}")
        message = f"Sign delivery for #1\n\nGongGong-Issue: #1\nGongGong-Request: isolated-fixture\nRepository: fixture/repo\nCandidate: {candidate}\nTree: {tree}\nBase: {base}\nTarget: main\nWriter: fixture"
        f.git("commit", "--allow-empty", "-m", message)
        signed = f.git("rev-parse", "HEAD")
        f.git("update-ref", "refs/pull/7/head", signed)
        f.git("switch", "main")
        f.git("merge", "--no-ff", "fixture-candidate", "-m", "private accepted merge")
        merge = f.git("rev-parse", "HEAD")
        f.git("remote", "add", "origin", "https://github.com/fixture/repo.git")
        f.native_candidate()
        f.binding["artifact_manifest"] = str(f.manifest_path)
        activation.atomic_json(Path(f.binding["binding_path"]), f.binding)
        f.save()
        metadata = {
            "pr": {
                "url": "https://github.com/fixture/repo/pull/7",
                "headRefName": "codex/submit/fixture/1/" + candidate,
                "headRefOid": signed,
                "baseRefName": "main",
                "isCrossRepository": False,
                "state": "MERGED",
                "mergeCommit": {"oid": merge},
            },
            "tip": {
                "oid": signed,
                "message": message,
                "tree": {"oid": tree},
                "parents": {"nodes": [{"oid": candidate}]},
                "author": {"user": {"login": "fixture"}},
                "signature": {"isValid": True, "wasSignedByGitHub": True},
            },
            "issue": {"state": "CLOSED", "stateReason": "COMPLETED", "labels": [{"name": "status:done"}]},
        }
        self.gh_log = f.folder / "gh-calls.jsonl"
        state = f.folder / "gh-state.json"
        state.write_text(json.dumps(metadata))
        script = f.folder / "fake-gh.py"
        script.write_text(
            "import json,sys\nfrom pathlib import Path\n"
            + f"v=json.loads(Path({str(state)!r}).read_text())\nPath({str(self.gh_log)!r}).open('a').write(json.dumps(sys.argv[1:])+'\\n')\n"
            + "a=sys.argv[1:]\nif a[:2]==['pr','view']: result=v['pr']\nelif a[:2]==['issue','view']: result=v['issue']\nelif a and a[0]=='api' and 'graphql' in a:\n q=json.load(sys.stdin); assert q['variables']['oid']==v['tip']['oid']; result={'data':{'repository':{'object':v['tip']}}}\nelse: raise AssertionError('Non-read GH operation')\nprint(json.dumps(result))\n"
        )
        gh = f.folder / "fake-gh"
        gh.write_text(
            "#!/bin/sh\nexec " + shlex.quote(sys.executable) + " -E -s -B " + shlex.quote(str(script)) + ' "$@"\n'
        )
        gh.chmod(0o700)
        git_script = f.folder / "fake-git.py"
        git_script.write_text(
            "import os,sys\na=sys.argv[1:]\na=["
            + repr(str(f.root))
            + " if value=='https://github.com/fixture/repo.git' and 'fetch' in a else value for value in a]\nos.execv('/usr/bin/git',['git',*a])\n"
        )
        git = f.folder / "git"
        git.write_text(
            "#!/bin/sh\nexec " + shlex.quote(sys.executable) + " -E -s -B " + shlex.quote(str(git_script)) + ' "$@"\n'
        )
        git.chmod(0o700)
        trap = f.folder / "untrusted-modules"
        trap.mkdir()
        self.trap_marker = f.folder / "untrusted-imported"
        code = f"from pathlib import Path\nPath({str(self.trap_marker)!r}).touch()\nraise RuntimeError('untrusted module')\n"
        for name in (
            "editor_candidate_activation.py",
            "editor_native_app.py",
            "editor_managed_native_entry.py",
            "sitecustomize.py",
        ):
            (trap / name).write_text(code)
            (f.root / name).write_text(code)
        self.env = dict(
            os.environ,
            GONGGONG_GH=str(gh),
            GONGGONG_GIT=str(git),
            PATH=str(f.folder) + os.pathsep + os.environ.get("PATH", ""),
            PYTHONPATH=str(trap),
            PYTHONHOME=str(trap / "missing-home"),
        )
        self.candidate, self.merge = candidate, merge

    def cli(self):
        f = self.fixture
        result = subprocess.run(
            [sys.executable, "-E", "-s", "-B", "-X", "utf8", str(WRITER), "--repo", str(f.root), "--inspect-pr", "7"],
            cwd=f.root,
            env=self.env,
            capture_output=True,
            encoding="utf-8",
            timeout=90,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(
            (report["pr_state"], report["candidate"], report["current_main"]), ("MERGED", self.candidate, self.merge)
        )
        self.assertFalse(self.trap_marker.exists())
        return report["engine_launch_activation"]

    def test_clean_cli_native_activation_and_reuse_ignore_import_traps(self):
        f = self.fixture
        source_before = {
            str(p.relative_to(Path(f.manifest["native_app"]["bundle_path"]))): hashlib.sha256(
                p.read_bytes()
            ).hexdigest()
            for p in Path(f.manifest["native_app"]["bundle_path"]).rglob("*")
            if p.is_file()
        }
        first = self.cli()
        self.assertTrue(first["ok"])
        self.assertEqual(first["state"], "activated")
        native.verify_signature(f.app)
        second = self.cli()
        self.assertTrue(second["ok"] and second["reused"])
        native.verify_signature(f.app)
        source_after = {
            str(p.relative_to(Path(f.manifest["native_app"]["bundle_path"]))): hashlib.sha256(
                p.read_bytes()
            ).hexdigest()
            for p in Path(f.manifest["native_app"]["bundle_path"]).rglob("*")
            if p.is_file()
        }
        self.assertEqual(source_before, source_after)
        self.assertEqual(native.digest(f.entry), f.manifest["artifact_sha256"])
        calls = [json.loads(line) for line in self.gh_log.read_text().splitlines()]
        self.assertEqual(len(calls), 6)

    def test_clean_cli_preserves_merge_when_native_signature_is_invalid(self):
        f = self.fixture
        (Path(f.manifest["native_app"]["bundle_path"]) / "Contents/Resources/unsigned.txt").write_text("not signed")
        original = f.entry.read_bytes()
        result = self.cli()
        self.assertEqual(result["state"], "pending")
        self.assertTrue(result["error"].startswith("activation_native_app_invalid"))
        self.assertEqual(original, f.entry.read_bytes())

    def test_clean_process_resolves_full_native_managed_dependency_graph(self):
        names = [
            "editor_candidate_activation",
            "editor_native_app",
            "editor_managed_native_entry",
            "editor_engine_candidate",
            "editor_source_manifest",
        ]
        result = subprocess.run(
            [
                sys.executable,
                "-E",
                "-s",
                "-B",
                "-X",
                "utf8",
                "-c",
                "import importlib,json\nnames="
                + repr(names)
                + "\nprint(json.dumps({name:importlib.import_module(name).__file__ for name in names}))\n",
            ],
            cwd=INSTALLATION / "tools",
            env=self.env,
            capture_output=True,
            encoding="utf-8",
            timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        modules = json.loads(result.stdout)
        self.assertEqual(set(modules), set(names))
        for path in modules.values():
            self.assertEqual(Path(path).parent, INSTALLATION / "tools")
        self.assertFalse(self.trap_marker.exists())
        self.assertFalse(self.gh_log.exists())


if __name__ == "__main__":
    unittest.main()
