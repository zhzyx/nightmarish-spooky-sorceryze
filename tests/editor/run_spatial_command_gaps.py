"""Private native HTTP/confirmation regression for spatial editor commands."""

import argparse
import hashlib
import importlib.util
import json
import math
import os
import subprocess
import tempfile
import time
import traceback
from pathlib import Path

from editor_test_isolation import copy_editor


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def wait_json(path, process):
    deadline = time.monotonic() + 60
    while not path.exists():
        if process.poll() is not None or time.monotonic() > deadline:
            raise AssertionError(f"fixture unavailable {path.name}: {process.poll()}")
        time.sleep(0.025)
    return json.loads(path.read_text())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("spatial_client", root / "tools/editor_control_client.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    real_settings = Path.home() / "Library/Application Support/Godot/editor_settings-4.8.tres"
    report = {"ok": False, "checks": [], "editor_sha256": sha(args.godot), "real_settings_before": sha(real_settings)}
    try:
        with tempfile.TemporaryDirectory(prefix="spatial-native-") as tmp:
            base = Path(tmp)
            project = base / "project"
            project.mkdir()
            commands = base / "commands"
            commands.mkdir()
            editor = copy_editor(args.godot, base / "engine")
            (editor.parent / "editor_data/editor_settings-4.8.tres").write_text(
                '[gd_resource type="EditorSettings" format=3]\n[resource]\nai_chat/editor_control_bridge_enabled = true\n'
            )
            (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="Spatial Native"\n')
            (project / "fixture.tscn").write_text('[gd_scene format=3]\n[node name="Root" type="Node"]\n')
            (project / "test.gd").write_text(Path(__file__).with_name("spatial_command_gaps.gd").read_text())
            log_path = base / "editor.log"
            with log_path.open("w") as log:
                process = subprocess.Popen(
                    [str(editor), "--headless", "--editor", "--path", str(project), "--script", "res://test.gd"],
                    stdout=log,
                    stderr=log,
                    env={**os.environ, "GODOT_AI_API_KEY": "", "SPATIAL_COMMAND_DIR": str(commands)},
                )
                try:
                    assert wait_json(commands / "ready.json", process)["ok"]
                    client = module.EditorClient(project, instance=process.pid)
                    seq = 0
                    cseq = 0

                    def command(action, **values):
                        nonlocal cseq
                        cseq += 1
                        pending = commands / "command.pending"
                        pending.write_text(json.dumps({"id": cseq, "action": action, **values}))
                        pending.replace(commands / "command.json")
                        return wait_json(commands / f"ack-{cseq}.json", process)

                    def route(action, **values):
                        nonlocal seq
                        for _ in range(50):
                            seq += 1
                            message = {
                                "intent": "engine_operation",
                                "source": "spatial-native",
                                "request_id": f"spatial-{seq}",
                                "operation": {"action": action, **values},
                            }
                            result = client.route(message)
                            if result.get("error") != "editor_busy":
                                return message, result
                            time.sleep(0.1)
                        return message, result

                    def approve(message):
                        assert command("approve")["visible"], message
                        return client.status(message["request_id"], message["source"])

                    def apply(action, **values):
                        message, preview = route(action, **values)
                        assert preview.get("confirmation_required") and preview.get("manual_confirmation_required"), (
                            preview
                        )
                        answer = approve(message)
                        assert answer.get("ok"), answer
                        assert answer["readback"]["ok"], answer
                        return answer

                    def check(text):
                        report["checks"].append(text)

                    opened = route("open_scene", target="res://fixture.tscn")[1]
                    assert opened["ok"], opened
                    time.sleep(0.1)
                    command("setup")
                    assert route("polygon_state", target="Polygon")[1]["ok"]
                    points = [[0, 0], [20, 0], [0, 20]]
                    apply("polygon_set_points", target="Polygon", value=points)
                    assert command("snapshot")["points"] == points
                    command("undo")
                    assert command("snapshot")["points"] == [[0, 0], [10, 0], [0, 10]]
                    command("redo")
                    assert command("snapshot")["points"] == points
                    check("native polygon data mutation, readback, undo and redo")
                    apply("polygon_set_points", target="Collision", value=points)
                    check("native CollisionPolygon2D points")
                    message, preview = route("polygon_set_points", target="Polygon", value=[[0, 0], [30, 0], [0, 30]])
                    assert preview["confirmation_required"]
                    command("mutate_polygon")
                    assert approve(message)["error"] == "spatial_changed_since_confirmation"
                    message, _ = route("polygon_set_points", target="Polygon", value=points)
                    command("replace_polygon")
                    assert approve(message)["error"] == "spatial_changed_since_confirmation"
                    check("confirmation rejects edited or replaced actual node")
                    command("clear_owner")
                    assert (
                        route("polygon_set_points", target="Polygon", value=points)[1]["error"]
                        == "unsupported_scene_target"
                    )
                    command("restore_owner")
                    for target in ("../Polygon", "/root/Polygon", "Polygon:polygon"):
                        assert route("polygon_state", target=target)[1]["error"] == "invalid_node_path"
                    assert route("polygon_set_points", target="Polygon", value=[["invalid", 0]])[1].get("ok") is False
                    check("scene ownership, traversal and invalid point boundaries")
                    for dimension in ("2d", "3d"):
                        state = route("viewport_state", dimension=dimension)[1]
                        assert state["ok"], state
                        value = (
                            {"offset": [25, 40], "zoom": 1.5}
                            if dimension == "2d"
                            else {"position": [1, 2, 3], "distance": 7, "x_rotation": 0.25, "y_rotation": -0.5}
                        )
                        answer = apply("viewport_set_view", dimension=dimension, value=value)
                        for key, expected in value.items():
                            assert answer["readback"]["state"]["camera"][key] == expected, answer
                    assert (
                        route("viewport_set_view", dimension="2d", value={"zoom": 0})[1]["error"]
                        == "invalid_camera_number"
                    )
                    assert (
                        route("viewport_set_view", dimension="3d", index=4, value={"distance": 1})[1]["error"]
                        == "invalid_viewport_index"
                    )
                    assert (
                        route("viewport_set_view", dimension="3d", value={"script": "x"})[1]["error"]
                        == "unsupported_camera_field"
                    )
                    check("actual native 2D pan/zoom and 3D orbit center/angle/distance, bounded field rejection")
                    hit = route("viewport_pick", value={"origin": [0, 0, 5], "direction": [0, 0, -1]})[1]
                    assert hit["ok"] and hit["hit_found"] and hit["hit"]["target"] == "Spatial/Cube", hit
                    assert (
                        route("viewport_pick", value={"origin": [0, 0, 5], "direction": [0, 0, -2]})[1]["error"]
                        == "pick_direction_must_be_normalized"
                    )
                    command("select_spatial")
                    answer = apply(
                        "viewport_transform_selection",
                        target="Spatial",
                        value={"mode": "translate", "space": "world", "delta": [1, 2, 3]},
                    )
                    assert answer["readback"]["state"]["transform"][3] == [1, 2, 3], answer
                    command("undo")
                    assert route("viewport_selection_state", target="Spatial")[1]["state"]["transform"][3] == [0, 0, 0]
                    command("redo")
                    apply(
                        "viewport_transform_selection",
                        target="Spatial",
                        value={"mode": "rotate", "space": "local", "delta": [0, 0.25, 0]},
                    )
                    apply(
                        "viewport_transform_selection",
                        target="Spatial",
                        value={"mode": "scale", "space": "view", "delta": [2, 2, 2]},
                    )
                    message, _ = route(
                        "viewport_transform_selection",
                        target="Spatial",
                        value={"mode": "translate", "space": "view", "delta": [0, 1, 0]},
                    )
                    command("clear_selection")
                    assert approve(message)["error"] == "viewport_requires_actual_single_selection"
                    check(
                        "native world ray mesh hit and selected-object world/local/view delta transform plus undo and selection drift rejection"
                    )
                    command("select_spatial")
                    command("huge_scale")
                    assert (
                        route(
                            "viewport_transform_selection",
                            target="Spatial",
                            value={"mode": "scale", "space": "local", "delta": [100, 1, 1]},
                        )[1]["error"]
                        == "invalid_resulting_viewport_transform"
                    )
                    command("restore_scale")
                    check("overflowing transform is rejected before native mutation")
                    for dimension, fields in (
                        ("2d", {"offset": [0.3, -0.3], "zoom": 0.3}),
                        ("3d", {"position": [0.3, 0.3, 0.3], "x_rotation": 0.3, "y_rotation": 0.3, "distance": 0.3}),
                    ):
                        readback = apply("viewport_set_view", dimension=dimension, value=fields)["readback"]["state"][
                            "camera"
                        ]
                        for key, requested in fields.items():
                            observed = readback[key]
                            if isinstance(requested, list):
                                assert all(math.isclose(a, b, abs_tol=1e-6) for a, b in zip(requested, observed)), (
                                    readback
                                )
                            else:
                                assert math.isclose(requested, observed, abs_tol=1e-6), readback
                    check(
                        "camera readback accepts real_t quantization for decimal 0.3 while returning actual native values"
                    )
                    animation = {"target": "Player", "animation": "Move"}
                    assert (
                        route("animation_add_track", **animation, track_type=0, path="Spatial", property="offset_left")[
                            1
                        ]["error"]
                        == "animation_property_unavailable_or_not_scalar"
                    )
                    assert (
                        route("animation_add_track", **animation, track_type=0, path="Spatial", property="rotation")[1][
                            "error"
                        ]
                        == "animation_property_unavailable_or_not_scalar"
                    )
                    apply("animation_add_track", **animation, track_type=1, path="Spatial")
                    apply("animation_insert_key", **animation, track=0, time=1, value=[1, 2, 3])
                    answer = apply("animation_move_key", **animation, track=0, key=0, time=2)
                    assert answer["readback"]["state"]["animation_data"]["tracks"][0]["keys"][0]["time"] == 2
                    command("undo")
                    assert (
                        route("animation_state", **animation)[1]["state"]["animation_data"]["tracks"][0]["keys"][0][
                            "time"
                        ]
                        == 1
                    )
                    command("redo")
                    command("edit_player")
                    selected = apply("animation_select_keys", **animation, keys=[{"track": 0, "key": 0}])
                    assert selected["readback"]["state"]["selected_keys"] == [{"track": 0, "key": 0}], selected
                    selected = apply("animation_select_keys", **animation, keys=[])
                    assert selected["readback"]["state"]["selected_keys"] == [], selected
                    check(
                        "actual AnimationTrackEditor key selection and deselection reads back actual native selection"
                    )
                    apply("animation_remove_key", **animation, track=0, key=0)
                    apply("animation_remove_track", **animation, track=0)
                    assert command("snapshot")["tracks"] == 0
                    check("native animation add/remove track, insert/move/remove key and undo/redo")
                    assert (
                        route("animation_add_track", **animation, track_type=5, path="Spatial")[1]["error"]
                        == "invalid_animation_track_definition"
                    )
                    apply("animation_add_track", **animation, track_type=0, path="Polygon", property="visible")
                    assert (
                        route("animation_insert_key", **animation, track=0, time=1, value=1)[1]["error"]
                        == "animation_property_type_mismatch"
                    )
                    apply("animation_insert_key", **animation, track=0, time=1, value=True)
                    copied = route("animation_copy_keys", **animation, keys=[{"track": 0, "key": 0}])[1]
                    assert copied["ok"] and copied["clipboard"][0]["value"] is True, copied
                    apply("animation_paste_keys", **animation, value={"keys": copied["clipboard"], "offset": 1})
                    cut = apply("animation_cut_keys", **animation, keys=[{"track": 0, "key": 1}])
                    assert cut["clipboard"][0]["time"] == 2
                    command("undo")
                    assert (
                        len(route("animation_state", **animation)[1]["state"]["animation_data"]["tracks"][0]["keys"])
                        == 2
                    )
                    command("redo")
                    check("typed internal copy/cut/paste clipboard is atomic and undoable without OS clipboard")
                    assert (
                        route("animation_insert_key", **animation, track=0, time=1, value=False)[1]["error"]
                        == "animation_time_occupied"
                    )
                    message, _ = route("animation_move_key", **animation, track=0, key=0, time=2)
                    command("mutate_animation")
                    assert approve(message)["error"] == "spatial_changed_since_confirmation"
                    command("playing", value=True)
                    assert route("animation_state", **animation)[1]["error"] == "animation_unavailable_or_playing"
                    command("playing", value=False)
                    check("animation forbids event tracks, collisions, resource drift and playing player")
                    cells = [
                        {"coords": [0, 0], "source_id": 0, "atlas_coords": [1, 0]},
                        {"coords": [1, 0], "source_id": 0, "atlas_coords": [0, 0]},
                    ]
                    answer = apply("tilemap_set_cells", target="Tiles", cells=cells)
                    assert answer["readback"]["state"]["cells"][0]["atlas_coords"] == [1, 0]
                    command("undo")
                    observed = route("tilemap_state", target="Tiles", cells=cells)[1]
                    assert observed["state"]["cells"][0]["atlas_coords"] == [0, 0]
                    command("redo")
                    apply("tilemap_set_cells", target="Tiles", cells=[{"coords": [0, 0], "source_id": -1}])
                    assert (
                        route(
                            "tilemap_set_cells",
                            target="Tiles",
                            cells=[{"coords": [1, 1], "source_id": 0, "atlas_coords": [99, 99]}],
                        )[1]["error"]
                        == "unsupported_tile_atlas_or_alternative"
                    )
                    check("native atlas cells paint/erase/readback/undo/redo; invalid atlas rejected")
                    command("tools", value=False)
                    assert route("viewport_state", dimension="2d")[1]["error"] == "permission_denied"
                    command("tools", value=True)
                    command("consultation", value=True)
                    assert route("polygon_state", target="Polygon")[1]["error"] == "permission_denied"
                    command("consultation", value=False)
                    check("host tool permission and consultation gates retained")
                    metadata = command("snapshot")
                    assert not any(
                        str(key).startswith("_ai_chat_spatial")
                        for key in metadata["animation_metadata"] + metadata["tileset_metadata"]
                    ), metadata
                    check("read observations leave animation and tileset serializable metadata unchanged")
                    command("animation_method")
                    assert route("animation_state", **animation)[1]["error"] == "unsupported_animation_or_capacity"
                    check("unsupported existing animation event track fails closed")
                    command("doomed_player")
                    doomed_message, doomed_preview = route(
                        "animation_insert_key", target="DoomedPlayer", animation="Move", track=0, time=0.5, value=False
                    )
                    assert doomed_preview["confirmation_required"], doomed_preview
                    doomed_result = approve(doomed_message)
                    assert doomed_result["error"] == "spatial_readback_failed", doomed_result
                    assert route("polygon_state", target="Polygon")[1]["ok"]
                    check(
                        "animation resource remains alive through changed callback deleting its scene owner; actual failed readback is reported"
                    )
                    command("finish")
                    process.wait(timeout=15)
                    assert process.returncode == 0
                finally:
                    if process.poll() is None:
                        process.terminate()
                        process.wait(timeout=15)
                    report["editor_log_tail"] = log_path.read_text(errors="replace")[-10000:]
        report["ok"] = True
    except Exception:
        report["failure"] = traceback.format_exc()
    report["real_settings_after"] = sha(real_settings)
    report["real_settings_unchanged"] = report["real_settings_before"] == report["real_settings_after"]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    print(json.dumps({"ok": report["ok"], "checks": len(report["checks"]), "report": str(args.report)}))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
