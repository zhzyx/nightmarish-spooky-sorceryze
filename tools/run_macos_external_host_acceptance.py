"""Real macOS signed-host socket acceptance; no model, GUI, signing or policy bypass.

Run only on a disposable GitHub runner. The real account trust registry must be
empty. Every mutation is restored; launchd jobs and the private editor are owned.
PowerShell packages are official immutable releases with pinned download hashes.
The optional Codex app comes from the URL in openai/codex desktop_app/mac.rs.
Its existing Electron fuse is read, never modified. A disabled/unknown fuse means
unavailable evidence, never a visible app launch or a substitute CLI success.
"""

import argparse
import hashlib
import json
import mmap
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SENTINEL = b"dL7pKGdnNz796PbbjQWNKmHXBZaB9tsX"
PACKAGES = (
    ("7.6.9", "9002562086ad18dcdc4a1156f6cd6467cfb5a91b28206e56491212193b68e5e6"),
    ("7.7.0", "a15e395a9749b67501e69e52e07ef53bbb39ed2c97ed18940d5497e9c0e49a2e"),
)
CODEX_URL = "https://persistent.oaistatic.com/codex-app-prod/Codex.dmg"
IDENTITY_ERRORS = {"unrecognized_ancestor_code", "trusted_desktop_missing"}

PROBE = r"""import json,os,sys
from pathlib import Path
configuration=json.loads(Path(sys.argv[1]).read_text())
sys.path.insert(0,configuration['tools'])
from editor_instruction_client import EditorInstructionClient
value={'client_pid':os.getpid(),'parent_pid':os.getppid(),'uid':os.getuid()}
try:
    value['reply']=EditorInstructionClient(configuration['project'],configuration['engine']).context()
except Exception as error:
    value['probe_error']=type(error).__name__+': '+str(error)
Path(configuration['result']).write_text(json.dumps(value))
"""


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def command(arguments, *, timeout=60, check=True):
    result = subprocess.run([str(x) for x in arguments], capture_output=True, text=True, timeout=timeout)
    if check and result.returncode:
        raise RuntimeError(f"{Path(arguments[0]).name} exited {result.returncode}: {result.stderr[-2000:]}")
    return result


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fuse_states(data):
    """Read V1 RunAsNode in every universal slice; reject ambiguous wire data."""
    states = []
    start = 0
    while (index := data.find(SENTINEL, start)) >= 0:
        wire = index + len(SENTINEL)
        require(wire + 3 <= len(data), "truncated Electron fuse")
        require(data[wire] == 1 and data[wire + 1] >= 1, "unsupported Electron fuse version")
        require(wire + 2 + data[wire + 1] <= len(data), "truncated Electron fuse wire")
        states.append(data[wire + 2])
        start = wire + 2 + data[wire + 1]
    require(1 <= len(states) <= 2, "Electron fuse absent or ambiguous")
    return states


def validate_reply(value, positive):
    require("probe_error" not in value and isinstance(value.get("reply"), dict), "client did not receive native reply")
    reply = value["reply"]
    if positive:
        require(
            reply.get("ok") is True and reply.get("authenticated_desktop_peer") is True, "native authorization failed"
        )
        require(reply.get("peer_pid") == value["client_pid"], "reply did not authenticate actual client PID")
        require(
            reply.get("trusted_desktop_pid") == value["parent_pid"],
            "reply did not authenticate actual signed host parent",
        )
    else:
        require(reply.get("ok") is False and reply.get("error") in IDENTITY_ERRORS, "expected native identity denial")


def download(url, target, expected=None):
    command(
        ["/usr/bin/curl", "--fail", "--location", "--proto", "=https", "--max-time", "180", "--output", target, url],
        timeout=190,
    )
    actual = sha256(target)
    require(expected is None or actual == expected, "official package download hash mismatch")
    return dict(url=url, sha256=actual)


def powershell_packages(folder, report):
    paths = []
    for version, expected in PACKAGES:
        package = folder / f"pwsh-{version}.pkg"
        url = (
            f"https://github.com/PowerShell/PowerShell/releases/download/v{version}/powershell-{version}-osx-arm64.pkg"
        )
        receipt = download(url, package, expected)
        receipt.update(
            version=version,
            expected_sha256=expected,
            digest_source=f"https://api.github.com/repos/PowerShell/PowerShell/releases/tags/v{version}",
        )
        target = folder / f"pwsh-{version}"
        command(["/usr/sbin/pkgutil", "--expand-full", package, target], timeout=120)
        matches = [path for path in target.rglob("pwsh") if path.is_file() and not path.is_symlink()]
        require(len(matches) == 1, "official PowerShell package has ambiguous executable")
        paths.append(matches[0])
        report["downloads"].append(receipt)
    return paths


def codex_bundle(folder, report):
    package = folder / "Codex.dmg"
    report["downloads"].append(download(CODEX_URL, package))
    mount = folder / "codex-mount"
    mount.mkdir()
    command(
        ["/usr/bin/hdiutil", "attach", "-readonly", "-nobrowse", "-noautoopen", "-mountpoint", mount, package],
        timeout=120,
    )
    try:
        apps = list(mount.glob("*.app"))
        require(len(apps) == 1, "official Codex image has ambiguous app")
        target = folder / apps[0].name
        command(["/usr/bin/ditto", apps[0], target], timeout=120)
        return target
    finally:
        command(["/usr/bin/hdiutil", "detach", mount], timeout=30)


def launch_probe(folder, host, client, project, engine, *, electron=False):
    label = "org.gonggong.host-acceptance." + uuid.uuid4().hex
    result_path = folder / (label + ".json")
    config = folder / (label + "-input.json")
    config.write_text(
        json.dumps(dict(tools=str(ROOT / "tools"), project=str(project), engine=engine, result=str(result_path)))
    )
    if electron:
        wrapper = folder / (label + ".js")
        wrapper.write_text(
            "const r=require('child_process').spawnSync('/usr/bin/python3',"
            + json.dumps([str(client), str(config)])
            + ",{stdio:'inherit'});setTimeout(()=>process.exit(r.status===null?1:r.status),10000);",
            encoding="utf-8",
        )
        arguments = [str(host), str(wrapper)]
    else:
        wrapper = folder / (label + ".ps1")

        def quote(value):
            return "'" + str(value).replace("'", "''") + "'"

        wrapper.write_text(
            "& '/usr/bin/python3' "
            + quote(client)
            + " "
            + quote(config)
            + "\n$probeExit=$LASTEXITCODE\nStart-Sleep -Seconds 10\nexit $probeExit\n",
            encoding="utf-8",
        )
        arguments = [str(host), "-NoLogo", "-NoProfile", "-NonInteractive", "-File", str(wrapper)]
    environment = {
        "HOME": str(folder),
        "PATH": "/usr/bin:/bin:/usr/sbin:/sbin",
        "LANG": "en_US.UTF-8",
        "NODE_OPTIONS": "",
    }
    if electron:
        environment.update(ELECTRON_RUN_AS_NODE="1", CODEX_HOME=str(folder / "empty-codex-home"))
    plist = folder / (label + ".plist")
    plist.write_bytes(
        plistlib.dumps(
            dict(
                Label=label,
                ProgramArguments=arguments,
                RunAtLoad=True,
                EnvironmentVariables=environment,
                StandardOutPath=str(folder / (label + ".stdout")),
                StandardErrorPath=str(folder / (label + ".stderr")),
            )
        )
    )
    domains = [f"user/{os.getuid()}", f"gui/{os.getuid()}"]
    target = None
    attempts = []
    try:
        for domain in domains:
            started = command(["/bin/launchctl", "bootstrap", domain, plist], check=False)
            attempts.append(dict(domain=domain, exit_code=started.returncode, stderr=started.stderr[-1000:]))
            if started.returncode == 0:
                target = domain + "/" + label
                break
        require(target is not None, "launchctl user bootstrap failed: " + json.dumps(attempts))
        deadline = time.monotonic() + 35
        while time.monotonic() < deadline and not result_path.is_file():
            time.sleep(0.1)
        require(result_path.is_file(), "signed host returned no client receipt; see owned launchd stderr")
        value = json.loads(result_path.read_text())
        value["launchctl_domain"] = target.rsplit("/", 1)[0]
        value["launchctl_attempts"] = attempts
        value["host_ps"] = command(
            ["/bin/ps", "-p", str(value["parent_pid"]), "-o", "pid=,ppid=,uid=,comm="], check=False
        ).stdout.strip()
        return value
    finally:
        if target is not None:
            removed = command(["/bin/launchctl", "bootout", target], check=False)
            require(removed.returncode == 0, "could not unload owned launchd job " + target)


def cleanup_owned_resources(trust, engine, folder, report_path, report):
    """Attempt every owned cleanup, without masking the original test failure."""

    def attempt(stage, action):
        try:
            action()
        except Exception as error:
            report.setdefault("cleanup_errors", []).append({"stage": stage, "error": str(error)})
            report["ok"] = False

    def restore_policy():
        with trust.registry() as descriptor:
            trust.write_registry(descriptor, [])

    def stop_editor():
        if engine is not None and engine.poll() is None:
            engine.terminate()
            try:
                engine.wait(timeout=15)
            except subprocess.TimeoutExpired:
                engine.kill()
                engine.wait(timeout=10)

    def save_logs():
        # Never copy the discovery bearer token or existing user configuration.
        logs = report_path.parent / (report_path.stem + "-logs")
        logs.mkdir(exist_ok=True)
        for path in folder.iterdir():
            if path.suffix in (".stdout", ".stderr", ".log"):
                shutil.copyfile(path, logs / path.name)

    attempt("restore_policy", restore_policy)
    attempt("stop_editor", stop_editor)
    attempt("save_logs", save_logs)


def finish_report(report, path):
    # A stale success flag must never defeat failure of a terminal observer.
    report["ok"] = report.get("ok") is True and not report.get("error") and not report.get("cleanup_errors")
    report["ok"] = bool(report["ok"])
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["ok"] else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path)
    parser.add_argument(
        "--preflight", action="store_true", help="Check real signatures and launchd only; no editor acceptance claim"
    )
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--host-pwsh", type=Path)
    parser.add_argument("--upgrade-pwsh", type=Path)
    parser.add_argument("--download-fixtures", action="store_true")
    parser.add_argument("--codex-app", type=Path)
    parser.add_argument("--download-codex", action="store_true")
    parser.add_argument("--require-codex", action="store_true")
    args = parser.parse_args(argv)
    report = dict(
        ok=False,
        scope="actual macOS signed process ancestry and read-only editor context; no GUI or model inference",
        cases=[],
        downloads=[],
        codex=dict(state="not_tested"),
        actual_upgrade=False,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    try:
        require(
            sys.platform == "darwin" and os.getuid() != 0 and os.environ.get("GITHUB_ACTIONS") == "true",
            "requires disposable non-root GitHub macOS runner",
        )
        import editor_trusted_hosts as trust

        # Never temporarily replace a developer's existing authorization list.
        with trust.registry() as descriptor:
            require(not trust.read_registry(descriptor), "preexisting host trust policy; refusing to modify")
        with tempfile.TemporaryDirectory(prefix="gonggong-host-acceptance-") as temporary:
            folder = Path(temporary).resolve()
            hosts = powershell_packages(folder, report) if args.download_fixtures else []
            installed = shutil.which("pwsh")
            host = args.host_pwsh or (hosts[0] if hosts else Path(installed) if installed else None)
            require(host is not None, "PowerShell host unavailable")
            host = host.resolve(strict=True)
            identity = trust.signed_identity(host, "host", diagnostics=report.setdefault("signature_checks", []))
            report["host"] = dict(path=str(host), identity=identity, sha256=sha256(host))
            upgrades = [args.upgrade_pwsh] if args.upgrade_pwsh else hosts
            upgraded = None
            for candidate in upgrades:
                candidate = candidate.resolve(strict=True)
                observed = trust.signed_identity(candidate, "host", diagnostics=report["signature_checks"])
                if observed[1:3] == identity[1:3] and observed[3] != identity[3]:
                    upgraded = (candidate, observed)
                    break
            require(upgraded is not None, "second actual vendor-signed code version unavailable")
            report["upgraded_host"] = dict(path=str(upgraded[0]), identity=upgraded[1], sha256=sha256(upgraded[0]))
            if args.preflight:
                report["scope"] = (
                    "environment preflight only: actual vendor signatures and launchd execution; no editor authentication tested"
                )
                client = folder / "preflight.py"
                client.write_text(
                    "import json,os,sys\nfrom pathlib import Path\n"
                    "c=json.loads(Path(sys.argv[1]).read_text())\n"
                    "Path(c['result']).write_text(json.dumps(dict(client_pid=os.getpid(),parent_pid=os.getppid(),uid=os.getuid(),preflight_only=True)))\n",
                    encoding="utf-8",
                )
                try:
                    report["launchd"] = launch_probe(folder, host, client, folder, 0)
                    report["ok"] = True
                finally:
                    logs = args.report.parent / (args.report.stem + "-logs")
                    logs.mkdir(exist_ok=True)
                    for path in folder.iterdir():
                        if path.suffix in (".stdout", ".stderr"):
                            shutil.copyfile(path, logs / path.name)
                    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
                print(json.dumps(report))
                return 0
            require(args.godot is not None, "--godot is required for actual editor acceptance")
            os.environ.pop("GONGGONG_WORKSPACE", None)
            sys.path.insert(0, str(ROOT / "tests/editor"))
            from editor_test_isolation import copy_editor

            engine_path = copy_editor(args.godot, folder / "engine")
            report["editor_sha256"] = sha256(engine_path)
            project = folder / "project"
            project.mkdir()
            (project / "project.godot").write_text(
                'config_version=5\n[application]\nconfig/name="External Host Acceptance"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n'
            )
            client = folder / "client.py"
            client.write_text(PROBE, encoding="utf-8")
            environment = {
                key: value
                for key, value in os.environ.items()
                if not key.startswith(("GONGGONG_", "CODEX_"))
                and not any(word in key.upper() for word in ("TOKEN", "SECRET", "API_KEY"))
            }
            engine = None
            try:
                with (folder / "editor.log").open("wb") as log:
                    engine = subprocess.Popen(
                        [str(engine_path), "--headless", "--editor", "--path", str(project)],
                        stdout=log,
                        stderr=log,
                        env=environment,
                    )
                discovery = project / ".godot/editor/ai_control" / (str(engine.pid) + ".json")
                deadline = time.monotonic() + 90
                while not discovery.is_file() and engine.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.2)
                require(
                    discovery.is_file() and "instruction_socket" in json.loads(discovery.read_text()),
                    "native editor did not publish instruction socket",
                )

                def probe(name, binary, positive, electron=False):
                    value = launch_probe(folder, binary, client, project, engine.pid, electron=electron)
                    report["cases"].append(dict(name=name, expected_authorized=positive, observed=value))
                    validate_reply(value, positive)
                    report["cases"][-1]["passed"] = True

                def policy(entries):
                    with trust.registry() as descriptor:
                        trust.write_registry(descriptor, entries)

                def register(binary, entry):
                    result = command([
                        sys.executable,
                        ROOT / "tools/editor_trusted_hosts.py",
                        "register",
                        binary,
                        "--role",
                        entry[0],
                        "--team",
                        entry[1],
                        "--identifier",
                        entry[2],
                        "--cdhash",
                        entry[3],
                    ])
                    require(json.loads(result.stdout)["action"] == "register", "registration receipt unavailable")

                probe("unregistered_signed_host_rejected", host, False)
                register(host, identity)
                probe("explicit_signed_host_authorized", host, True)
                helper = ("helper", *identity[1:])
                register(host, helper)
                probe("host_downgraded_to_helper_rejected", host, False)
                register(host, identity)
                probe("helper_upgraded_to_host_authorized", host, True)
                # Simulate a stale policy digest, never a forged/re-signed binary.
                wrong_hash = ("0" if identity[3][0] != "0" else "1") + identity[3][1:]
                policy([(identity[0], identity[1], identity[2], wrong_hash)])
                probe("wrong_cdhash_policy_rejected", host, False)
                register(host, identity)
                probe("actual_new_signed_version_rejected_before_registration", upgraded[0], False)
                register(upgraded[0], upgraded[1])
                probe("actual_new_signed_version_authorized_after_registration", upgraded[0], True)
                report["actual_upgrade"] = True
                command([
                    sys.executable,
                    ROOT / "tools/editor_trusted_hosts.py",
                    "revoke",
                    "--role",
                    identity[0],
                    "--team",
                    identity[1],
                    "--identifier",
                    identity[2],
                    "--cdhash",
                    identity[3],
                ])
                probe("revoked_original_host_rejected", host, False)
                policy([])
                report["non_codex_host_ok"] = True
                codex_ready = False
                try:
                    app = args.codex_app or (codex_bundle(folder, report) if args.download_codex else None)
                    require(app is not None, "official Codex macOS app not supplied")
                    metadata = plistlib.loads((app / "Contents/Info.plist").read_bytes())
                    binary = app / "Contents/MacOS" / metadata["CFBundleExecutable"]
                    observed = trust.signed_identity(binary, "host", diagnostics=report["signature_checks"])
                    require(
                        observed[1:3] == ("2DC432GLL2", "com.openai.codex"),
                        "app is not the existing built-in Codex desktop identity",
                    )
                    framework = app / "Contents/Frameworks/Electron Framework.framework/Electron Framework"
                    with framework.open("rb") as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
                        states = fuse_states(data)
                    report["codex"] = dict(
                        state="inspected", identity=observed, run_as_node_fuses=states, sha256=sha256(binary)
                    )
                    require(
                        all(state == 0x31 for state in states),
                        "RunAsNode disabled or unknown; app will not be launched",
                    )
                    codex_ready = True
                    probe("builtin_codex_desktop_signed_anchor_without_registry", binary, True, electron=True)
                    report["codex"]["state"] = "passed_signed_anchor_node_mode"
                    report["codex"]["desktop_ui_or_model_tested"] = False
                except Exception as error:
                    report["codex"].update(state="failed" if codex_ready else "unavailable", reason=str(error))
                    if codex_ready or args.require_codex:
                        raise
                report["ok"] = True
                report["full_signed_anchor_acceptance_ok"] = (
                    report["codex"].get("state") == "passed_signed_anchor_node_mode"
                )
            finally:
                cleanup_owned_resources(trust, engine, folder, args.report, report)
    except Exception as error:
        report["ok"] = False
        report["error"] = str(error)
    return finish_report(report, args.report)


if __name__ == "__main__":
    raise SystemExit(main())
