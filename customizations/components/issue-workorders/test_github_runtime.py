"""Offline CLI discovery, host isolation and transport regression coverage."""

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import issue_gate
import kuafu_github
import work_items
import writer_submit
import yanluo_host

runtime = work_items.github_runtime
ROOT = Path(__file__).resolve().parents[3]
FIXED_LOCATIONS = runtime.fixed_locations


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.installation = self.root / "trusted host"
        self.home = self.root / "home"
        self.env = {"PATH": "", "HOME": str(self.home), "GONGGONG_KUAFU_LOCAL_ONLY": "1"}
        self.enterContext(patch.object(runtime, "INSTALLATION", self.installation))
        self.enterContext(patch.object(runtime.Path, "home", return_value=self.home))
        # No test may discover or launch the developer's real installed CLI.
        self.enterContext(patch.object(runtime, "fixed_locations", return_value=[self.home / ".local/bin/gh"]))

    def executable(self, path, output="fixture", code=None):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("#!" + sys.executable + "\n" + (code or "print(" + repr(output) + ")\n"), encoding="utf-8")
        path.chmod(0o755)
        return path

    def test_priority_explicit_installed_path_fixed(self):
        explicit = self.executable(self.root / "chosen gh")
        local = self.executable(self.installation / "project/runtime/gh/bin/gh.exe")
        on_path = self.executable(self.root / ("bin/gh.exe" if os.name == "nt" else "bin/gh"))
        fixed = self.executable(self.home / ".local/bin/gh")
        env = dict(self.env, PATH=str(on_path.parent))
        self.assertEqual(runtime.resolve_gh(dict(env, GONGGONG_GH=str(explicit))), str(explicit))
        self.assertEqual(runtime.resolve_gh(env), str(local))
        local.unlink()
        self.assertEqual(runtime.resolve_gh(env), str(on_path))
        on_path.unlink()
        self.assertEqual(runtime.resolve_gh(env), str(fixed))

    def test_fixed_locations_are_platform_specific_and_use_supplied_environment(self):
        windows = self.root / "Program Files"
        legacy = self.executable(self.home / "Documents/Codex/tools/github-cli/2.0/bin/gh.exe")
        with patch.object(runtime, "WINDOWS", True):
            self.assertEqual(FIXED_LOCATIONS({"ProgramFiles": str(windows)}), [windows / "GitHub CLI/gh.exe", legacy])
        with patch.object(runtime, "WINDOWS", False):
            self.assertEqual(
                FIXED_LOCATIONS({"ProgramFiles": str(windows)}),
                [self.home / ".local/bin/gh", Path("/opt/homebrew/bin/gh"), Path("/usr/local/bin/gh")],
            )

    def test_invalid_explicit_never_falls_back(self):
        self.executable(self.home / ".local/bin/gh")
        for configured in ("", str(self.root / "missing"), str(self.root)):
            with (
                self.subTest(configured=configured),
                self.assertRaisesRegex(runtime.GitHubCommandError, "configured.*missing"),
            ):
                runtime.resolve_gh(dict(self.env, GONGGONG_GH=configured))
        if os.name != "nt":
            path = self.executable(self.root / "not executable")
            path.chmod(0o644)
            with self.assertRaisesRegex(runtime.GitHubCommandError, "not executable"):
                runtime.resolve_gh(dict(self.env, GONGGONG_GH=str(path)))

    def test_explicit_command_name_resolves_only_that_name_on_supplied_path(self):
        name = "gh.exe" if os.name == "nt" else "gh"
        chosen = self.executable(self.root / "selected bin" / name)
        self.executable(self.installation / "project/runtime/gh/bin" / name)
        self.executable(self.home / ".local/bin/gh")
        env = dict(self.env, PATH=str(chosen.parent), GONGGONG_GH="gh")
        self.assertEqual(runtime.resolve_gh(env), str(chosen))
        chosen.unlink()
        with self.assertRaisesRegex(runtime.GitHubCommandError, "configured.*missing"):
            runtime.resolve_gh(env)
        with self.assertRaisesRegex(runtime.GitHubCommandError, "configured.*missing"):
            runtime.resolve_gh(dict(env, GONGGONG_GH="another-gh"))

    def test_windows_command_search_uses_supplied_extensions_without_implicit_cwd(self):
        chosen = self.executable(self.root / "selected bin/gh.fixture")
        with patch.object(runtime, "WINDOWS", True), patch.dict(os.environ, PATHEXT=".EXE"):
            env = dict(self.env, PATH=str(chosen.parent), PATHEXT=".FIXTURE", GONGGONG_GH="gh")
            self.assertEqual(runtime.resolve_gh(env), str(chosen))
            self.assertIsNone(runtime.command_on_path("gh", dict(env, PATH="")))
            self.assertIsNone(runtime.command_on_path("gh", dict(env, PATHEXT=".EXE")))

    def test_missing_path_does_not_inherit_process_path(self):
        path = self.executable(self.root / "ambient bin/gh")
        with (
            patch.dict(os.environ, {"PATH": str(path.parent)}),
            self.assertRaisesRegex(runtime.GitHubCommandError, "GITHUB_RUNTIME"),
        ):
            runtime.resolve_gh({})

    def test_install_after_failed_probe_and_replacement_are_visible(self):
        with self.assertRaises(runtime.GitHubCommandError):
            runtime.resolve_gh(self.env)
        path = self.executable(self.installation / "project/runtime/gh/bin/gh", "first")
        self.assertEqual(runtime.resolve_gh(self.env), str(path))
        if os.name != "nt":
            self.assertEqual(runtime.run_gh("version", env=self.env), "first")
            self.executable(path, "replacement")
            self.assertEqual(runtime.run_gh("version", env=self.env), "replacement")
        path.unlink()
        with self.assertRaises(runtime.GitHubCommandError):
            runtime.resolve_gh(self.env)

    @unittest.skipIf(os.name == "nt", "POSIX synthetic executable")
    def test_spaces_unicode_and_shell_characters_are_single_argv(self):
        path = self.executable(
            self.root / "a space ' $ ; 中文/gh", code="import json,sys\nprint(json.dumps(sys.argv[1:]))\n"
        )
        output = runtime.run_gh("api", "query with ' $ ; 中文", env=dict(self.env, GONGGONG_GH=str(path)))
        self.assertEqual(json.loads(output), ["api", "query with ' $ ; 中文"])

    def test_transport_error_classification_is_sanitized(self):
        path = self.executable(self.root / "gh")
        env = dict(self.env, GONGGONG_GH=str(path))
        failures = [
            (FileNotFoundError("private path"), "GITHUB_RUNTIME", None),
            (PermissionError("private path"), "GITHUB_RUNTIME", None),
            (OSError("bad executable format"), "GITHUB_RUNTIME", None),
            (subprocess.TimeoutExpired("private args", 120), "GITHUB_TIMEOUT", None),
            (subprocess.CompletedProcess([], 1, "", "private-token EOF"), "GITHUB_NETWORK", None),
            (subprocess.CompletedProcess([], 1, "", "private-token HTTP 403"), "GITHUB_HTTP_403", 403),
            (subprocess.CompletedProcess([], 1, "", "private-token auth required"), "GITHUB_COMMAND", None),
        ]
        for result, prefix, status in failures:
            kwargs = {"side_effect": result} if isinstance(result, Exception) else {"return_value": result}
            with self.subTest(prefix=prefix), patch.object(runtime.subprocess, "run", **kwargs):
                with self.assertRaisesRegex(runtime.GitHubCommandError, "^" + prefix) as raised:
                    runtime.run_gh("api", "user", env=env)
                self.assertEqual(raised.exception.http_status, status)
                self.assertNotIn("private", str(raised.exception))

    def test_pagination_budget_only_covers_recognized_rest_reads(self):
        read = ["api", "repos/a/b/issues?state=all", "--paginate", "--slurp"]
        variants = [
            read,
            ["api", "--paginate", "--jq", ".[]|.id", "user/repos"],
            [*read, "--hostname=fixture.invalid", "-X", "GET"],
            ["api", "https://fixture.invalid/api/v3/issues", "--paginate"],
        ]
        for args in variants:
            with self.subTest(args=args):
                self.assertEqual(runtime.request_timeout(args), 600)
                self.assertEqual(runtime.request_timeout(args, 37), 37)
                self.assertEqual(runtime.request_timeout(args, 600), 600)
        unsafe = [
            read + ["-f", "title=new"],
            read + ["--input", "-"],
            read + ["-X", "POST"],
            read + ["--method=DELETE"],
            read + ["--unknown"],
            read + ["extra"],
            ["api", "graphql", "--paginate"],
            ["api", "https://fixture.invalid/api/graphql", "--paginate"],
            ["issue", "create", "--body", "--paginate"],
            ["api", "user"],
            ["api", "--paginate", "--jq", "user/repos"],
        ]
        for args in unsafe:
            with self.subTest(args=args):
                self.assertEqual(runtime.request_timeout(args), 120)
        self.assertEqual(runtime.request_timeout(read, input_value="{}"), 120)
        for timeout in (0, -1, True, float("inf"), float("nan"), "600"):
            with self.assertRaises(runtime.GitHubCommandError):
                runtime.request_timeout(read, timeout)

    @unittest.skipIf(os.name == "nt", "POSIX synthetic executable")
    def test_slow_complete_read_survives_single_request_budget_and_stalled_child_is_reaped(self):
        path = self.executable(
            self.root / "pager",
            code="""import json,os,sys,time
from pathlib import Path
Path('child.pid').write_text(str(os.getpid()))
for page in range(11): time.sleep(0.025)
print(json.dumps([[{'id': i}] for i in range(11)]))
""",
        )
        env = dict(self.env, GONGGONG_GH=str(path))
        args = ("api", "repos/a/b/issues", "--paginate", "--slurp")
        with patch.object(runtime, "DEFAULT_TIMEOUT", 0.1), patch.object(runtime, "PAGINATION_TIMEOUT", 2):
            self.assertEqual(len(json.loads(runtime.run_gh(*args, env=env, cwd=self.root))), 11)
            for command in (args, ("issue", "create")):
                with self.assertRaisesRegex(runtime.GitHubCommandError, "GITHUB_TIMEOUT"):
                    runtime.run_gh(*command, env=env, cwd=self.root, timeout=0.1)
                pid = int((self.root / "child.pid").read_text())
                with self.assertRaises(ProcessLookupError):
                    os.kill(pid, 0)

    def test_native_page_shapes_errors_and_deadlines_are_not_reimplemented(self):
        path = self.executable(self.root / "pager")
        env = dict(self.env, GONGGONG_GH=str(path))
        for output, suffix in (
            ("[[1],[2]]", ["--slurp"]),
            ('[{"jobs":[]},{"jobs":[1]}]', ["--slurp"]),
            ("\n37\n", ["--jq", ".[]|.id"]),
        ):
            args = ["api", "fixture", "--paginate", *suffix]
            with patch.object(
                runtime.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, output, "")
            ) as run:
                self.assertEqual(runtime.run_gh(*args, env=env), output.strip())
                run.assert_called_once()
                self.assertEqual(run.call_args.args[0], [str(path), *args])
                self.assertEqual(run.call_args.kwargs["timeout"], 600)
                self.assertEqual(run.call_args.kwargs["env"], env)
        failures = [
            subprocess.TimeoutExpired("fixture", 600, output="partial"),
            subprocess.CompletedProcess([], 1, "partial", "HTTP 403"),
            subprocess.CompletedProcess([], 1, "partial", "EOF"),
        ]
        for failure in failures:
            kwargs = {"side_effect": failure} if isinstance(failure, Exception) else {"return_value": failure}
            with patch.object(runtime.subprocess, "run", **kwargs) as run:
                with self.assertRaises(runtime.GitHubCommandError):
                    runtime.run_gh("api", "fixture", "--paginate", env=env, timeout=23)
                run.assert_called_once()
                self.assertEqual(run.call_args.kwargs["timeout"], 23)

    def test_full_scan_must_succeed_before_issue_creation(self):
        settings = {"repository": "a/b"}
        doc = self.root / "design-docs/test.md"
        doc.parent.mkdir()
        doc.write_text("fixture")
        late = {"body": "<!-- gonggong-request:fixture-id -->", "html_url": "https://github.com/a/b/issues/1"}
        complete = [[] for _ in range(10)] + [[late]]
        for result in (
            runtime.GitHubCommandError(reason="GITHUB_TIMEOUT: fixture"),
            "[broken",
            json.dumps(complete + [[late]]),
            json.dumps(complete),
        ):

            def gh(*args, **kwargs):
                if args == ("api", "user"):
                    return '{"login":"fixture"}'
                self.assertEqual(args, ("api", "repos/a/b/issues?state=all&per_page=100", "--paginate", "--slurp"))
                if isinstance(result, Exception):
                    raise result
                return result

            with (
                patch.object(work_items, "config", return_value=(settings, [{"name": "type:bug"}])),
                patch.object(work_items, "gh", side_effect=gh) as api,
            ):
                if result == json.dumps(complete):
                    value = work_items.issue(
                        self.root, "design-docs/test.md", "fixture", "bug", "fixture-id", apply=True
                    )
                    self.assertEqual(value["state"], "existing")
                else:
                    with self.assertRaises(ValueError):
                        work_items.issue(self.root, "design-docs/test.md", "fixture", "bug", "fixture-id", apply=True)
                self.assertEqual(api.call_count, 2)

    @unittest.skipIf(os.name == "nt", "POSIX synthetic executable")
    def test_read_graphql_and_write_use_same_cli_and_preserve_input(self):
        path = self.executable(
            self.root / "selected gh",
            code="""import json,sys
payload = sys.stdin.read()
print(json.dumps({"data": {"arguments": sys.argv[1:], "input": json.loads(payload) if payload else None}}))
""",
        )
        with patch.dict(os.environ, dict(self.env, GONGGONG_GH=str(path)), clear=True):
            read = json.loads(work_items.gh("api", "user"))["data"]
            graphql = writer_submit.graphql("query($value:String!){viewer{login}}", value="quoted '\" value")
            write = kuafu_github.GitHub("fixture/repo").post("issues", {"title": "synthetic"})["data"]
        self.assertEqual(read["arguments"], ["api", "user"])
        self.assertEqual(graphql["input"]["variables"], {"value": "quoted '\" value"})
        self.assertEqual(write["input"], {"title": "synthetic"})
        self.assertIn("POST", write["arguments"])

    @unittest.skipIf(os.name == "nt", "POSIX synthetic executable and Git helper shell")
    def test_git_credential_helper_executes_exact_quoted_cli(self):
        path = self.executable(
            self.root / "a space ' $ ; 中文/gh",
            code="""import sys
assert sys.argv[1:] == ["auth", "git-credential", "get"]
sys.stdin.read()
print("username=synthetic-user\\npassword=synthetic-placeholder")
""",
        )
        env = dict(self.env, GONGGONG_GH=str(path), GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
        git = shutil.which("git")
        if not git:
            self.skipTest("Git unavailable")
        with patch.dict(os.environ, env, clear=True), patch.object(writer_submit, "git", return_value="ok") as invoke:
            self.assertEqual(writer_submit.authenticated_git(self.root, "fetch"), "ok")
        helper = invoke.call_args.args[4].removeprefix("credential.helper=")
        self.assertEqual(helper, runtime.credential_helper(env))
        output = subprocess.run(
            [git, "-c", "credential.helper=", "-c", "credential.helper=" + helper, "credential", "fill"],
            input="protocol=https\nhost=fixture.invalid\n\n",
            text=True,
            capture_output=True,
            env=env,
            timeout=30,
            check=True,
        ).stdout
        self.assertIn("username=synthetic-user", output)

    def test_yanluo_pins_selected_runtime_and_removes_signing_key(self):
        host = object.__new__(yanluo_host.GithubHost)
        host.repo = self.root
        host.gh = str(self.executable(self.root / "pinned gh"))
        with patch.dict(os.environ, {"GONGGONG_HOST_KEY": "private-test-value", "GONGGONG_GH": "changed"}):
            with patch.object(work_items, "gh", return_value='{"ok":true}') as run:
                self.assertEqual(host.api("fixture"), {"ok": True})
        env = run.call_args.kwargs["env"]
        self.assertEqual(env["GONGGONG_GH"], host.gh)
        self.assertNotIn("GONGGONG_HOST_KEY", env)

    def test_gate_session_rejects_changed_loaded_github_dependency(self):
        session = issue_gate.VerificationSession()
        for module in (work_items, runtime):
            with (
                self.subTest(module=module.__file__),
                patch.object(issue_gate, "GITHUB_SOURCES", {Path(module.__file__): b"different source"}),
            ):
                session.events["old-evidence"] = True
                with self.assertRaisesRegex(ValueError, "restart"):
                    session.check_runtime()
                self.assertEqual(session.events, {})

    @unittest.skipIf(os.name == "nt", "POSIX home installation fixture; Windows path policy is tested separately")
    def test_import_order_is_environment_neutral_and_uses_fixed_install(self):
        path = self.executable(self.home / ".local/bin/gh")
        script = """import importlib, json, os, sys
from pathlib import Path
sys.path[:0] = [sys.argv[1] + '/customizations/components/issue-workorders', sys.argv[1] + '/customizations/components/godot-host/daqian', sys.argv[1] + '/customizations/components/godot-host']
before = dict(os.environ)
for name in sys.argv[2:]: importlib.import_module(name)
import work_items, bridge
assert dict(os.environ) == before
print(json.dumps([work_items.github_runtime.resolve_gh(), bridge.find_gh(dict(os.environ))]))
"""
        for order in (
            ("work_items", "repository_access", "bridge"),
            ("repository_access", "bridge", "work_items"),
            ("bridge", "work_items", "repository_access"),
        ):
            result = subprocess.run(
                [sys.executable, "-B", "-c", script, str(ROOT), *order],
                env=self.env,
                text=True,
                capture_output=True,
                check=True,
                timeout=30,
            )
            self.assertEqual(json.loads(result.stdout), [str(path), str(path)])

    def test_bridge_ignores_target_project_tools(self):
        spec = importlib.util.spec_from_file_location(
            "github_fixture_bridge", ROOT / "customizations/components/godot-host/bridge.py"
        )
        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)
        target = self.root / "untrusted target"
        self.executable(target / "project/runtime/gh/bin/gh.exe")
        with (
            patch.object(bridge._github, "INSTALLATION", self.installation),
            patch.object(bridge._github, "fixed_locations", return_value=[]),
        ):
            self.assertIsNone(bridge.find_gh(self.env, target))
            installed = self.executable(self.installation / "project/runtime/gh/bin/gh.exe")
            self.assertEqual(bridge.find_gh(self.env, target), str(installed))
            with patch.dict(os.environ, {"GONGGONG_GH": str(target / "missing")}, clear=True):
                with self.assertRaisesRegex(bridge._github.GitHubCommandError, "configured.*missing"):
                    bridge.host_environment(target)

    @unittest.skipIf(os.name == "nt", "POSIX synthetic executable")
    def test_dispatch_pin_survives_real_legacy_path_preparation(self):
        spec = importlib.util.spec_from_file_location(
            "github_legacy_fixture_bridge", ROOT / "customizations/components/godot-host/bridge.py"
        )
        bridge = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bridge)
        selected = self.executable(self.root / "session CLI", output="selected-session")
        other = self.executable(self.installation / "legacy tools/gh", output="wrong-PATH-cli")
        components = []
        for name in ("node", "git"):
            tool = self.executable(other.parent / name)
            components.append({"id": name, "path": str(tool), "sha256": hashlib.sha256(tool.read_bytes()).hexdigest()})
        state = self.installation / "project/runtime/state/installed.json"
        state.parent.mkdir(parents=True)
        state.write_text(
            json.dumps({
                "schema_version": 1,
                "authorized": True,
                "path_base": "workspace_root",
                "components": components,
            })
        )
        supplied = {**self.env, "GONGGONG_GH": str(selected)}
        with (
            patch.object(bridge, "__file__", str(self.installation / "customizations/components/godot-host/bridge.py")),
            patch.dict(os.environ, supplied, clear=True),
        ):
            prepared = bridge.host_environment(self.root / "target project")
            self.assertEqual(os.environ["PATH"], "")
            self.assertEqual(prepared["GONGGONG_GH"], str(selected))
            self.assertEqual(prepared["GONGGONG_NODE"], str(other.parent / "node"))
            self.assertEqual(prepared["GONGGONG_GIT"], str(other.parent / "git"))
            self.assertIn(str(other.parent), prepared["PATH"].split(os.pathsep))
            self.assertEqual(bridge._github.run_gh("api", "fixture", env=prepared), "selected-session")

    @unittest.skipIf(os.name == "nt", "POSIX synthetic executable")
    def test_archived_host_imports_dependency_and_relocates_runtime(self):
        # Exercise the source archive boundary consumed by package_workspace_release;
        # no production index, branch, installed app or account is changed.
        source = self.root / "source"
        relative = "customizations/components/issue-workorders"
        folder = source / relative
        folder.mkdir(parents=True)
        for name in ("github_runtime.py", "work_items.py"):
            shutil.copyfile(ROOT / relative / name, folder / name)
        for name in (
            "customizations/components/godot-host/bridge.py",
            "customizations/components/godot-host/workspace_paths.py",
            "customizations/components/godot-host/environment_igniter.py",
            "tools/gonggong_runtime_config.py",
        ):
            destination = source / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / name, destination)
        git = shutil.which("git")
        if not git:
            self.skipTest("Git unavailable")
        env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)

        def run(*args):
            return subprocess.run([git, "-C", str(source), *args], env=env, capture_output=True, check=True)

        run("init", "-q")
        run("add", ".")
        run(
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-qm",
            "isolated package fixture",
        )
        archive = self.root / "host.tar"
        run("archive", "--format=tar", "--output", str(archive), "HEAD")
        relocated = self.root / "relocated host"
        with tarfile.open(archive) as bundle:
            bundle.extractall(relocated, filter="data")
        tool = self.executable(relocated / "project/runtime/gh/bin/gh", "packaged-host")
        script = "import runpy,sys; m=runpy.run_path(sys.argv[1]); print(m['gh']('version'))"
        args = [sys.executable, "-B", "-c", script, str(relocated / relative / "work_items.py")]
        result = subprocess.run(args, env=self.env, capture_output=True, text=True, timeout=30, check=True)
        self.assertEqual(result.stdout.strip(), "packaged-host")
        bridge_script = (
            "import runpy,sys,os; m=runpy.run_path(sys.argv[1]); print(m['find_gh'](dict(os.environ),sys.argv[2]))"
        )
        bridge_args = [
            sys.executable,
            "-B",
            "-c",
            bridge_script,
            str(relocated / "customizations/components/godot-host/bridge.py"),
            str(self.root / "untrusted target"),
        ]
        bridge_result = subprocess.run(
            bridge_args, env=self.env, capture_output=True, text=True, timeout=30, check=True
        )
        self.assertEqual(bridge_result.stdout.strip(), str(tool))
        tool.unlink()
        (relocated / relative / "github_runtime.py").unlink()
        result = subprocess.run(args, env=self.env, capture_output=True, text=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("github_runtime.py", result.stderr)


if __name__ == "__main__":
    unittest.main()
