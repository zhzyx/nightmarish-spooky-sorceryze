"""Actual Executor/host integration with a deterministic, local fake Provider.

No image model, upload, network service, or user asset is used in this test.
"""

import argparse
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from editor_demo import factory
from editor_host import compile_graph, dispatch
from executor import snapshot_file
from multi_image_provider import MultiImageProvider, register_images
from test_editor_host import fixtures
from test_multi_image_provider import FakeImageProvider


class PersistentFake(FakeImageProvider):
    def __init__(self, state):
        super().__init__("comfy")
        self.state = Path(state)
        if self.state.is_file():
            stored = json.loads(self.state.read_text(encoding="utf-8"))
            self.jobs = stored["jobs"]
            self.requests = stored["requests"]
            self.submissions = stored["submissions"]
            self.polls = stored["polls"]

    def save(self):
        body = dict(jobs=self.jobs, requests=self.requests, submissions=self.submissions, polls=self.polls)
        temporary = self.state.with_suffix(".tmp")
        temporary.write_text(json.dumps(body), encoding="utf-8")
        os.replace(temporary, self.state)

    def read(self, key):
        result = super().read(key)
        self.save()
        return result

    def submit(self, request, manifest, key):
        result = super().submit(request, manifest, key)
        self.save()
        return result

    def poll(self, key):
        result = super().poll(key)
        self.save()
        return result

    def cancel(self, key):
        result = super().cancel(key)
        self.save()
        return result


def persistent_factory():
    registry, _ = factory()
    register_images(registry)
    state = Path(os.environ["AINATIVE_MULTI_IMAGE_FIXTURE_STATE"])
    provider = MultiImageProvider(PersistentFake(state / "inner.json"), state / "adapter")
    return registry, {"comfy": provider}


def board(sources, directory, config):
    from test_multi_image_provider import asset

    result = asset("board", "|".join(source["asset"]["id"] for source in sources))
    result["payload"]["provenance"] = dict(
        adaptation="labelled_multi_source_reference_board",
        sources=[dict(source_sha256=source["asset"]["revision"], label=source["label"]) for source in sources],
        board_sha256=result["revision"],
    )
    return result


class MultiImageHostTests(unittest.TestCase):
    def test_compile_executor_selection_publication_and_restore(self):
        with tempfile.TemporaryDirectory(prefix="multi-image-host-") as temporary:
            root = Path(temporary)
            fixtures(root)
            from test_kimi_work_image_provider import png

            second = root / "second.png"
            second.write_bytes(png(64, 64))
            paths = [root / "sample.png", second]
            snapshots = [dict(snapshot_file(path), extension=".png") for path in paths]
            node = dict(
                id="gen",
                type="image_to_image",
                version="2",
                provider="comfy",
                source_paths=[str(path) for path in paths],
                source_snapshots=copy.deepcopy(snapshots),
                image_context_paths=[],
                text="",
                parameters={"prompt": "same sculpture", "output_count": 2, "output_labels": ["front", "three-quarter"]},
            )
            graph, manifest = compile_graph({"nodes": [node], "edges": []})
            self.assertEqual([item["id"] for item in manifest["artifacts"]], ["gen-source-0", "gen-source-1"])
            self.assertEqual(graph[0]["request"]["version"], "2")
            self.assertEqual(graph[0]["request"]["inputs"]["source"]["id"], "gen-source-0")
            node.update(source_paths=["", ""], source_snapshots=snapshots)
            self.assertEqual(compile_graph({"nodes": [node], "edges": []})[1], manifest)
            node.update(source=str(paths[0]), source_paths=[], source_snapshots=[])
            self.assertEqual(len(compile_graph({"nodes": [node], "edges": []})[1]["artifacts"]), 1)

            # The second graph port carries every member; the legacy result port
            # still carries only the primary image for Mesh compatibility.
            upstream = dict(node, id="upstream", type="text_to_image", source="", source_paths=[], source_snapshots=[])
            downstream = dict(node, id="downstream", source="", source_paths=[], source_snapshots=[])
            graph, _ = compile_graph({
                "nodes": [upstream, downstream],
                "edges": [{"from": "upstream", "to": "downstream", "input": "source", "output": "image_set"}],
            })
            self.assertEqual(graph[1]["links"]["source"], {"node": "upstream", "port": "image_set"})

            run_node = dict(node, source="", source_paths=["", ""], source_snapshots=snapshots)
            args = argparse.Namespace(
                db=str(root / "runs.sqlite"), factory="test_multi_image_host:persistent_factory", command="create"
            )
            with (
                patch.dict(os.environ, {"AINATIVE_MULTI_IMAGE_FIXTURE_STATE": str(root)}),
                patch("multi_image_provider.make_reference_board", side_effect=board) as make_board,
            ):
                run = dispatch(args, {"model": {"nodes": [run_node], "edges": []}})["run_id"]
                args.command = "step"
                for _ in range(12):
                    state = dispatch(args, {"run": run})
                    if state["state"] in ("succeeded", "failed"):
                        break
                self.assertEqual(state["state"], "succeeded", state["nodes"]["gen"])
                self.assertEqual(make_board.call_count, 1)
                args.command = "preview"
                request = {"run": run, "node": "gen"}
                preview = dispatch(args, request)
                self.assertEqual([item["label"] for item in preview["images"]], ["front", "three-quarter"])
                self.assertEqual(preview["artifact"], preview["images"][0]["artifact"])
                self.assertNotEqual(preview["images"][0]["artifact"], preview["images"][1]["artifact"])
                with self.assertRaisesRegex(ValueError, "not a set member"):
                    dispatch(args, dict(request, artifact={"id": "not-a-member", "revision": "0" * 64}))
                selected = preview["images"][1]
                member = dispatch(args, dict(request, artifact=selected["artifact"]))
                self.assertEqual(member["path"], selected["path"])
                self.assertNotEqual(member["token"], preview["token"])
                stage = root / "stage.tres"
                stage.write_text('[gd_resource type="ImageTexture" format=3]\n[resource]\n', encoding="utf-8")
                import hashlib

                args.command = "publish"
                published = dispatch(
                    args,
                    {
                        **request,
                        "artifact": selected["artifact"],
                        "confirmation": member["token"],
                        "staged": str(stage),
                        "staged_sha256": hashlib.sha256(stage.read_bytes()).hexdigest(),
                        "target": str(root / "selected.tres"),
                    },
                )
                self.assertEqual(Path(published["path"]).read_bytes(), stage.read_bytes())
                before = json.loads((root / "inner.json").read_text(encoding="utf-8"))
                self.assertEqual(before["submissions"], 2)
                args.command = "step"
                restored = dispatch(args, {"run": run})
                self.assertEqual(restored["state"], "succeeded")
                after = json.loads((root / "inner.json").read_text(encoding="utf-8"))
                self.assertEqual(after["submissions"], before["submissions"])
                args.command = "preview"
                self.assertEqual(dispatch(args, dict(request, artifact=selected["artifact"]))["token"], member["token"])
                parent = MultiImageProvider(PersistentFake(root / "inner.json"), root / "adapter")
                children = parent.read(state["nodes"]["gen"]["job"]["job_id"])["children"]
                self.assertEqual(len(children), 2)
                self.assertNotEqual(children[0]["key"], children[1]["key"])
                self.assertEqual(
                    [
                        item["source_sha256"]
                        for item in parent.result_manifest(state["nodes"]["gen"]["job"]["job_id"])["artifacts"][-1][
                            "payload"
                        ]["provenance"]["reference_board"]["sources"]
                    ],
                    [snapshot["content_sha256"] for snapshot in snapshots],
                )


if __name__ == "__main__":
    unittest.main()
