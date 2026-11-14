"""Compile one neutral scene and consume it in server plus two clients."""

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

from RunM2Handshake import run_handshake


def entity(entity_id, name, x):
    return {
        "entity_id": entity_id,
        "name": name,
        "node_type": "Node3D",
        "parent_entity_id": 0,
        "transform": {"translation": [x, 0, 0], "rotation_xyzw": [0, 0, 0, 1], "scale": [1, 1, 1]},
        "gameplay": {"kind": "player_spawn"},
        "assets": [],
    }


def run(command):
    return subprocess.run([str(value) for value in command], capture_output=True, text=True, timeout=30)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--next-asset", type=Path, required=True)
    parser.add_argument("--server", type=Path, required=True)
    parser.add_argument("--client", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    for name in ("next_asset", "server", "client", "report"):
        setattr(args, name, getattr(args, name).resolve())
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=args.report.parent) as temporary:
        root = Path(temporary)
        request = {
            "schema_version": 1,
            "scene": {
                "schema_version": 1,
                "scene_id": "m3.scene",
                "scene_revision": "r9",
                "simulation": {"fixed_step_ms": 20, "max_speed": 4.5},
                "entities": [entity(20, "spawn-b", -3), entity(10, "spawn-a", 2)],
            },
            "assets": [],
        }
        request_path = root / "request.json"
        request_path.write_text(json.dumps(request), encoding="utf-8")
        package = root / "scene.enpak"
        compiled = run([
            args.next_asset,
            "compile",
            "--request",
            request_path,
            "--source-root",
            root,
            "--output",
            package,
        ])
        assert compiled.returncode == 0, compiled.stdout + compiled.stderr
        package_info = json.loads(compiled.stdout)
        result = run_handshake(
            args.server,
            args.client,
            args.report,
            asset_package=package,
        )
        assert result["passed"]
        a_welcome = next(item for item in result["welcomes"] if item["client_id"] == "A" and item["resumed"] == 0)
        scene_config = result["scene_config"]
        expected = (
            scene_config["spawn_x_by_entity"][a_welcome["entity_id"]]
            + 24 * scene_config["max_speed"] * scene_config["fixed_step_ms"] / 1000
        )
        assert abs(result["predictions"][0]["position_x"] - expected) < 0.001
        identity = result["server_scene"][0]
        assert identity["package_digest"] == package_info["package_digest"]
        assert identity["scene_revision"] == "r9"

        no_package = run_handshake(
            args.server,
            args.client,
            root / "no-package.json",
            fixed_step_ms=20,
        )
        assert no_package["passed"] and abs(no_package["predictions"][0]["position_x"] - 3.84) < 0.001
        spawn_rejections = []
        for count in (0, 1, 3):
            bad_request = json.loads(json.dumps(request))
            bad_request["scene"]["entities"] = [entity(10, "spawn-a", 2)] if count == 1 else []
            if count == 3:
                bad_request["scene"]["entities"].append(entity(30, "spawn-c", 5))
            bad_request_path = root / f"request-{count}.json"
            bad_request_path.write_text(json.dumps(bad_request), encoding="utf-8")
            bad_package = root / f"spawn-{count}.enpak"
            bad_compile = run([
                args.next_asset,
                "compile",
                "--request",
                bad_request_path,
                "--source-root",
                root,
                "--output",
                bad_package,
            ])
            if count == 0:
                assert bad_compile.returncode != 0 and "entity_budget" in bad_compile.stdout
                spawn_rejections.append(count)
                continue
            assert bad_compile.returncode == 0, bad_compile.stdout + bad_compile.stderr
            rejected = run([
                args.server,
                "--asset-package",
                bad_package,
                "--bind",
                "127.0.0.1",
                "--port",
                "0",
                "--duration-ms",
                "100",
            ])
            assert rejected.returncode != 0 and "ENGINE_NEXT_SERVER_READY" not in rejected.stdout
            spawn_rejections.append(count)

        conflict = run([args.server, "--asset-package", package, "--fixed-step-ms", "20"])
        assert conflict.returncode == 2
        invalid = root / "invalid.enpak"
        invalid.mkdir()
        invalid_server = run([
            args.server,
            "--asset-package",
            invalid,
            "--bind",
            "127.0.0.1",
            "--port",
            "0",
            "--duration-ms",
            "100",
        ])
        invalid_client = run([
            args.client,
            "--asset-package",
            invalid,
            "--connect",
            "127.0.0.1",
            "--port",
            "1",
            "--duration-ms",
            "100",
        ])
        assert invalid_server.returncode != 0 and "ENGINE_NEXT_SERVER_READY" not in invalid_server.stdout
        assert invalid_client.returncode != 0 and "ENGINE_NEXT_CLIENT_TRANSPORT_CONNECTED" not in invalid_client.stdout
        result["package_compile"] = package_info
        result["invalid_package_rejected_before_transport"] = True
        result["package_fixed_step_override_rejected"] = True
        result["spawn_count_rejected"] = spawn_rejections
        result["no_package_fixed_20"] = {
            "passed": no_package["passed"],
            "position_x": no_package["predictions"][0]["position_x"],
        }
        result["passed"] = True
        args.report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"ENGINE_NEXT_M3_SCENE clients=2 scene_revision=r9 expected_a_position_x={expected} status=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
