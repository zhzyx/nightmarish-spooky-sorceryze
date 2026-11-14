"""Run the real Godot legacy adapter against neutral packages and whitelist scenes."""

import argparse
import json
import subprocess
import tempfile
from pathlib import Path


def invoke(command, *, expect_success=True):
    result = subprocess.run([str(value) for value in command], capture_output=True, text=True, timeout=30)
    text = result.stdout + result.stderr
    if expect_success:
        assert result.returncode == 0 and "SCRIPT ERROR" not in text and "ERROR:" not in text, text
    else:
        assert result.returncode != 0, text
    return result


def legacy(args, root, action, options, *, expect_success=True):
    command = [args.godot, "--headless", "--script", args.adapter, "--", "--action", action]
    for name, value in options.items():
        command.extend(["--" + name, value])
    result = invoke(command, expect_success=expect_success)
    payload = None
    for line in result.stdout.splitlines():
        if line.startswith("{"):
            payload = json.loads(line)
    assert payload is not None and payload.get("ok") == expect_success, result.stdout + result.stderr
    return payload


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--next-asset", type=Path, required=True)
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--fixtures", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    for name in ("godot", "next_asset", "adapter", "fixtures", "report"):
        setattr(args, name, getattr(args, name).resolve())
    args.report.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=args.report.parent) as temporary:
        root = Path(temporary)
        request = root / "request.json"
        stage = root / "stage"
        imported = legacy(
            args,
            root,
            "import",
            {
                "input": args.fixtures / "Whitelist.tscn",
                "source-root": args.fixtures,
                "request-output": request,
                "stage-root": stage,
            },
        )
        assert imported["entity_count"] == 2 and imported["asset_count"] == 1
        package = root / "scene.enpak"
        compiled = invoke([
            args.next_asset,
            "compile",
            "--request",
            request,
            "--source-root",
            stage,
            "--output",
            package,
        ])
        package_info = json.loads(compiled.stdout)
        verify_options = {
            "package": package,
            "next-asset": args.next_asset,
            "work-dir": root / "verify",
        }
        verified = legacy(args, root, "verify", verify_options)
        assert verified["package_digest"] == package_info["package_digest"] and verified["entity_count"] == 2
        published = root / "published.tscn"
        publish_options = dict(verify_options, **{"work-dir": root / "publish", "output": published})
        legacy(args, root, "publish", publish_options)
        assert published.is_file()
        legacy(args, root, "publish", publish_options, expect_success=False)
        legacy(
            args, root, "verify", dict(verify_options, **{"work-dir": root / "verify-published", "scene": published})
        )
        original_scene = published.read_text(encoding="utf-8")
        broken_scenes = {
            "parent": original_scene.replace('parent="Root"', 'parent="."', 1),
            "simulation": original_scene.replace('"fixed_step_ms": 20.0', '"fixed_step_ms": 16.0', 1),
            "mesh": original_scene.replace('mesh = SubResource("ArrayMesh', "mesh = null # ArrayMesh", 1),
        }
        for name, content in broken_scenes.items():
            assert content != original_scene
            broken = root / f"broken-{name}.tscn"
            broken.write_text(content, encoding="utf-8")
            legacy(
                args,
                root,
                "verify",
                dict(verify_options, **{"work-dir": root / f"verify-{name}", "scene": broken}),
                expect_success=False,
            )
        legacy(
            args,
            root,
            "import",
            {
                "input": args.fixtures / "Whitelist.tscn",
                "source-root": args.fixtures,
                "request-output": request,
                "stage-root": stage,
            },
            expect_success=False,
        )

        rejected = {}
        for fixture in (
            "ScriptRejected.tscn",
            "UnsupportedNode.tscn",
            "Inherited.tscn",
            "Uid.tscn",
            "External.tscn",
            "Missing.tscn",
            "UnsupportedProperty.tscn",
            "UnknownAttribute.tscn",
            "NodeUnknownAttribute.tscn",
        ):
            output = root / (fixture + ".json")
            legacy(
                args,
                root,
                "import",
                {
                    "input": args.fixtures / fixture,
                    "source-root": args.fixtures,
                    "request-output": output,
                    "stage-root": root / (fixture + "-stage"),
                },
                expect_success=False,
            )
            assert not output.exists()
            rejected[fixture] = True
        version = invoke([args.godot, "--headless", "--version"]).stdout.strip()
        report = {
            "passed": True,
            "godot_version": version,
            "package_digest": package_info["package_digest"],
            "scene_revision": "r3",
            "entities": 2,
            "mesh_assets": 1,
            "publish_no_clobber": True,
            "import_no_clobber": True,
            "published_scene_semantics": True,
            "semantic_rejections": list(broken_scenes),
            "rejected": rejected,
        }
        args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print("ENGINE_NEXT_M3_LEGACY import=1 verify=1 publish=1 semantic_verify=1 rejected=9 status=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
