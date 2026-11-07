"""Real native scene business actions through the isolated, authenticated host."""

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import time
import traceback
from pathlib import Path

from editor_test_isolation import copy_editor


def wait_json(path, process):
    deadline = time.monotonic() + 60
    while not path.exists():
        if process.poll() is not None or time.monotonic() > deadline:
            raise AssertionError(f"Fixture unavailable: {path.name}, process={process.poll()}")
        time.sleep(0.03)
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--macos-template", type=Path)
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("scene_client", repository / "tools/editor_control_client.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    report = {"ok": False, "checks": [], "editor_sha256": digest(args.godot)}
    # Observe the real settings without opening, updating or copying them.
    real_settings = Path.home() / "Library/Application Support/Godot/editor_settings-4.8.tres"
    report["real_settings_before"] = digest(real_settings)
    try:
        with tempfile.TemporaryDirectory(prefix="scene-completion-") as temporary:
            base = Path(temporary)
            project = base / "project"
            project.mkdir()
            commands = base / "commands"
            commands.mkdir()
            editor = copy_editor(args.godot, base / "engine")
            (editor.parent / "editor_data/editor_settings-4.8.tres").write_text(
                '[gd_resource type="EditorSettings" format=3]\n[resource]\nai_chat/editor_control_bridge_enabled = true\n'
            )
            (project / "project.godot").write_text(
                'config_version=5\n[application]\nconfig/name="Scene Completion"\nrun/main_scene="res://fixture.tscn"\n[rendering]\ntextures/vram_compression/import_etc2_astc=true\n'
            )
            (project / "test.gd").write_text(Path(__file__).with_name("editor_scene_completion.gd").read_text())
            (project / "behavior.gd").write_text(
                "@tool\nextends Node2D\nvar fired := 0\nvar hijacks := 0\nfunc _on_pressed():\n\tfired += 1\n"
                + "".join(
                    f'@warning_ignore("native_method_override")\nfunc {name}({parameters}):\n\thijacks += 1\n'
                    + ("\treturn OK\n" if name == "connect" else "")
                    for name, parameters in (
                        ("set_name", "_value"),
                        ("set_owner", "_value"),
                        ("reparent", "_parent, _keep = true"),
                        ("add_child", "_node, _readable = false, _internal = 0"),
                        ("remove_child", "_node"),
                        ("move_child", "_node, _position"),
                        ("connect", "_signal, _callable, _flags = 0"),
                        ("disconnect", "_signal, _callable"),
                    )
                )
            )
            for kind, declaration in (
                ("path", 'NodePath = NodePath("../Branch/Leaf")'),
                ("array", 'Array = [NodePath("../Branch/Leaf")]'),
                ("dictionary", 'Dictionary = {"target": NodePath("../Branch/Leaf")}'),
            ):
                (project / f"reference-{kind}.gd").write_text(
                    f"@tool\nextends Node2D\n@export var path: {declaration}\n"
                )
            (project / "reference-getter.gd").write_text(
                "@tool\nextends Node2D\nvar getter_calls := 0\nvar has_custom_getter := true\n"
                '@export var path: NodePath = NodePath("../Branch/Leaf"):\n'
                "\tget:\n\t\tgetter_calls += 1\n\t\treturn path\n"
            )
            if args.macos_template:
                (project / "templates").mkdir()
                shutil.copy2(args.macos_template, project / "templates/mac-arm64.zip")
                report["macos_template_sha256"] = digest(project / "templates/mac-arm64.zip")
            (project / "resource_behavior.gd").write_text("@tool\nextends Gradient\n")
            (project / "gradient.tres").write_text(
                '[gd_resource type="Gradient" format=3]\n[resource]\ncolors = PackedColorArray(1, 0, 0, 1, 0, 1, 0, 1)\n'
            )
            for mode in ("delete", "replace", "mutate"):
                (project / f"loader-{mode}.tres").write_text('[gd_resource type="Gradient" format=3]\n[resource]\n')
            (project / "instance.tscn").write_text(
                '[gd_scene format=3]\n[node name="Instance" type="Node2D"]\n[node name="Internal" type="Node2D" parent="."]\n'
            )
            (project / "base.tscn").write_text(
                '[gd_scene format=3]\n[node name="Base" type="Node2D"]\n[node name="Inherited" type="Node2D" parent="."]\n'
            )
            (project / "derived.tscn").write_text(
                '[gd_scene load_steps=2 format=3]\n[ext_resource type="PackedScene" path="res://base.tscn" id="1"]\n[node name="Derived" instance=ExtResource("1")]\n[node name="Local" type="Node2D" parent="."]\n'
            )
            (project / "fixture.tscn").write_text("""[gd_scene load_steps=3 format=3]
[ext_resource type="Script" path="res://behavior.gd" id="1"]
[ext_resource type="PackedScene" path="res://instance.tscn" id="2"]
[node name="Root" type="Node2D"]
[node name="Branch" type="Node2D" parent="."]
[node name="Leaf" type="Node2D" parent="Branch"]
[node name="Tracker" type="RemoteTransform2D" parent="."]
remote_path = NodePath("../Branch/Leaf")
[node name="Destination" type="Node2D" parent="."]
[node name="Receiver" type="Node2D" parent="."]
script = ExtResource("1")
[node name="Button" type="Button" parent="."]
[node name="Line" type="Line2D" parent="."]
[node name="Instance" parent="." instance=ExtResource("2")]
""")
            # A real tiny PNG goes through the native texture importer.
            import base64

            (project / "pixel.png").write_bytes(
                base64.b64decode(
                    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
                )
            )
            (project / "export_presets.cfg").write_text("""[preset.0]
name="Scene Pack"
platform="Linux"
runnable=false
export_filter="all_resources"
include_filter=""
exclude_filter="test.gd"
export_path=""
encrypt_pck=false
encrypt_directory=false
[preset.0.options]
binary_format/architecture="x86_64"
""")
            with (project / "export_presets.cfg").open("a") as presets:
                for index, (name, extra) in enumerate(
                    (
                        ("Scene Mac", ""),
                        ("Scene Mac Nonempty Helpers", 'codesign/entitlements/app_sandbox/helper_executables=[""]\n'),
                        ("Scene Mac Nonempty Options", 'codesign/custom_options=PackedStringArray("")\n'),
                    ),
                    1,
                ):
                    presets.write(
                        f'\n[preset.{index}]\nname="{name}"\nplatform="macOS"\nrunnable=false\n'
                        'export_filter="all_resources"\ninclude_filter=""\nexclude_filter="test.gd,templates/*"\n'
                        f'[preset.{index}.options]\nbinary_format/architecture="arm64"\napplication/bundle_identifier="com.example.scenecompletion"\n'
                        "codesign/codesign=0\nnotarization/notarization=0\n"
                        + ('custom_template/release="res://templates/mac-arm64.zip"\n' if args.macos_template else "")
                        + extra
                    )
            (project / "exports").mkdir()
            log_path = base / "editor.log"
            with log_path.open("w") as log:
                process = subprocess.Popen(
                    [str(editor), "--headless", "--editor", "--path", str(project), "--script", "res://test.gd"],
                    stdout=log,
                    stderr=log,
                    env={**os.environ, "GODOT_AI_API_KEY": "", "SCENE_COMMAND_DIR": str(commands)},
                )
                try:
                    assert wait_json(commands / "ready.json", process)["ok"]
                    client = module.EditorClient(project)
                    sequence = 0
                    command_sequence = 0

                    def command(action, **values):
                        nonlocal command_sequence
                        command_sequence += 1
                        pending = commands / "command.pending"
                        pending.write_text(json.dumps({"id": command_sequence, "action": action, **values}))
                        pending.replace(commands / "command.json")
                        return wait_json(commands / f"ack-{command_sequence}.json", process)

                    def route(action, **values):
                        nonlocal sequence
                        for _ in range(50):
                            sequence += 1
                            message = {
                                "intent": "engine_operation",
                                "source": "scene-completion",
                                "request_id": f"scene-{sequence}",
                                "operation": {"action": action, **values},
                            }
                            preview = client.route(message)
                            if preview.get("error") != "editor_busy":
                                return message, preview
                            time.sleep(0.1)
                        return message, preview

                    def approve(message):
                        assert command("approve")["visible"], "Native confirmation is required"
                        return client.status(message["request_id"], message["source"])

                    def apply(action, **values):
                        message, preview = route(action, **values)
                        assert preview.get("confirmation_required") and preview.get("manual_confirmation_required"), (
                            preview
                        )
                        value = approve(message)
                        assert value.get("ok"), value
                        return value

                    def check(name):
                        report["checks"].append(name)

                    assert route("open_scene", target="res://fixture.tscn")[1]["ok"]
                    time.sleep(0.2)
                    command("animation")
                    for kind in ("path", "array", "dictionary", "key"):
                        command("metadata_reference", value=kind)
                        before = command("snapshot", path="Reference")["metadata_path"]
                        for action, values in (
                            ("scene_reparent_node", {"target": "Branch", "parent": "Destination"}),
                            ("scene_rename_node", {"target": "Branch", "name": "RenamedBranch"}),
                            ("scene_delete_node", {"target": "Branch"}),
                        ):
                            rejected = route(action, **values)[1]
                            assert rejected["error"] == "unsafe_metadata_reference_scope", rejected
                        assert command("snapshot", path="Reference")["metadata_path"] == before
                        assert command("snapshot", path="Branch")["exists"]
                        command("script_reference_clear")
                    command("metadata_reference", value="scalar")
                    apply("scene_reparent_node", target="Branch", parent="Destination")
                    assert command("snapshot", path="Reference")["metadata_path"] == "7"
                    command("undo")
                    command("script_reference_clear")
                    check(
                        "native metadata references reject structural edits; scalar metadata permits normal move and undo"
                    )

                    for kind in ("path", "array", "dictionary", "getter"):
                        command("script_reference", value=kind)
                        getter_baseline = (
                            command("snapshot", path="Reference")["reference_getter_calls"] if kind == "getter" else 0
                        )
                        for action, values in (
                            ("scene_reparent_node", {"target": "Branch", "parent": "Destination"}),
                            ("scene_rename_node", {"target": "Branch", "name": "RenamedBranch"}),
                            ("scene_delete_node", {"target": "Branch"}),
                        ):
                            rejected = route(action, **values)[1]
                            assert rejected["error"] == "unsafe_script_reference_scope", rejected
                        value = command("snapshot", path="Reference")
                        if kind == "getter":
                            assert value["reference_getter_calls"] == getter_baseline, value
                            report["script_reference_getter_baseline"] = getter_baseline
                        elif kind == "path":
                            assert value["reference_path"] == "../Branch/Leaf", value
                        assert command("snapshot", path="Branch")["exists"]
                        command("script_reference_clear")
                    check("script storage references reject structural edits without getters or broken paths")

                    apply("scene_reparent_node", target="Branch", parent="Destination")
                    value = command("snapshot", path="Destination/Branch")
                    assert (
                        value["exists"]
                        and value["owner"] == "."
                        and value["leaf_owner"] == "."
                        and value["track"] == "Destination/Branch/Leaf:position"
                        and value["reference"] == "../Destination/Branch/Leaf"
                    ), value
                    command("undo")
                    assert command("snapshot", path="Branch")["track"] == "Branch/Leaf:position"
                    assert command("snapshot")["reference"] == "../Branch/Leaf"
                    command("redo")
                    assert command("snapshot", path="Destination/Branch")["leaf_owner"] == "."
                    command("undo")
                    check("subtree move, owners, native animation paths, undo and redo")
                    apply("scene_delete_node", target="Branch")
                    assert not command("snapshot", path="Branch")["exists"]
                    assert command("snapshot")["reference"] == ""
                    command("undo")
                    value = command("snapshot", path="Branch")
                    assert (
                        value["exists"]
                        and value["leaf_owner"] == "."
                        and value["track"] == "Branch/Leaf:position"
                        and value["reference"] == "../Branch/Leaf"
                    ), value
                    check("subtree delete and exact owner/animation restoration")
                    apply("scene_set_property", target="Receiver", property="position", value=[3, 4])
                    assert command("snapshot", path="Receiver")["position"] == [3, 4]
                    command("undo")
                    assert command("snapshot", path="Receiver")["position"] == [0, 0]
                    check("script-attached native property edit and undo")
                    apply("scene_rename_node", target="Receiver", name="RenamedReceiver")
                    assert command("snapshot", path="RenamedReceiver")["exists"]
                    command("undo")
                    command("redo")
                    assert command("snapshot", path="RenamedReceiver")["hijacks"] == 0
                    command("undo")
                    apply("scene_create_node", target="Receiver", type="Node2D", name="NativeChild")
                    assert command("snapshot", path="Receiver/NativeChild")["owner"] == "."
                    command("undo")
                    command("redo")
                    apply("scene_reparent_node", target="Receiver/NativeChild", parent="Destination")
                    command("undo")
                    assert command("snapshot", path="Receiver/NativeChild")["exists"]
                    apply("scene_delete_node", target="Receiver/NativeChild")
                    command("undo")
                    command("redo")
                    assert command("snapshot", path="Receiver")["hijacks"] == 0
                    apply("scene_reparent_node", target="Receiver", parent="Destination")
                    command("undo")
                    command("redo")
                    assert command("snapshot", path="Destination/Receiver")["hijacks"] == 0
                    command("undo")
                    check("script-shadowed native rename/add/remove/reparent/move/owner with undo and redo")
                    assert (
                        route("scene_set_property", target="Instance/Internal", property="position", value=[2, 3])[1][
                            "error"
                        ]
                        == "instance_children_not_editable"
                    )
                    command("editable", value=True)
                    apply("scene_set_property", target="Instance/Internal", property="position", value=[2, 3])
                    assert command("snapshot", path="Instance/Internal")["owner"] == "Instance"
                    assert (
                        route("scene_delete_node", target="Instance/Internal")[1]["error"]
                        == "inherited_or_foreign_structure"
                    )
                    apply("scene_reparent_node", target="Instance", parent="Destination")
                    assert command("snapshot", path="Destination/Instance/Internal")["owner"] == "Destination/Instance"
                    command("undo")
                    assert command("snapshot", path="Instance/Internal")["owner"] == "Instance"
                    check("instance editable override, protected internal structure, instance-root subtree move")
                    apply(
                        "scene_assign_resource", target="Line", property="gradient", resource_path="res://gradient.tres"
                    )
                    assert command("snapshot", path="Line")["gradient"]
                    command("undo")
                    assert not command("snapshot", path="Line")["gradient"]
                    command("redo")
                    apply(
                        "scene_export_resource",
                        target="Line",
                        property="gradient",
                        destination="res://exports/gradient.tres",
                    )
                    assert (project / "exports/gradient.tres").is_file()
                    check("native resource assignment/undo and explicit resource export")
                    message, preview = route(
                        "scene_export_resource",
                        target="Line",
                        property="gradient",
                        destination="res://exports/stale.tres",
                    )
                    assert preview.get("confirmation_required"), preview
                    command("gradient_mutate")
                    assert approve(message)["error"] == "scene_changed_since_confirmation"
                    apply(
                        "scene_export_resource",
                        target="Line",
                        property="gradient",
                        destination="res://exports/fresh.tres",
                    )
                    message, preview = route(
                        "scene_assign_resource", target="Line", property="gradient", resource_path="res://gradient.tres"
                    )
                    assert preview.get("confirmation_required"), preview
                    command("gradient_mutate")
                    assert approve(message)["error"] == "scene_changed_since_confirmation"
                    command("gradient_metadata", value="script")
                    assert (
                        route(
                            "scene_export_resource",
                            target="Line",
                            property="gradient",
                            destination="res://exports/rejected.tres",
                        )[1]["error"]
                        == "unsupported_resource_snapshot"
                    )
                    command("gradient_metadata", value="clear")
                    command("gradient_metadata", value="cycle")
                    assert (
                        route(
                            "scene_export_resource",
                            target="Line",
                            property="gradient",
                            destination="res://exports/rejected.tres",
                        )[1]["error"]
                        == "unsupported_resource_snapshot"
                    )
                    command("gradient_metadata", value="clear")
                    check("unchanged-version Gradient content staleness; nested script/cycle rejection and fresh save")
                    apply(
                        "scene_connect_signal",
                        target="Button",
                        signal="pressed",
                        receiver="Receiver",
                        method="_on_pressed",
                    )
                    assert command("snapshot", path="Button")["connected"]
                    apply(
                        "scene_disconnect_signal",
                        target="Button",
                        signal="pressed",
                        receiver="Receiver",
                        method="_on_pressed",
                    )
                    assert not command("snapshot", path="Button")["connected"]
                    command("undo")
                    assert command("snapshot", path="Button")["connected"]
                    command("undo")
                    assert not command("snapshot", path="Button")["connected"]
                    assert command("snapshot")["fired"] == 0
                    check("persistent signal connect/disconnect and undo without method invocation")
                    apply(
                        "scene_connect_signal",
                        target="Receiver",
                        signal="visibility_changed",
                        receiver="Receiver",
                        method="_on_pressed",
                    )
                    assert command("snapshot", path="Receiver")["self_connected"]
                    command("undo")
                    command("redo")
                    apply(
                        "scene_disconnect_signal",
                        target="Receiver",
                        signal="visibility_changed",
                        receiver="Receiver",
                        method="_on_pressed",
                    )
                    command("undo")
                    command("redo")
                    value = command("snapshot", path="Receiver")
                    assert not value["self_connected"] and value["hijacks"] == 0 and value["fired"] == 0, value
                    check("script-shadowed native connect/disconnect with undo and redo")
                    previous_version = command("history_noop")["version"]
                    message, preview = route("scene_set_property", target="Receiver", property="position", value=[8, 9])
                    assert preview.get("confirmation_required"), preview
                    assert command("history_branch")["version"] == previous_version
                    assert approve(message)["error"] == "scene_changed_since_confirmation"
                    check("native history branch rejects approval even when UndoRedo version and scene values repeat")
                    for action in ("run_project", "run_scene"):
                        previous_version = command("history_noop")["version"]
                        values = {"target": "res://fixture.tscn"} if action == "run_scene" else {}
                        message, preview = route(action, **values)
                        assert preview.get("confirmation_required"), preview
                        assert command("history_branch")["version"] == previous_version
                        assert approve(message)["error"] == "scene_changed_since_confirmation"
                        assert not command("snapshot")["playing"]
                    check("run project and scene approvals bind history epoch when numeric version repeats")
                    message, preview = route("scene_set_property", target="Receiver", property="position", value=[5, 6])
                    assert preview.get("confirmation_required"), preview
                    command("mutate", path="Receiver")
                    assert approve(message)["error"] == "scene_changed_since_confirmation"
                    message, preview = route(
                        "scene_assign_resource", target="Line", property="gradient", resource_path="res://gradient.tres"
                    )
                    assert preview.get("confirmation_required"), preview
                    with (project / "gradient.tres").open("a") as file:
                        file.write("\n; changed after approval preview\n")
                    assert approve(message)["error"] == "scene_changed_since_confirmation"
                    check("stale property and resource file hash rejection")
                    for mode in ("delete", "replace", "mutate"):
                        command("loader", value=mode)
                        message, preview = route(
                            "scene_assign_resource",
                            target="Line",
                            property="gradient",
                            resource_path=f"res://loader-{mode}.tres",
                        )
                        assert preview.get("confirmation_required"), preview
                        assert command("snapshot", path="Line")["loader_calls"] == 0, "Proposal must not load resources"
                        value = approve(message)
                        assert not value["ok"] and value["error"] == "scene_changed_during_resource_load", value
                        assert command("snapshot")["loader_calls"] == 1
                        command("loader_clear")
                    check("no preview loading; loader delete/replace/old-value mutation rejected after confirmation")
                    value = apply("scene_import_resource", resource_path="res://pixel.png")
                    assert value["import_valid"] and len(value["import_metadata_sha256"]) == 64
                    check("native texture reimport/scan and actual import metadata")
                    deadline = time.monotonic() + 10
                    while command("snapshot")["scanning"] and time.monotonic() < deadline:
                        time.sleep(0.1)
                    message, preview = route(
                        "project_export",
                        preset="Scene Pack",
                        format="pack",
                        debug=False,
                        destination="res://exports/project.pck",
                    )
                    assert preview.get("confirmation_required"), preview
                    imported = next((project / ".godot/imported").glob("*.ctex"))
                    imported.write_bytes(imported.read_bytes() + b"changed-import-input")
                    assert approve(message)["error"] == "scene_changed_since_confirmation"
                    check("PCK approval binds actual imported artifact contents")
                    value = apply(
                        "project_export",
                        preset="Scene Pack",
                        format="pack",
                        debug=False,
                        destination="res://exports/project.pck",
                    )
                    assert value["output_exists"] and value["output_sha256"] == digest(project / "exports/project.pck")
                    report["project_pack_sha256"] = value["output_sha256"]
                    check("native preset project pack export with actual output hash")
                    value = apply(
                        "project_export",
                        preset="Scene Pack",
                        format="zip",
                        debug=False,
                        destination="res://exports/project.zip",
                    )
                    assert value["output_sha256"] == digest(project / "exports/project.zip"), value
                    import zipfile

                    with zipfile.ZipFile(project / "exports/project.zip") as archive:
                        assert archive.testzip() is None
                        assert "project.binary" in archive.namelist()
                    check("native ZIP export succeeds through project destination with actual archive validation")
                    value = apply(
                        "project_export",
                        preset="Scene Mac",
                        format="zip",
                        debug=False,
                        destination="res://exports/macos-pack.zip",
                    )
                    assert value["output_sha256"] == digest(project / "exports/macos-pack.zip"), value
                    for preset_name in ("Scene Mac Nonempty Helpers", "Scene Mac Nonempty Options"):
                        rejected = route(
                            "project_export",
                            preset=preset_name,
                            format="zip",
                            debug=False,
                            destination="res://exports/rejected.zip",
                        )[1]
                        assert rejected["error"] == "credential_export_not_supported", rejected
                    check(
                        "disabled macOS signing accepts empty native collections and rejects nonempty credential collections"
                    )
                    if args.macos_template:
                        value = apply(
                            "project_export",
                            preset="Scene Mac",
                            format="project",
                            debug=False,
                            destination="res://exports/scene.app",
                        )
                        assert value["output_exists"] and value["output_directory"] and value["output_sha256"], value
                        import plistlib

                        info = plistlib.loads((project / "exports/scene.app/Contents/Info.plist").read_bytes())
                        assert (project / "exports/scene.app/Contents/MacOS" / info["CFBundleExecutable"]).is_file()
                        report["macos_application_sha256"] = value["output_sha256"]
                        check(
                            "unsigned arm64 macOS application exports through confirmed API using pinned private template"
                        )

                    deadline = time.monotonic() + 10
                    while command("snapshot")["scanning"] and time.monotonic() < deadline:
                        time.sleep(0.1)
                    message, preview = route(
                        "project_export",
                        preset="Scene Pack",
                        format="pack",
                        debug=False,
                        destination="res://exports/project.pck",
                    )
                    assert preview.get("confirmation_required"), preview
                    cache = project / ".godot/global_script_class_cache.cfg"
                    cache.write_bytes(cache.read_bytes() + b"\n")
                    assert approve(message)["error"] == "scene_changed_since_confirmation"
                    message, preview = route(
                        "project_export",
                        preset="Scene Pack",
                        format="pack",
                        debug=False,
                        destination="res://exports/project.pck",
                    )
                    assert preview.get("confirmation_required"), preview
                    receipt = project / ".godot/editor/approval-receipt.json"
                    receipt.parent.mkdir(exist_ok=True)
                    receipt.write_text("{}")
                    assert approve(message)["ok"]
                    check("PCK binds global class cache; editor receipts preserve approval validity")
                    deadline = time.monotonic() + 10
                    while command("snapshot")["scanning"] and time.monotonic() < deadline:
                        time.sleep(0.1)
                    message, preview = route(
                        "project_export",
                        preset="Scene Pack",
                        format="project",
                        debug=False,
                        destination="res://exports/project.x86_64",
                    )
                    assert preview.get("confirmation_required"), preview
                    value = approve(message)
                    assert (
                        not value["ok"]
                        and value["error"] == "project_export_unavailable"
                        and value["missing_templates"]
                    ), value
                    report["project_application_export"] = value["error"]
                    check("application export missing templates is a real failure, no download")
                    assert (
                        route(
                            "scene_assign_resource",
                            target="Line",
                            property="gradient",
                            resource_path="res://../outside.tres",
                        )[1]["error"]
                        == "invalid_project_path"
                    )
                    command("tools", value=False)
                    assert not route("scene_set_property", target="Receiver", property="position", value=[1, 1])[1][
                        "ok"
                    ]
                    command("tools", value=True)
                    command("consultation", value=True)
                    assert not route("scene_set_property", target="Receiver", property="position", value=[1, 1])[1][
                        "ok"
                    ]
                    command("consultation", value=False)
                    check("path/tool/consultation boundaries")
                    assert route("open_scene", target="res://derived.tscn")[1]["ok"]
                    time.sleep(0.2)
                    apply("scene_set_property", target="Inherited", property="position", value=[7, 8])
                    assert (
                        route("scene_delete_node", target="Inherited")[1]["error"] == "inherited_or_foreign_structure"
                    )
                    apply("scene_create_node", target=".", type="Node2D", name="Added")
                    assert command("snapshot", path="Added")["owner"] == "."
                    check("inherited property override and local addition; inherited structure protected")
                    command("finish")
                    report["editor_exit_code"] = process.wait(timeout=30)
                    assert report["editor_exit_code"] == 0, report["editor_exit_code"]
                    assert "SCRIPT ERROR:" not in log_path.read_text()
                    report["ok"] = True
                finally:
                    if process.poll() is None:
                        process.terminate()
                        process.wait(timeout=20)
                    report["log_tail"] = log_path.read_text()[-12000:]
    except Exception as error:
        report["error"] = repr(error)
        report["traceback"] = traceback.format_exc()
    report["real_settings_after"] = digest(real_settings)
    report["real_settings_unchanged"] = report["real_settings_before"] == report["real_settings_after"]
    report["ok"] = report["ok"] and report["real_settings_unchanged"]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
