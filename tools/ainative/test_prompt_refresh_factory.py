"""Prompt-sensitive local image provider for Godot full-workflow regression tests."""

import base64
import copy
import hashlib
import struct
import zlib

from extensions import NodeRegistry
from multi_image_provider import register_images


def png_for(prompt):
    digest = hashlib.sha256(prompt.encode("utf-8")).digest()
    row = b"\0" + bytes(digest[:3]) * 8
    data = row * 8

    def chunk(kind, body):
        return struct.pack(">I", len(body)) + kind + body + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF)

    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 8, 8, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(data)) + chunk(b"IEND", b"")


class PromptImageProvider:
    def __init__(self):
        self.jobs = {}
        self.manifests = {}

    def describe(self):
        return dict(
            id="prompt_refresh_fixture",
            version="1",
            model="Prompt-sensitive local fixture",
            model_version="1",
            capabilities=["generate_image"],
            context_types=["text", "image", "image_set"],
            available=True,
        )

    def submit(self, request, manifest, idempotency_key):
        prompt = request["parameters"]["prompt"]
        data = png_for(prompt)
        sha = hashlib.sha256(data).hexdigest()
        image = dict(
            id="prompt-image-" + sha,
            revision=sha,
            type="image",
            payload=dict(
                content_base64=base64.b64encode(data).decode("ascii"),
                content_sha256=sha,
                extension=".png",
                bytes=len(data),
                provenance={"prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest()},
            ),
        )
        reference = {"id": image["id"], "revision": sha}
        body = dict(schema_version=1, items=[dict(artifact=reference, label="main", index=0)], count=1)
        collection = dict(
            id="prompt-image-set-" + idempotency_key,
            revision=hashlib.sha256(str(body).encode()).hexdigest(),
            type="image_set",
            payload=body,
            dependencies=[reference],
        )
        outputs = {"image_set": {"id": collection["id"], "revision": collection["revision"]}}
        job = dict(job_id=idempotency_key, state="succeeded", outputs=outputs, error=None)
        self.jobs[idempotency_key] = job
        self.manifests[idempotency_key] = dict(
            schema_version=1,
            artifacts=copy.deepcopy(manifest["artifacts"]) + [image, collection],
        )
        return copy.deepcopy(job)

    def poll(self, key):
        return copy.deepcopy(self.jobs[key])

    def result_manifest(self, key):
        return copy.deepcopy(self.manifests[key])

    def cancel(self, key):
        return None


def factory():
    registry = NodeRegistry()
    register_images(registry)
    return registry, {"prompt_fixture": PromptImageProvider()}
