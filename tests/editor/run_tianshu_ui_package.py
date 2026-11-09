"""Exercise installed, selected and rejected UI packages with one private editor."""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from editor_test_isolation import copy_editor
from package_tianshu_ui import installed_package

ROOT = Path(__file__).resolve().parents[2]
PROBE = """@tool
extends SceneTree
func _initialize():
    run.call_deferred()
func run():
    var dock = root.find_child("Daqian", true, false)
    if not dock:
        quit(2)
        return
    var workspace = dock.find_child("DaqianWorkspace", true, false)
    if not workspace:
        print("TIANSHU_PACKAGE_RESULT blocked")
    else:
        var graph = workspace.editor
        var card := GraphNode.new()
        graph.canvas.add_child(card)
        graph.positions.clear()
        graph.layout_columns = [[card]]
        graph._layout_cards()
        print("TIANSHU_PACKAGE_RESULT ", roundi(card.position_offset.x / graph.canvas.get_theme_default_base_scale()), " ", graph.apply_button.text)
    quit()
"""


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    os.environ.pop("GONGGONG_WORKSPACE", None)
    with tempfile.TemporaryDirectory(prefix="tianshu-ui-") as temporary:
        base = Path(temporary).resolve()
        executable = args.godot
        if executable.name.endswith(".console.exe"):
            executable = executable.with_name(executable.name.replace(".console.exe", ".exe"))
        binary = copy_editor(executable, base / "editor")
        original = digest(binary.read_bytes())
        installed = installed_package(binary)
        project = base / "project"
        project.mkdir()
        (project / "project.godot").write_text(
            'config_version=5\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n'
        )
        (project / "probe.gd").write_text(PROBE, encoding="utf-8")
        scripts = base / "scripts"
        scripts.mkdir()
        for name in ("graph_layout.gd", "issue_graph.gd"):
            shutil.copyfile(ROOT / "editor/docks/daqian" / name, scripts / name)
        layout = scripts / "graph_layout.gd"
        layout.write_text(
            layout.read_text(encoding="utf-8").replace("var x := 48.0", "var x := 96.0"), encoding="utf-8"
        )
        graph = scripts / "issue_graph.gd"
        graph.write_text(
            graph.read_text(encoding="utf-8").replace(
                'apply_button.text = "应用更改"', 'apply_button.text = "应用候选"'
            ),
            encoding="utf-8",
        )
        candidate = base / "v2.json"
        pin = subprocess.check_output(
            [
                sys.executable,
                str(ROOT / "tools/package_tianshu_ui.py"),
                "--source",
                str(scripts),
                "--version",
                "2",
                "--output",
                str(candidate),
            ],
            text=True,
        ).strip()
        # Even a syntactically valid local package must never shadow the installed default.
        shutil.copyfile(candidate, project / installed.name)
        report = {
            "editor_sha256": original,
            "installed_sha256": digest(installed.read_bytes()),
            "candidate_sha256": pin,
            "cases": {},
        }
        env = {key: value for key, value in os.environ.items() if not key.startswith("GONGGONG_")}

        def run(case, expected, path=None, fingerprint=None, diagnostic=""):
            variables = env.copy()
            if path is not None:
                variables["GONGGONG_TIANSHU_UI_PACKAGE"] = str(path)
            if fingerprint is not None:
                variables["GONGGONG_TIANSHU_UI_SHA256"] = fingerprint
            result = subprocess.run(
                [str(binary), "--headless", "--editor", "--path", str(project), "--script", "res://probe.gd"],
                cwd=project,
                env=variables,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=75,
            )
            log = result.stdout + result.stderr
            if (
                result.returncode
                or f"TIANSHU_PACKAGE_RESULT {expected}" not in log.splitlines()
                or diagnostic not in log
                or "SCRIPT ERROR" in log
            ):
                raise RuntimeError(case + "\n" + log)
            report["cases"][case] = expected

        run("installed", "48 应用更改")
        run("selected", "96 应用候选", candidate, pin)
        run("rollback", "48 应用更改")
        original_name = binary
        slot = "self_update_a" if "self_update_b" in binary.name.split(".") else "self_update_b"
        binary = binary.rename(binary.with_name("godot.editor." + slot + (".exe" if os.name == "nt" else "")))
        slot_package = installed_package(binary)
        shutil.copyfile(candidate, slot_package)
        run("independent_self_update_slot", "96 应用候选")
        slot_package.unlink()
        binary = binary.rename(original_name)
        run("wrong_pin", "blocked", candidate, "0" * 64, "pin mismatch")
        run("missing_pin", "blocked", candidate, diagnostic="SHA-256 pin")
        run("project_path", "blocked", "res://tianshu-ui.json", pin, "absolute filesystem path")
        run("missing_selected", "blocked", base / "missing", pin, "package missing")
        envelope = json.loads(candidate.read_bytes())
        payload = json.loads(envelope["payload"])
        payload["abi"] += "-incompatible"
        envelope["payload"] = json.dumps(payload)
        candidate.write_text(json.dumps(envelope), encoding="utf-8")
        run("damaged_payload", "blocked", candidate, digest(candidate.read_bytes()), "checksum mismatch")
        envelope["sha256"] = digest(envelope["payload"].encode())
        candidate.write_text(json.dumps(envelope), encoding="utf-8")
        run("incompatible", "blocked", candidate, digest(candidate.read_bytes()), "Incompatible Tianshu UI package ABI")
        installed.unlink()
        run("missing_default", "blocked", diagnostic="package missing")
        assert digest(binary.read_bytes()) == original
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report))


if __name__ == "__main__":
    main()
