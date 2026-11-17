"""Run actual native board loading A->B->A and malformed rejections on a private editor."""

import argparse
import base64
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from editor_test_isolation import copy_editor
from package_tianshu_board import SOURCE, installed_package, pack, validate

PROBE = """@tool
extends SceneTree
func _initialize():
    run.call_deferred()
func run():
    for i in 8:
        await process_frame
    var workspace = root.find_child("DaqianWorkspace", true, false)
    if not workspace:
        quit(2)
        return
    var before: String = workspace.board_bundle_sha256
    var replacement := OS.get_environment("BOARD_REPLACEMENT")
    if not replacement.is_empty():
        var file := FileAccess.open(OS.get_environment("BOARD_INSTALLED"), FileAccess.WRITE)
        if not file:
            quit(3)
            return
        file.store_buffer(FileAccess.get_file_as_bytes(replacement))
        file.close()
    print("BOARD_PACKAGE_RESULT ", before, "|", workspace.board_bundle_sha256)
    quit()
"""


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encode(data):
    payload = json.dumps(data, sort_keys=True)
    return json.dumps(dict(payload=payload, sha256=digest(payload.encode()))).encode()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="tianshu-board-") as temporary:
        root = Path(temporary)
        executable = args.godot
        if executable.name.endswith(".console.exe"):
            executable = executable.with_name(executable.name.replace(".console.exe", ".exe"))
        binary = copy_editor(executable, root / "editor")
        original = digest(binary.read_bytes())
        project = root / "project"
        project.mkdir()
        (project / "project.godot").write_text(
            'config_version=5\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n'
        )
        (project / "probe.gd").write_text(PROBE, encoding="utf-8")
        a = root / "a.json"
        pack(SOURCE, "A", a)
        source = root / "source"
        shutil.copytree(SOURCE, source)
        with (source / "board.py").open("a", encoding="utf-8") as stream:
            stream.write("\n# native package B acceptance fixture\n")
        b = root / "b.json"
        pack(source, "B", b)
        sha_a = validate(a.read_bytes())["bundle_sha256"]
        sha_b = validate(b.read_bytes())["bundle_sha256"]
        installed = installed_package(binary)
        shutil.copyfile(a, installed)
        env = {key: value for key, value in os.environ.items() if not key.startswith(("GONGGONG_", "BOARD_"))}
        report = dict(
            editor_sha256=original,
            package_a=digest(a.read_bytes()),
            package_b=digest(b.read_bytes()),
            cases={},
            evidence_level="native editor injection; Python execution semantics tested separately",
        )

        def run(name, expected, path=None, pin=None, replacement=None):
            variables = dict(env)
            if path is not None:
                variables["GONGGONG_TIANSHU_BOARD_PACKAGE"] = str(path)
            if pin is not None:
                variables["GONGGONG_TIANSHU_BOARD_SHA256"] = pin
            if replacement:
                variables.update(BOARD_REPLACEMENT=str(replacement), BOARD_INSTALLED=str(installed))
            result = subprocess.run(
                [str(binary), "--headless", "--editor", "--path", str(project), "--script", "res://probe.gd"],
                cwd=project,
                env=variables,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=90,
            )
            log = result.stdout + result.stderr
            marker = f"BOARD_PACKAGE_RESULT {expected}|{expected}"
            if (
                result.returncode
                or marker not in log.splitlines()
                or "SCRIPT ERROR" in log
                or (not expected and "compatibility package rejected" not in log)
            ):
                raise RuntimeError(name + "\n" + log)
            report["cases"][name] = dict(returncode=result.returncode, observed=marker)

        run("installed_A_session_fixed_while_B_written", sha_a, replacement=b)
        run("next_session_B", sha_b)
        shutil.copyfile(a, installed)
        run("rollback_A", sha_a)
        run("explicit_B", sha_b, b, digest(b.read_bytes()))
        from package_tianshu_ui import installed_package as ui_package

        original_binary = binary
        original_ui = ui_package(binary)
        slot = "self_update_b" if "self_update_a" in binary.name.split(".") else "self_update_a"
        binary = binary.rename(binary.with_name("godot.editor." + slot + (".exe" if os.name == "nt" else "")))
        shutil.copyfile(original_ui, ui_package(binary))
        shutil.copyfile(b, installed_package(binary))
        run("self_update_slot_B", sha_b)
        binary = binary.rename(original_binary)
        helper_probe = Path(__file__).with_name("daqian_board_helpers.gd")
        shutil.copyfile(helper_probe, project / "helpers.gd")
        helper_env = dict(env, DAQIAN_TEST_REPO=str(Path(__file__).resolve().parents[2]))
        helpers = subprocess.run(
            [str(binary), "--headless", "--editor", "--path", str(project), "--script", "res://helpers.gd"],
            cwd=project,
            env=helper_env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=90,
        )
        helper_log = helpers.stdout + helpers.stderr
        if helpers.returncode or "DAQIAN_BOARD_HELPERS_OK" not in helper_log or "SCRIPT ERROR" in helper_log:
            raise RuntimeError("legacy/modern helper regression\n" + helper_log)
        report["cases"]["legacy_modern_unknown_helpers"] = dict(
            returncode=helpers.returncode, observed="DAQIAN_BOARD_HELPERS_OK"
        )
        run("wrong_pin", "", b, "0" * 64)
        run("missing_pin", "", b)
        run("relative_path", "", "b.json", digest(b.read_bytes()))
        run("missing_package", "", root / "missing.json", "0" * 64)
        data = validate(a.read_bytes())
        invalid = {
            "unknown_abi": encode({**data, "abi": "unknown/2"}),
            "entry_digest": encode({**data, "entries": {**data["entries"], "board.py": "0" * 64}}),
            "zip_digest": encode({**data, "bundle_sha256": "0" * 64}),
            "wrong_type": encode({**data, "entries": []}),
            "bad_base64": encode({**data, "bundle_base64": "???"}),
            "bad_payload": a.read_bytes().replace(b"payload", b"invalid"),
            "oversize": b"x" * (4 * 1024 * 1024 + 1),
        }
        bundle = base64.b64decode(data["bundle_base64"])[:-9]
        invalid["corrupt_zip"] = encode({
            **data,
            "bundle_base64": base64.b64encode(bundle).decode(),
            "bundle_sha256": digest(bundle),
        })
        for name, raw in invalid.items():
            candidate = root / (name + ".json")
            candidate.write_bytes(raw)
            run(name, "", candidate, digest(raw))
        if digest(binary.read_bytes()) != original:
            raise RuntimeError("Binary changed")
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
