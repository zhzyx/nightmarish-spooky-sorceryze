"""Bridge regression tests: immutable sources, no-clobber and configuration isolation."""

import argparse
import copy
import hashlib
import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from editor_host import compile_graph, dispatch


def fixtures(folder):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", 2, 2, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\0\xff\0\0\0\xff\0\0\0\0\xff\xff\xff\xff"))
        + chunk(b"IEND", b"")
    )
    (folder / "sample.png").write_bytes(png)
    import base64

    vertices = struct.pack("<9f", -1, 0, 0, 1, 0, 0, 0, 1, 0)
    gltf = {
        "asset": {"version": "2.0"},
        "scene": 0,
        "scenes": [{"nodes": [0]}],
        "nodes": [{"mesh": 0}],
        "meshes": [{"primitives": [{"attributes": {"POSITION": 0}}]}],
        "buffers": [
            {
                "byteLength": len(vertices),
                "uri": "data:application/octet-stream;base64," + base64.b64encode(vertices).decode(),
            }
        ],
        "bufferViews": [{"buffer": 0, "byteLength": len(vertices)}],
        "accessors": [
            {"bufferView": 0, "componentType": 5126, "count": 3, "type": "VEC3", "min": [-1, 0, 0], "max": [1, 1, 0]}
        ],
    }
    (folder / "sample.gltf").write_text(json.dumps(gltf))
    gltf["buffers"] = [{"byteLength": len(vertices)}]
    chunk = json.dumps(gltf).encode()
    chunk += b" " * ((-len(chunk)) % 4)
    (folder / "sample.glb").write_bytes(
        struct.pack("<5I", 0x46546C67, 2, 28 + len(chunk) + len(vertices), len(chunk), 0x4E4F534A)
        + chunk
        + struct.pack("<2I", len(vertices), 0x004E4942)
        + vertices
    )


def model(path, fail=False):
    return {
        "format": 1,
        "edges": [],
        "nodes": [
            {
                "id": "first",
                "source": str(path),
                "image_context": "",
                "text": "reference",
                "parameters": {"fail": fail, "delay": 0},
                "x": 10,
                "y": 20,
            }
        ],
    }


def reconcile_factory():
    """Fault-injection provider for the actual Godot replay; not a production provider."""
    import os

    from editor_demo import Demo, factory

    registry, _ = factory()

    class Unknown(Demo):
        def record(self, value):
            with open(os.environ["AINATIVE_LOOKUP_MARKER"], "a") as stream:
                stream.write(value + "\n")

        def submit(self, request, manifest, idempotency_key):
            self.record("submit")
            raise RuntimeError("simulated lost receipt")

        def lookup(self, key):
            self.record("lookup")
            return None

    return registry, {"local-copy": Unknown()}


def integer_transport_factory():
    """Production node schemas, without constructing or calling a model backend."""
    from comfy_provider import KINDS, register
    from extensions import NodeRegistry

    registry = NodeRegistry()
    register(registry)

    class DescriptionOnly:
        def describe(self):
            return dict(
                id="comfy",
                version="1",
                model="transport-test",
                model_version="1",
                capabilities=list(KINDS),
                context_types=["text", "image"],
                available=True,
            )

    return registry, {"comfy": DescriptionOnly()}


class BridgeTests(unittest.TestCase):
    def test_target_runs_only_dependency_closure_and_ignores_unrelated_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures(root)
            args = argparse.Namespace(db=str(root / "db"), factory="editor_demo:factory", command="create")
            graph = model(root / "sample.png")
            graph["nodes"].extend([
                dict(id="second", parameters={"delay": 0}, text="changed downstream prompt"),
                dict(id="unrelated", source=str(root / "missing.png"), type="not-a-real-node", parameters={}),
                dict(id="downstream", parameters={}),
            ])
            graph["edges"] = [dict(**{"from": "first", "to": "second"}), dict(**{"from": "second", "to": "downstream"})]
            original = copy.deepcopy(graph)
            run = dispatch(args, {"model": graph, "target": "second"})["run_id"]
            args.command = "status"
            self.assertEqual(set(dispatch(args, {"run": run})["nodes"]), {"first", "second"})
            args.command = "step"
            self.assertEqual(dispatch(args, {"run": run})["nodes"]["first"]["state"], "succeeded")
            self.assertEqual(dispatch(args, {"run": run})["state"], "succeeded")
            args.command = "preview"
            preview = dispatch(args, {"run": run, "node": "second"})
            self.assertEqual(Path(preview["path"]).read_bytes(), (root / "sample.png").read_bytes())
            self.assertEqual(graph, original)
            args.command = "create"
            root_run = dispatch(args, {"model": graph, "target": "first"})["run_id"]
            args.command = "status"
            self.assertEqual(set(dispatch(args, {"run": root_run})["nodes"]), {"first"})

    def test_target_invalid_identity_missing_dependency_and_cycle_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures(root)
            args = argparse.Namespace(db=str(root / "db"), factory="editor_demo:factory", command="create")
            graph = model(root / "sample.png")
            with self.assertRaisesRegex(ValueError, "unknown target"):
                dispatch(args, {"model": graph, "target": "missing"})
            duplicate = copy.deepcopy(graph)
            duplicate["nodes"].append(copy.deepcopy(graph["nodes"][0]))
            with self.assertRaisesRegex(ValueError, "duplicate node"):
                dispatch(args, {"model": duplicate, "target": "first"})
            missing = copy.deepcopy(graph)
            missing["edges"] = [{"from": "missing", "to": "first"}]
            with self.assertRaisesRegex(ValueError, "missing dependency"):
                dispatch(args, {"model": missing, "target": "first"})
            cycle = copy.deepcopy(graph)
            cycle["edges"] = [{"from": "first", "to": "first"}]
            with self.assertRaisesRegex(ValueError, "cycle"):
                dispatch(args, {"model": cycle, "target": "first"})

    def test_image_suffix_follows_immutable_bytes_in_sources_context_and_saved_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures(root)
            png = (root / "sample.png").read_bytes()
            jpg = b"\xff\xd8\xff\xe0" + b"JPEG header detection" + b"\xff\xd9"
            (root / "export.png").write_bytes(jpg)
            (root / "reference.jpg").write_bytes(png)
            workflow = model(root / "export.png")
            node = workflow["nodes"][0]
            node["image_context"] = str(root / "reference.jpg")
            _, assets = compile_graph(workflow)
            for artifact, (field, data, extension) in zip(
                assets["artifacts"], (("source", jpg, ".jpg"), ("image_context", png, ".png"))
            ):
                self.assertEqual(artifact["payload"]["extension"], extension)
                self.assertEqual(artifact["revision"], hashlib.sha256(data).hexdigest())
                snapshot = dict(artifact["payload"], extension=Path(node[field]).suffix)
                node[field] = ""
                node[field + "_snapshot"] = snapshot
            self.assertEqual(compile_graph(workflow)[1], assets)

    def test_preview_preserves_snapshot_and_rejects_tampered_materialization(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures(root)
            source = root / "sample.png"
            original = source.read_bytes()
            args = argparse.Namespace(db=str(root / "db"), factory="editor_demo:factory", command="create")
            run = dispatch(args, {"model": model(source), "target": "first"})["run_id"]
            source.write_bytes(b"changed after create")
            args.command = "step"
            dispatch(args, {"run": run})
            args.command = "preview"
            preview = dispatch(args, {"run": run, "node": "first"})
            self.assertEqual(Path(preview["path"]).read_bytes(), original)
            Path(preview["path"]).write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "preview collision"):
                dispatch(args, {"run": run, "node": "first"})

    def test_completed_node_preview_before_full_run_and_after_other_branch_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures(root)
            args = argparse.Namespace(db=str(root / "db"), factory="editor_demo:factory", command="create")
            graph = model(root / "sample.png")
            other = copy.deepcopy(graph["nodes"][0])
            other.update(id="other", parameters={"fail": True})
            graph["nodes"].append(other)
            run = dispatch(args, {"model": graph})["run_id"]
            request = {"run": run, "node": "first"}
            args.command = "preview"
            with self.assertRaisesRegex(ValueError, "successful result"):
                dispatch(args, request)
            args.command = "step"
            self.assertEqual(dispatch(args, {"run": run})["state"], "running")
            args.command = "preview"
            preview = dispatch(args, request)
            args.command = "step"
            self.assertEqual(dispatch(args, {"run": run})["state"], "failed")
            args.command = "preview"
            self.assertEqual(dispatch(args, request), preview)
            with self.assertRaisesRegex(ValueError, "successful result"):
                dispatch(args, {"run": run, "node": "other"})
            args.command = "publish"
            with self.assertRaisesRegex(ValueError, "not publishable"):
                dispatch(args, {**request, "confirmation": preview["token"]})
            args.command = "cancel"
            dispatch(args, {"run": run})
            args.command = "preview"
            with self.assertRaisesRegex(ValueError, "cancelled"):
                dispatch(args, request)

    def test_godot_float_integer_serialization_at_create_boundary(self):
        import subprocess
        import sys

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Godot JSON.parse_string -> JSON.stringify represents seed as 42.0.
            request = json.loads(
                '{"model":{"nodes":[{"id":"g","type":"text_to_image","provider":"comfy","parameters":{"prompt":"owl","seed":42.0,"width":512.0,"denoise":0.5}}],"edges":[]}}'
            )
            spec = root / "spec.json"
            result = root / "result.json"
            spec.write_text(json.dumps(request), encoding="utf-8")
            subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).with_name("editor_host.py")),
                    "create",
                    "--db",
                    str(root / "db"),
                    "--factory",
                    "test_editor_host:integer_transport_factory",
                    "--spec",
                    str(spec),
                    "--result",
                    str(result),
                ],
                check=True,
            )
            run = json.loads(result.read_text(encoding="utf-8"))["result"]["run_id"]
            args = argparse.Namespace(db=str(root / "db"), command="status")
            params = dispatch(args, {"run": run})["nodes"]["g"]["request"]["parameters"]
            self.assertEqual(params["seed"], 42)
            self.assertIs(type(params["seed"]), int)
            self.assertIs(type(params["width"]), int)
            self.assertEqual(params["denoise"], 0.5)
            self.assertIs(type(params["denoise"]), float)
            self.assertIs(type(request["model"]["nodes"][0]["parameters"]["seed"]), float)

    def test_editor_integer_rejects_fraction_bool_nonfinite_and_unsafe(self):
        with tempfile.TemporaryDirectory() as tmp:
            args = argparse.Namespace(
                db=str(Path(tmp) / "db"), factory="test_editor_host:integer_transport_factory", command="create"
            )
            for seed in (
                42.5,
                True,
                False,
                float("nan"),
                float("inf"),
                float("-inf"),
                float(2**53),
                2**53,
                -(2**53),
                "42",
            ):
                with self.subTest(seed=seed):
                    request = {
                        "model": {
                            "nodes": [
                                dict(
                                    id="g",
                                    type="text_to_image",
                                    provider="comfy",
                                    parameters={"prompt": "owl", "seed": seed},
                                )
                            ],
                            "edges": [],
                        }
                    }
                    with self.assertRaises(ValueError):
                        dispatch(args, request)
            for seed in (float(2**53 - 1), float(-(2**53 - 1)), 42):
                with self.subTest(valid_seed=seed):
                    request = {
                        "model": {
                            "nodes": [
                                dict(
                                    id="g",
                                    type="text_to_image",
                                    provider="comfy",
                                    parameters={"prompt": "owl", "seed": seed, "denoise": 1.0},
                                )
                            ],
                            "edges": [],
                        }
                    }
                    run = dispatch(args, request)["run_id"]
                    status_args = argparse.Namespace(db=args.db, command="status")
                    params = dispatch(status_args, {"run": run})["nodes"]["g"]["request"]["parameters"]
                    self.assertEqual(params["seed"], int(seed))
                    self.assertIs(type(params["seed"]), int)
                    self.assertIs(type(params["denoise"]), float)

    def test_bound_publish_and_no_clobber(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures(root)
            source = root / "sample.png"
            before = source.read_bytes()
            args = argparse.Namespace(db=str(root / "db"), factory="editor_demo:factory", command="create")
            run = dispatch(args, {"model": model(source)})["run_id"]
            req = {"run": run, "node": "first"}
            args.command = "step"
            self.assertEqual(dispatch(args, req)["state"], "succeeded")
            args.command = "preview"
            preview = dispatch(args, req)
            stage = root / "stage.tres"
            stage.write_text('[gd_resource type="Resource" format=3]\n[resource]\n')
            args.command = "publish"
            request = {
                **req,
                "confirmation": preview["token"],
                "staged": str(stage),
                "staged_sha256": hashlib.sha256(stage.read_bytes()).hexdigest(),
                "target": str(root / "published.tres"),
            }
            dispatch(args, request)
            with self.assertRaises(FileExistsError):
                dispatch(args, request)
            with self.assertRaises(ValueError):
                dispatch(args, {**request, "confirmation": "stale"})
            stage.write_text("changed after confirmation")
            with self.assertRaises(ValueError):
                dispatch(args, {**request, "target": str(root / "tampered.tres")})
            self.assertFalse((root / "tampered.tres").exists())
            self.assertEqual(source.read_bytes(), before)
            args.command = "create"
            failed = dispatch(args, {"model": model(source, True)})["run_id"]
            args.command = "step"
            self.assertEqual(dispatch(args, {"run": failed})["state"], "failed")
            args.command = "retry"
            state = dispatch(args, {"run": failed, "node": "first"})
            self.assertEqual(state["nodes"]["first"]["attempt"], 1)
            args.command = "cancel"
            self.assertEqual(dispatch(args, {"run": failed})["state"], "cancelled")
            self.assertEqual(source.read_bytes(), before)

    def test_config_and_external_gltf_rejected(self):
        with self.assertRaises(ValueError):
            compile_graph({"factory": "evil", "nodes": [], "edges": []})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.gltf"
            path.write_text('{"buffers":[{"uri":"other.bin"}]}')
            with self.assertRaises(ValueError):
                compile_graph(model(path))
            chunk = path.read_bytes()
            chunk += b" " * ((-len(chunk)) % 4)
            glb = Path(tmp) / "bad.glb"
            glb.write_bytes(struct.pack("<5I", 0x46546C67, 2, 20 + len(chunk), len(chunk), 0x4E4F534A) + chunk)
            with self.assertRaises(ValueError):
                compile_graph(model(glb))


if __name__ == "__main__":
    unittest.main()
