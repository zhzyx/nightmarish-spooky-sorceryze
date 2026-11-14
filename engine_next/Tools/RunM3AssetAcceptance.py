"""Exercise the real next_asset CLI in two clean output directories."""

import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path


def run(command, cwd, passed=True):
    result = subprocess.run([str(value) for value in command], cwd=cwd, capture_output=True, text=True, timeout=20)
    if passed and result.returncode != 0:
        raise RuntimeError(result.stdout + result.stderr)
    if not passed and result.returncode == 0:
        raise RuntimeError("Invalid command unexpectedly passed")
    return result


def request(fixture):
    data = (Path(fixture) / "valid.glb").read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    entity = {
        "entity_id": 7,
        "name": "mesh",
        "node_type": "MeshInstance3D",
        "parent_entity_id": 0,
        "transform": {"translation": [0, 0, 0], "rotation_xyzw": [0, 0, 0, 1], "scale": [1, 1, 1]},
        "gameplay": {"kind": "static"},
        "assets": [{"role": "mesh", "asset_id": "mesh", "revision": "r1", "content_sha256": digest}],
    }
    return {
        "schema_version": 1,
        "scene": {
            "schema_version": 1,
            "scene_id": "m3.cli",
            "scene_revision": "r1",
            "simulation": {"fixed_step_ms": 16, "max_speed": 8},
            "entities": [entity],
        },
        "assets": [
            {
                "asset_id": "mesh",
                "revision": "r1",
                "type": "mesh",
                "media_type": "model/gltf-binary",
                "dependencies": [],
                "source": {"kind": "godot_whitelist_import", "importer_version": "1"},
                "path": "valid.glb",
            }
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--next-asset", type=Path, required=True)
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    args.next_asset = args.next_asset.resolve()
    args.fixtures = args.fixtures.resolve()
    args.report = args.report.resolve()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=args.report.parent) as temporary:
        root = Path(temporary)
        request_path = root / "request.json"
        request_path.write_text(json.dumps(request(args.fixtures)), encoding="utf-8")
        outputs = []
        for name in ("a", "b"):
            (root / name).mkdir()
            package = root / name / "scene.enpak"
            run(
                [
                    args.next_asset,
                    "compile",
                    "--request",
                    request_path,
                    "--source-root",
                    args.fixtures,
                    "--output",
                    package,
                ],
                root / name,
            )
            validated = run([args.next_asset, "validate", "--package", package], root / name)
            inspected = run([args.next_asset, "inspect", "--package", package], root / name)
            outputs.append(json.loads(inspected.stdout))
            assert json.loads(validated.stdout)["valid"] is True
        assert outputs[0]["package_digest"] == outputs[1]["package_digest"]
        assert (root / "a/scene.enpak/AssetManifest.json").read_bytes() == (
            root / "b/scene.enpak/AssetManifest.json"
        ).read_bytes()
        run(
            [
                args.next_asset,
                "compile",
                "--request",
                request_path,
                "--source-root",
                args.fixtures,
                "--output",
                root / "a/scene.enpak",
            ],
            root / "a",
        )
        bad = request(args.fixtures)
        bad["assets"][0]["path"] = "../valid.glb"
        bad_path = root / "bad.json"
        bad_path.write_text(json.dumps(bad), encoding="utf-8")
        run(
            [
                args.next_asset,
                "compile",
                "--request",
                bad_path,
                "--source-root",
                args.fixtures,
                "--output",
                root / "a/bad.enpak",
            ],
            root / "a",
            passed=False,
        )
        result = {
            "passed": True,
            "package_digest": outputs[0]["package_digest"],
            "deterministic": True,
            "no_clobber_reconciled": True,
            "path_escape_rejected": True,
        }
        args.report.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print("ENGINE_NEXT_M3_ASSETS deterministic=1 no_clobber=1 path_escape_rejected=1 status=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
