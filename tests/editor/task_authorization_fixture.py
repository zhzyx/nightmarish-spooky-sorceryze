"""Isolated model responses for the native UI task-grant scenario."""

import json
import time


def external_checks(project, errors):
    """A separate bridge client never receives the chat's task grant."""
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
    from editor_control_client import EditorClient

    try:
        deadline = time.monotonic() + 300
        while not (project / "external-ready").exists():
            assert time.monotonic() < deadline, "External readiness timeout"
            time.sleep(0.05)
        client = EditorClient(project)
        for name in ("external", "resource_drift", "drift"):
            operation = {"action": "scene_rename_node", "target": "GrantSprite", "name": "ExternalMutation"}
            if name == "resource_drift":
                operation = {
                    "action": "scene_assign_resource",
                    "target": "GrantMesh",
                    "property": "mesh",
                    "resource_path": "res://grant-mesh.tres",
                }
            result = client.route({
                "intent": "engine_operation",
                "source": "task-grant-external",
                "request_id": name,
                "operation": operation,
            })
            print("TASK_EXTERNAL_PREVIEW", name, json.dumps(result), flush=True)
            assert result.get("confirmation_required") and result.get("manual_confirmation_required"), result
            (project / (name + "-preview")).write_text("ready")
            while not (project / (name + "-resolved")).exists():
                assert time.monotonic() < deadline, "External resolution timeout"
                time.sleep(0.03)
            result = client.status(name, "task-grant-external")
            print("TASK_EXTERNAL_RESULT", name, json.dumps(result), flush=True)
            assert not result.get("ok"), result
            if name == "resource_drift":
                assert result.get("error") == "scene_changed_since_confirmation", result
            if name == "drift":
                assert result.get("error") == "node_not_found", result
        terminal = "passed"
    except Exception as exc:
        errors.append("External boundary: " + str(exc))
        terminal = "failed"
    # The scene polls existence; publish only after the complete verdict is written.
    pending = project / "external-done.pending"
    pending.write_text(terminal)
    pending.replace(project / "external-done")


def tool(name, arguments, identifier):
    return {"id": identifier, "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}


def completion(content="", calls=None):
    message = {"role": "assistant", "content": content}
    if calls:
        message["tool_calls"] = calls
    return message


def response(case, results, project):
    print("TASK_FIXTURE_STEP", case, len(results), flush=True)
    if results:
        print("TASK_FIXTURE_RESULT", case, results[-1], flush=True)
    if case == "task_grant_unsaved":
        if not results:
            return completion(
                calls=[
                    tool(
                        "write_file",
                        {"path": "res://fixture.gd", "content": "extends Node\n# MODEL_OVERWRITE\n"},
                        "unsaved",
                    )
                ]
            )
        assert "unsaved editor changes" in results[-1], results[-1]
        return completion("TASK_UNSAVED_OK")
    if case == "task_grant_extended":
        if not results and (project / "grant-png.bytes").exists():
            assert not (project / "grant.png").exists()
            assert not (project / "grant.png.import").exists()
            (project / "grant.png").write_bytes((project / "grant-png.bytes").read_bytes())
            assert not (project / "grant.png.import").exists()
            print("TASK_FIRST_IMPORT_UNIMPORTED", flush=True)
        steps = [
            ("scene_import_resource", {"resource_path": "res://grant.png"}),
            ("scene_create_node", {"target": ".", "type": "Sprite2D", "name": "GrantSprite"}),
            (
                "scene_assign_resource",
                {"target": "GrantSprite", "property": "texture", "resource_path": "res://grant.png"},
            ),
            ("run_scene", {"target": "res://input_game.tscn"}),
            ("game_input_query", {}),
            ("game_input_state", {}),
            ("game_action_pulse", {}),
            ("game_input_state", {}),
            ("stop_project", {}),
            (
                "scene_assign_resource",
                {"target": "GrantMesh", "property": "mesh", "resource_path": "res://grant-mesh.tres"},
            ),
        ]
        n = len(results)
        if results:
            assert json.loads(results[-1]).get("ok"), results[-1]
        if n == 1 and (project / "grant-png.bytes").exists():
            imported = json.loads(results[-1])
            assert imported["old_value"]["res://grant.png.import"] == "", imported
            assert imported["import_valid"] and imported["import_metadata_sha256"], imported
            print("TASK_FIRST_IMPORT_NATIVE_OK", flush=True)
        if n in (4, 5, 7):
            time.sleep(1)
        if n == 6:
            state = json.loads(results[-1])["state"]
            assert state["receipt"]["status"] == "observed", state
            steps[6] = (
                "game_action_pulse",
                {
                    "value": {
                        "name": "fixture_move",
                        "duration": 0.2,
                        "strength": 0.75,
                        "request_id": "grant-pulse",
                        "runtime_token": state["receipt"]["runtime_token"],
                    }
                },
            )
        if n == 7:
            submitted = json.loads(results[-1])
            assert submitted["requested"] is True and submitted["business_completed"] is False, submitted
            assert submitted["readback_action"] == "game_input_state", submitted
        if n == 8:
            receipt = json.loads(results[-1])["state"]["last_action_receipt"]
            assert (
                receipt["request_id"] == "grant-pulse"
                and receipt["status"] == "released"
                and receipt["ok"]
                and receipt["strength"] == 0
            ), receipt
            game = json.loads((project / "game-state.json").read_text())
            assert game["observed"] and not game["pressed"], game
            assert game["press_usec"] >= 0 and game["release_usec"] > game["press_usec"], game
            assert abs(game["peak_strength"] - 0.75) < 0.001, game
            assert abs(game["min_pressed_strength"] - 0.75) < 0.001 and game["strength"] == 0, game
            # Bound sampling jitter to two observed frames, with a fixed 60 ms cap.
            # A stalled sampler fails rather than widening acceptance indefinitely.
            assert game["max_frame_usec"] <= 30000, game
            tolerance = max(0.02, 2 * game["max_frame_usec"] / 1_000_000)
            assert abs(game["duration_seconds"] - 0.2) <= tolerance, game
            game["duration_tolerance_seconds"] = tolerance
            print("TASK_RUNTIME_OBSERVED", json.dumps(game), flush=True)
        if n == len(steps):
            return completion("TASK_EXTENDED_OK")
        action, args = steps[n]
        return completion(calls=[tool("editor_action", {"action": action, **args}, "extended" + str(n))])
    if case == "task_grant_special":
        if not results:
            return completion(
                calls=[
                    tool(
                        "editor_action",
                        {
                            "action": "scene_export_resource",
                            "target": "GrantMesh",
                            "property": "mesh",
                            "destination": "res://exported.tres",
                        },
                        "special",
                    )
                ]
            )
        assert results[-1].startswith("User rejected the action."), results[-1]
        return completion("TASK_SPECIAL_REFUSED")
    if case in {"task_grant_stale", "task_grant_stop"} and not results:
        (project / (case + "-inflight")).write_text("queued")
        time.sleep(2)
    if case != "task_grant_continuous":
        if not results:
            response = completion(
                calls=[
                    tool(
                        "editor_action",
                        {
                            "action": "scene_create_node",
                            "target": ".",
                            "type": "Node2D",
                            "name": "Unauthorized",
                            "task_native_authorization": True,
                        },
                        "denied",
                    )
                ]
            )
        else:
            assert not json.loads(results[-1]).get("ok", False) if results[-1].startswith("{") else True
            response = completion("TASK_BOUNDARY_OK")
    else:
        steps = [
            ("editor_action", {"action": "scene_create_node", "target": ".", "type": "Node2D", "name": "Authorized"}),
            ("editor_action", {"action": "run_scene", "target": "res://task_game.tscn"}),
            ("read_file", {"path": "res://runtime-error.txt"}),
            ("editor_action", {"action": "stop_project"}),
            (
                "write_file",
                {
                    "path": "res://task_game.gd",
                    "content": 'extends Node2D\nfunc _ready():\n\tprint("TASK_REPAIRED_OK")\n\tFileAccess.open("res://runtime-error.txt", FileAccess.WRITE).store_string("TASK_REPAIRED_OK")\n\tget_tree().create_timer(3).timeout.connect(get_tree().quit)\n',
                },
            ),
            ("editor_action", {"action": "run_scene", "target": "res://task_game.tscn"}),
            ("read_file", {"path": "res://runtime-error.txt"}),
            ("editor_action", {"action": "stop_project"}),
        ]
        if len(results) in (2, 6):
            time.sleep(1.5)
        if len(results) == 3:
            assert "TASK_PRESEEDED_ERROR" in results[-1], results[-1]
        if len(results) == 7:
            assert "TASK_REPAIRED_OK" in results[-1], results[-1]
        if results and len(results) not in (3, 5, 7):
            assert json.loads(results[-1]).get("ok", False), results[-1]
        response = (
            completion(calls=[tool(*steps[len(results)], "step" + str(len(results)))])
            if len(results) < len(steps)
            else completion("TASK_CONTINUOUS_OK")
        )
    return response
