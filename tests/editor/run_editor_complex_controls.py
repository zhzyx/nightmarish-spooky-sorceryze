"""Complex native controls through the real isolated headless editor and HTTP host confirmation."""

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from editor_test_isolation import copy_editor
from run_editor_capability_routing import await_file


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--case", choices=["all", "resources", "native_graph"], default="all")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("client", repo / "tools/editor_control_client.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    results = []
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.unlink(missing_ok=True)
    with tempfile.TemporaryDirectory(prefix="complex-controls-") as directory:
        project = Path(directory)
        editor = copy_editor(args.godot, project / "private-editor")
        (editor.parent / "editor_data/editor_settings-4.8.tres").write_text(
            '[gd_resource type="EditorSettings" format=3]\n[resource]\nai_chat/editor_control_bridge_enabled = true\nai_chat/endpoint = ""\n',
            encoding="utf-8",
        )
        (project / "project.godot").write_text(
            'config_version=5\n[application]\nconfig/name="Complex fixture"\n', encoding="utf-8"
        )
        shutil.copyfile(Path(__file__).with_name("editor_complex_controls.gd"), project / "test.gd")
        with (project / "editor.log").open("w", encoding="utf-8") as log:
            process = subprocess.Popen(
                [str(editor), "--headless", "--editor", "--path", str(project), "--script", "res://test.gd"],
                cwd=project,
                env={**os.environ, "GODOT_AI_API_KEY": ""},
                stdout=log,
                stderr=log,
            )
            try:
                ready = await_file(project / "ready.json", process, 40)
                client = module.EditorClient(project)
                sequence = 0

                def command(action="snapshot", **values):
                    nonlocal sequence
                    sequence += 1
                    pending = project / "command.pending"
                    pending.write_text(json.dumps({"action": action, "id": sequence, **values}), encoding="utf-8")
                    pending.replace(project / "command.json")
                    return await_file(project / f"ack-{sequence}.json", process)

                def route(action, label, **values):
                    nonlocal sequence
                    sequence += 1
                    matches = client.capabilities(label)["targets"]
                    exact = [entry for entry in matches if entry["display_name"] == label]
                    assert exact, (label, matches)
                    message = {
                        "intent": "engine_operation",
                        "request_id": f"complex-{sequence}",
                        "source": "acceptance",
                        "operation": {"action": action, "target": exact[0]["id"], **values},
                    }
                    return message, client.route(message)

                def confirmed(action, label, **values):
                    message, preview = route(action, label, **values)
                    assert preview.get("confirmation_required"), preview
                    state = command("approve")
                    result = client.status(message["request_id"], "acceptance")
                    assert result["ok"], result
                    return state, result

                if args.case == "all":
                    command("popup")
                    assert client.capabilities("ComplexMenu")["targets"][0]["class"] == "PopupMenu"
                    # Wait for native startup work using a read-only request.
                    ready_deadline = time.monotonic() + 20
                    _, read = route("read_menu_items", "ComplexMenu", limit=1, offset=0)
                    while read.get("error") == "editor_busy" and time.monotonic() < ready_deadline:
                        time.sleep(0.05)
                        _, read = route("read_menu_items", "ComplexMenu", limit=1, offset=0)
                    assert read["items"][0]["id"] == 73 and read["next_offset"] == 1, read
                    message, preview = route("activate_menu_item", "ComplexMenu", index=0)
                    assert preview["confirmation_required"] and not command()["menu_ids"]
                    command("menu_mutate")
                    command("approve")
                    assert (
                        client.status(message["request_id"], "acceptance")["error"]
                        == "target_changed_since_confirmation"
                    )
                    for mutation in ["menu_metadata", "menu_context"]:
                        command("popup")
                        message, preview = route("activate_menu_item", "ComplexMenu", index=0)
                        assert preview["confirmation_required"], preview
                        command(mutation)
                        command("approve")
                        assert (
                            client.status(message["request_id"], "acceptance")["error"]
                            == "target_changed_since_confirmation"
                        )
                    seeded = command("menu_history_seed")
                    assert seeded["global_history_id"] == 0, seeded
                    command("popup")
                    message, preview = route("activate_menu_item", "ComplexMenu", index=0)
                    assert preview["confirmation_required"], preview
                    reused = command("menu_history_reuse")
                    assert reused["menu_history_version_reused"], reused
                    command("approve")
                    rejected = client.status(message["request_id"], "acceptance")
                    assert rejected["error"] == "target_changed_since_confirmation", rejected
                    command("popup")
                    state, done = confirmed("activate_menu_item", "ComplexMenu", index=0)
                    assert state["menu_ids"] == [73] and done["requested"] and not done["business_completed"]
                    assert client.capabilities("ComplexLaterMenu")["targets"], "Deferred PopupMenu not discovered"
                    results.append(
                        "PopupMenu Window discovery, pagination, label/metadata/selection stale guards, native ID activation, deferred lifecycle"
                    )
                    command("popup")
                    message, preview = route("open_menu_submenu", "ComplexMenu", index=3)
                    assert preview["confirmation_required"], preview
                    command("replace_submenu")
                    command("approve")
                    assert (
                        client.status(message["request_id"], "acceptance")["error"]
                        == "target_changed_since_confirmation"
                    )
                    command("popup")
                    message, preview = route("open_menu_submenu", "ComplexMenu", index=3)
                    assert preview["confirmation_required"], preview
                    command("mutate_menu_on_popup")
                    command("approve")
                    requested = client.status(message["request_id"], "acceptance")
                    assert requested["requested"] and not requested["business_completed"], requested
                    command("await_submenu")
                    parent = client.capabilities("ComplexMenu")["targets"][0]
                    assert parent["submenu_request_status"] == "stale", parent
                    for mutation, expected in [
                        ("close_parent_on_popup", "not_visible"),
                        ("replace_submenu_on_popup", "stale"),
                    ]:
                        command("popup")
                        message, preview = route("open_menu_submenu", "ComplexMenu", index=3)
                        assert preview["confirmation_required"], preview
                        command(mutation)
                        command("approve")
                        command("await_submenu")
                        parent = client.capabilities("ComplexMenu")["targets"][0]
                        assert parent["submenu_request_status"] == expected, parent
                    command("popup")
                    state, opened = confirmed("open_menu_submenu", "ComplexMenu", index=3)
                    assert (
                        opened["submenu_request_status"] == "queued"
                        and opened["requested"]
                        and not opened["business_completed"]
                    ), opened
                    command("await_submenu")
                    parent = client.capabilities("ComplexMenu")["targets"][0]
                    assert parent["submenu_request_status"] == "opened", parent
                    _, leaf = route("read_menu_items", "ComplexSubmenu")
                    assert leaf.get("ok") and leaf.get("items", [])[0]["id"] == 91, leaf
                    state, _ = confirmed("activate_menu_item", "ComplexSubmenu", index=0)
                    assert state["menu_ids"] == [73, 91], state
                    results.append(
                        "Popup native delayed submenu state machine opens persistent nested Window; replacement/reopen drift rejected; leaf business ID read back"
                    )
                    command("popup")
                    message, _ = route("activate_menu_item", "ComplexMenu", index=0)
                    replacement = command("replace_menu")
                    command("approve")
                    assert (
                        client.status(message["request_id"], "acceptance")["error"]
                        == "target_changed_since_confirmation"
                    )
                    assert replacement["ids"]["ComplexMenu"], replacement
                    results.append("PopupMenu replacement instance rejected")

                    for action, value, expected in [
                        ("graph_connect", {"from": "Source", "from_port": 0, "to": "Destination", "to_port": 0}, 1),
                        ("graph_disconnect", {"from": "Source", "from_port": 0, "to": "Destination", "to_port": 0}, 0),
                    ]:
                        state, done = confirmed(action, "ComplexGraph", value=value)
                        assert len(state["model_links"]) == expected and state["graph_connections"] == expected, (
                            state,
                            done,
                        )
                        assert done["requested"] and not done["business_completed"]
                        _, read = route("read_graph_connections", "ComplexGraph")
                        assert len(read["items"]) == expected, read
                    state, done = confirmed(
                        "graph_move_node", "ComplexGraph", value={"node": "Source", "position": [30, 40]}
                    )
                    assert state["model_position"] == [30, 40] and not done["business_completed"], (state, done)
                    _, read = route("read_graph_nodes", "ComplexGraph")
                    assert len(read["items"]) == 2 and read["items"][0]["ports"], read
                    _, ports = route(
                        "read_graph_ports",
                        "ComplexGraph",
                        value={"node": "Source", "direction": "output"},
                        limit=1,
                        offset=0,
                    )
                    assert ports["total"] == 1 and ports["items"][0]["index"] == 0 and ports["next_offset"] == -1, ports
                    results.append(
                        "Graph ports/connections read, deferred native owner connect/disconnect, dragged owner model movement"
                    )
                    for action, label in [
                        ("activate_item", "ComplexItems"),
                        ("activate_tree_item", "ComplexTree"),
                        ("item_context_menu", "ComplexItems"),
                        ("tree_context_menu", "ComplexTree"),
                    ]:
                        message, preview = route(action, label, index=0)
                        assert preview["confirmation_required"], preview
                        command("item_metadata" if label == "ComplexItems" else "tree_metadata")
                        command("approve")
                        rejected = client.status(message["request_id"], "acceptance")
                        assert rejected["error"] == "target_changed_since_confirmation", rejected
                        state, done = confirmed(action, label, index=0)
                        assert done["requested"] and not done["business_completed"], done
                    assert state["activations"] == 2 and state["contexts"] == 2, state
                    results.append("Tree/ItemList native accept and context business handlers")

                if args.case != "native_graph":
                    state = command("curve")
                    assert state["ids"]["ComplexCurve"], state
                    _, read = route("read_curve", "ComplexCurve")
                    assert len(read["items"]) == 2, read
                    assert (
                        isinstance(read["state"]["resource_instance"], str)
                        and int(read["state"]["resource_instance"]) >= 2**63
                    )
                    state, done = confirmed("curve_preset", "ComplexCurve", value=0)
                    assert state["curve_first_y"] == 0.5 and done["business_completed"], (state, done)
                    state, done = confirmed("undo_resource_edit", "ComplexCurve")
                    assert state["curve_first_y"] == 0.25 and done["business_completed"], (state, done)
                    results.append("Real Inspector CurveEdit resource preset and native UndoRedo state restoration")

                    def resource_items(kind, label):
                        _, readback = route(kind, label)
                        assert readback["ok"], readback
                        return readback["items"]

                    def roundtrip_resource(action, label, kind, **values):
                        before_items = resource_items(kind, label)
                        state, result = confirmed(action, label, **values)
                        after_items = resource_items(kind, label)
                        assert after_items != before_items and result["business_completed"], (action, result)
                        confirmed("undo_resource_edit", label)
                        assert resource_items(kind, label) == before_items, (action, "undo did not restore every point")
                        confirmed("redo_resource_edit", label)
                        assert resource_items(kind, label) == after_items, (action, "redo did not restore every point")
                        confirmed("undo_resource_edit", label)
                        assert resource_items(kind, label) == before_items
                        return after_items

                    points = roundtrip_resource("curve_add_point", "ComplexCurve", "read_curve", value=[0.3, 0.6])
                    assert len(points) == 3 and abs(points[1]["position"][0] - 0.3) < 0.00001
                    confirmed("curve_add_point", "ComplexCurve", value=[0.3, 0.6])
                    points = roundtrip_resource(
                        "curve_set_point", "ComplexCurve", "read_curve", index=0, value=[0.8, 0.4]
                    )
                    assert (
                        abs(points[1]["position"][0] - 0.8) < 0.00001 and abs(points[1]["position"][1] - 0.4) < 0.00001
                    )
                    points = roundtrip_resource(
                        "curve_set_tangents", "ComplexCurve", "read_curve", index=1, value=[0.25, -0.5]
                    )
                    assert points[1]["left_tangent"] == 0.25 and points[1]["right_tangent"] == -0.5
                    points = roundtrip_resource(
                        "curve_set_tangent_modes", "ComplexCurve", "read_curve", index=1, value=[1, 1]
                    )
                    assert points[1]["left_mode"] == 1 and points[1]["right_mode"] == 1
                    points = roundtrip_resource("curve_remove_point", "ComplexCurve", "read_curve", index=1)
                    assert len(points) == 2
                    for action, values, error in [
                        ("curve_add_point", {"value": [0.3, 0.5]}, "curve_duplicate_offset"),
                        ("curve_set_point", {"index": 0, "value": [2, 0.5]}, "curve_point_out_of_range"),
                        ("curve_set_tangents", {"index": 0, "value": [1000001, 0]}, "invalid_curve_tangent"),
                        ("curve_set_tangent_modes", {"index": 0, "value": [0.5, 1]}, "invalid_curve_tangent_mode"),
                        ("curve_remove_point", {"index": 99}, "invalid_item_index"),
                    ]:
                        _, rejected = route(action, "ComplexCurve", **values)
                        assert rejected["error"] == error, rejected
                    message, _ = route("curve_set_point", "ComplexCurve", index=0, value=[0.1, 0.2])
                    command("curve_mutate")
                    command("approve")
                    assert (
                        client.status(message["request_id"], "acceptance")["error"]
                        == "target_changed_since_confirmation"
                    )
                    message, pending = route("curve_set_point", "ComplexCurve", index=0, value=[0.1, 0.2])
                    assert pending["confirmation_required"], pending
                    command("script_curve")
                    command("approve")
                    assert (
                        client.status(message["request_id"], "acceptance")["error"]
                        == "script_or_extension_resource_not_supported"
                    )
                    _, rejected = route("read_curve", "ComplexCurve")
                    assert rejected["error"] == "script_or_extension_resource_not_supported", rejected
                    _, rejected = route("curve_preset", "ComplexCurve", value=0)
                    assert rejected["error"] == "script_or_extension_resource_not_supported", rejected
                    assert not command()["unsafe_called"]
                    command("clear_curve_script")
                    results.append(
                        "Curve add/delete/reorder/left-right tangents/modes: full point Undo/Redo, finite/range/order/stale/script rejection"
                    )
                    state = command("gradient")
                    assert state["ids"]["ComplexGradient"], state
                    state, done = confirmed("gradient_set_color", "ComplexGradient", index=0, value=[1, 0, 0, 1])
                    assert state["gradient_first"] == "ff0000ff" and done["business_completed"], (state, done)
                    state, done = confirmed("undo_resource_edit", "ComplexGradient")
                    assert state["gradient_first"] == "000000ff", (state, done)
                    confirmed("gradient_set_color", "ComplexGradient", index=0, value=[1, 0, 0, 1])
                    confirmed("gradient_set_color", "ComplexGradient", index=0, value=[0, 1, 0, 1])
                    state, _ = confirmed("undo_resource_edit", "ComplexGradient")
                    assert state["gradient_first"] == "ff0000ff", "Native MERGE_ENDS absorbed an earlier command"
                    confirmed("gradient_set_color", "ComplexGradient", index=0, value=[0, 1, 0, 1])
                    command("history_mutate")
                    _, denied = route("undo_resource_edit", "ComplexGradient")
                    assert denied["error"] == "undo_unavailable", denied

                    confirmed("gradient_set_color", "ComplexGradient", index=0, value=[1, 0, 0, 1])
                    reused = command("history_reuse")
                    assert reused["history_version_reused"], reused
                    _, denied = route("undo_resource_edit", "ComplexGradient")
                    assert denied["error"] == "undo_unavailable", denied
                    state, _ = confirmed("gradient_add_point", "ComplexGradient", value=[0.5, 1, 0, 0, 1])
                    assert state["gradient_count"] == 3
                    state, _ = confirmed("gradient_remove_point", "ComplexGradient", index=1)
                    assert state["gradient_count"] == 2
                    state, _ = confirmed("undo_resource_edit", "ComplexGradient")
                    assert state["gradient_count"] == 3
                    points = roundtrip_resource("gradient_reverse", "ComplexGradient", "read_gradient")
                    assert points[0]["color"] == [1, 1, 1, 1], points
                    message, _ = route("gradient_set_color", "ComplexGradient", index=0, value=[1, 0, 0, 1])
                    command("resource_mutate")
                    command("approve")
                    assert (
                        client.status(message["request_id"], "acceptance")["error"]
                        == "target_changed_since_confirmation"
                    )
                    results.append(
                        "Real Inspector GradientEdit add/remove/recolor/reverse, non-merging UndoRedo, unrelated history and stale resource guards"
                    )
                    confirmed("gradient_add_point", "ComplexGradient", value=[0.25, 1, 0, 0, 1])
                    confirmed("gradient_add_point", "ComplexGradient", value=[0.6, 0, 0, 1, 1])
                    before_offset = resource_items("read_gradient", "ComplexGradient")
                    original_index = next(
                        i for i, point in enumerate(before_offset) if abs(point["offset"] - 0.25) < 0.00001
                    )
                    points = roundtrip_resource(
                        "gradient_set_offset", "ComplexGradient", "read_gradient", index=original_index, value=0.8
                    )
                    moved = next(point for point in points if abs(point["offset"] - 0.8) < 0.00001)
                    assert moved["color"] == [1, 0, 0, 1], moved
                    command("resource_mutate")
                    _, rejected = route("redo_resource_edit", "ComplexGradient")
                    assert rejected["error"] == "redo_unavailable", rejected
                    for value, error in [(0.6, "gradient_duplicate_offset"), (-0.1, "invalid_gradient_offset")]:
                        _, rejected = route("gradient_set_offset", "ComplexGradient", index=original_index, value=value)
                        assert rejected["error"] == error, rejected
                    message, _ = route("gradient_set_offset", "ComplexGradient", index=original_index, value=0.8)
                    command("resource_mutate")
                    command("approve")
                    assert (
                        client.status(message["request_id"], "acceptance")["error"]
                        == "target_changed_since_confirmation"
                    )
                    results.append(
                        "Gradient offset preserves point colors across sorted indices with complete Undo/Redo and duplicate/range/stale rejection"
                    )
                if args.case in {"all", "native_graph"}:
                    command("native_graph")
                    _, nodes = route("read_graph_nodes", "ComplexNativeGraph")
                    assert {node["name"] for node in nodes["items"]} >= {"0", "2"}, nodes
                    native_link = {"from": "2", "from_port": 0, "to": "0", "to_port": 0}
                    state, result = confirmed("graph_connect", "ComplexNativeGraph", value=native_link)
                    assert len(state["native_shader_connections"]) == 1 and not result["business_completed"], (
                        state,
                        result,
                    )
                    state, result = confirmed("graph_disconnect", "ComplexNativeGraph", value=native_link)
                    assert state["native_shader_connections"] == [] and not result["business_completed"], (
                        state,
                        result,
                    )
                    state, result = confirmed(
                        "graph_move_node", "ComplexNativeGraph", value={"node": "2", "position": [70, 80]}
                    )
                    assert state["native_shader_position"] == [70, 80] and not result["business_completed"], (
                        state,
                        result,
                    )
                    results.append(
                        "Built-in C++ VisualShader owner: native connect/disconnect/dragged update actual shader resource connections and node position"
                    )
                command("permission", value=False)
                assert (
                    client.route({
                        "intent": "engine_operation",
                        "request_id": "denied",
                        "source": "acceptance",
                        "operation": {"action": "read_graph_nodes", "target": ready["ids"]["ComplexGraph"]},
                    })["error"]
                    == "permission_denied"
                )
                command("permission", value=True)
                command("consultation", value=True)
                assert (
                    client.route({
                        "intent": "engine_operation",
                        "request_id": "consultation",
                        "source": "acceptance",
                        "operation": {"action": "read_graph_nodes", "target": ready["ids"]["ComplexGraph"]},
                    })["error"]
                    == "permission_denied"
                )
                command("consultation", value=False)
                results.append("Tool permission and consultation denial retained")
                (project / "finish").touch()
                process.wait(timeout=20)
                assert process.returncode == 0
                args.report.write_text(
                    json.dumps({"ok": True, "checks": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
                print("EDITOR_COMPLEX_CONTROLS_HTTP_OK")
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=10)
                log.flush()
                output = (project / "editor.log").read_text(encoding="utf-8", errors="replace")
                args.report.with_suffix(".editor.log").write_text(output, encoding="utf-8")
                print(output)


if __name__ == "__main__":
    main()
