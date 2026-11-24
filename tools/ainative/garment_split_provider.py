"""Durable provider for wearable garment reconstruction and diagnostic surface splits.

Automatic static-input runs use one remote vision segmentation request and local
source-bound geometry reconstruction. Explicit developer selections remain local
surface extraction. Every artifact carries exact bytes and provenance.
"""

import base64
import copy
import hashlib
import json
import re
import sqlite3
from pathlib import Path

from extensions import canonical, require, validate_invocation
from garment_split import split

KIND = "garment_split"
PROVIDER_ID = "garment-split"


def register(registry):
    registry.register(
        dict(
            id=KIND,
            version="1",
            inputs={"source": {"types": ["mesh"], "required": True}},
            outputs={"result": {"types": ["mesh"], "required": True}},
            context_types=[],
            parameters={
                "properties": {
                    "items": {"type": "array"},
                    "unresolved_items": {"type": "array"},
                    "inventory_sha256": {"type": "string"},
                }
            },
            capabilities=[KIND],
        )
    )


class GarmentSplitProvider:
    def __init__(self, config):
        allowed = {"storage", "planner", "review_godot_path", "review_script_path"}
        if not isinstance(config, dict) or set(config) - allowed:
            raise ValueError("garment_split_config_invalid")
        storage = Path(config["storage"])
        if not isinstance(config["storage"], str) or not config["storage"].strip():
            raise ValueError("garment_split_config_invalid")
        self.config = copy.deepcopy(config)
        self.storage = storage.resolve()
        self.storage.mkdir(parents=True, exist_ok=True)
        self.database = self.storage / "jobs.sqlite"
        with sqlite3.connect(self.database) as db:
            db.execute("CREATE TABLE IF NOT EXISTS jobs(key TEXT PRIMARY KEY, body TEXT NOT NULL)")

    def fingerprint(self):
        digest = hashlib.sha256()
        for name in (
            "garment_split_provider.py",
            "garment_split.py",
            "garment_inventory.py",
            "garment_auto.py",
            "garment_complete.py",
            "geometry_repair.py",
            "cloth_prepare.py",
        ):
            path = Path(__file__).with_name(name)
            digest.update(name.encode("utf-8") + b"\0" + path.read_bytes() + b"\0")
        identity = {
            key: self.config.get(key) for key in ("planner", "review_godot_path", "review_script_path")
        }
        digest.update(canonical(identity).encode("utf-8"))
        script = Path(self.config.get("review_script_path", ""))
        if script.is_file():
            digest.update(script.read_bytes())
        return digest.hexdigest()

    def describe(self):
        return dict(
            id=PROVIDER_ID,
            version="1",
            model="SOURCE-BOUND WEARABLE GARMENT RECONSTRUCTION",
            model_version=self.fingerprint(),
            available=True,
            capabilities=[KIND],
            context_types=[],
        )

    def read(self, key):
        require(isinstance(key, str) and re.fullmatch(r"[a-f0-9]{64}", key), "invalid job key")
        with sqlite3.connect(self.database) as db:
            row = db.execute("SELECT body FROM jobs WHERE key=?", (key,)).fetchone()
        require(row is not None, "unknown local job")
        return json.loads(row[0])

    def _store(self, key, record):
        with sqlite3.connect(self.database) as db:
            db.execute("UPDATE jobs SET body=? WHERE key=?", (canonical(record), key))
        return record

    @staticmethod
    def snapshot(key, state, outputs=None, error=None):
        return dict(job_id=key, state=state, outputs=outputs or {}, error=error)

    def _source(self, request, manifest):
        reference = request["inputs"]["source"]
        matches = [
            artifact
            for artifact in manifest["artifacts"]
            if artifact["id"] == reference["id"] and artifact["revision"] == reference["revision"]
        ]
        require(len(matches) == 1 and matches[0]["type"] == "mesh", "garment_split_source_invalid")
        payload = matches[0]["payload"]
        require(payload.get("extension", "").lower() == ".glb", "garment_split_source_invalid")
        data = base64.b64decode(payload["content_base64"], validate=True)
        require(
            hashlib.sha256(data).hexdigest() == payload["content_sha256"] == reference["revision"],
            "garment_split_source_invalid",
        )
        return matches[0], data

    @staticmethod
    def _asset(asset_id, data, provenance):
        sha = hashlib.sha256(data).hexdigest()
        return dict(
            id=asset_id,
            revision=sha,
            type="mesh",
            payload=dict(
                content_base64=base64.b64encode(data).decode("ascii"),
                content_sha256=sha,
                extension=".glb",
                bytes=len(data),
                provenance=provenance,
            ),
        )

    def _run(self, key, request, manifest):
        source_asset, source_data = self._source(request, manifest)
        parameters = copy.deepcopy(request["parameters"])
        job_root = self.storage / key
        job_root.mkdir(exist_ok=False)
        source_path = job_root / "source.glb"
        source_path.write_bytes(source_data)
        items = parameters.get("items", [])
        require(isinstance(items, list), "garment_split_spec_invalid")
        automatic_receipt = {}
        output = job_root / "output"
        if not items:
            from garment_complete import complete

            record = complete(
                source_path,
                output,
                job_root / "completion",
                self.config.get("review_godot_path", ""),
                self.config.get("review_script_path", ""),
                planner=self.config.get("planner"),
            )
            automatic_receipt = copy.deepcopy(record["automatic_recognition"])
        else:
            # Developer-supplied geometry selections remain surface extraction;
            # they are never promoted to wearable garments by the provider.
            spec = dict(
                schema_version=1,
                source=str(source_path),
                source_sha256=hashlib.sha256(source_data).hexdigest(),
                output=str(output),
                items=parameters["items"],
            )
            for field in ("unresolved_items", "inventory_sha256"):
                if field in parameters:
                    spec[field] = parameters[field]
            record = split(spec)
        collection_path = output / record["collection"]["path"]
        collection_data = collection_path.read_bytes()
        require(
            hashlib.sha256(collection_data).hexdigest() == record["collection"]["sha256"],
            "garment_split_output_invalid",
        )
        final_id = "garment-split-" + key
        common = dict(
            provider=PROVIDER_ID,
            operation=record["operation"],
            source_sha256=record["source_sha256"],
            source_artifact={key: source_asset[key] for key in ("id", "revision")},
            split_manifest_revision=record["manifest_revision"],
            capability_limited=record["capability_limited"],
            unresolved=copy.deepcopy(record["unresolved"]),
            original_model_not_overwritten=True,
            rigged=record["rigged"],
            skeleton_preserved=record["skeleton_preserved"],
            skin_weights_preserved=record["skin_weights_preserved"],
            inverse_bind_matrices_preserved=record["inverse_bind_matrices_preserved"],
            unreferenced_source_vertices_retained=record["unreferenced_source_vertices_retained"],
            blender_used=False,
            cloud_used=bool(automatic_receipt),
            automatic_recognition=copy.deepcopy(automatic_receipt) if automatic_receipt else None,
            visual_review_passed=False,
            fit_validated=False,
            animation_validated=False,
            cloth_ready=False,
        )
        primary_provenance = dict(
            common,
            artifact_role="garment_collection",
            garment_count=len(record["items"]),
            collection={key: copy.deepcopy(value) for key, value in record["collection"].items() if key != "path"},
            items=[
                dict(
                    id=item["id"],
                    label=item["label"],
                    state=item["state"],
                    review_state=item["review_state"],
                    coverage_state=item.get("coverage_state", "unknown"),
                    closed_position_welded=item.get("closed_position_welded", False),
                )
                for item in record["items"]
            ],
        )
        primary = self._asset(final_id, collection_data, primary_provenance)
        garments = []
        for index, item in enumerate(record["items"], 1):
            data = (output / item["path"]).read_bytes()
            require(hashlib.sha256(data).hexdigest() == item["sha256"], "garment_split_output_invalid")
            provenance = dict(
                common,
                artifact_role="garment",
                iteration_of=final_id,
                generation_iteration=index,
                generation_iteration_count=len(record["items"]),
                garment_id=item["id"],
                garment_label=item["label"],
                category=item["category"],
                slot=item["slot"],
                behavior=item["behavior"],
                review_state=item["review_state"],
                garment_state=item["state"],
                coverage_state=item.get("coverage_state", "unknown"),
                closed_position_welded=item.get("closed_position_welded", False),
                source_triangle_count=item.get("source_triangles"),
                thickness_m=item.get("thickness_m"),
                cloth_state=item.get("cloth", {}).get("state"),
                cloth_ready=False,
                triangles=item["triangles"],
                vertices=item["vertices"],
            )
            garments.append(self._asset(final_id + "-garment-" + str(index).zfill(3), data, provenance))
        result = dict(schema_version=1, artifacts=garments + [primary])
        terminal = self.snapshot(key, "succeeded", {"result": dict(id=final_id, revision=primary["revision"])})
        return result, terminal

    def submit(self, request, manifest, idempotency_key):
        from extensions import NodeRegistry

        registry = NodeRegistry()
        register(registry)
        validate_invocation(registry, request, manifest, self.describe())
        key = idempotency_key
        require(re.fullmatch(r"[a-f0-9]{64}", key), "invalid idempotency key")
        record = dict(request=request, manifest=manifest, fingerprint=self.fingerprint())
        with sqlite3.connect(self.database) as db:
            inserted = db.execute("INSERT OR IGNORE INTO jobs VALUES(?,?)", (key, canonical(record))).rowcount
        if not inserted:
            existing = self.read(key)
            require(
                canonical(existing["request"]) == canonical(request)
                and canonical(existing["manifest"]) == canonical(manifest)
                and existing["fingerprint"] == self.fingerprint(),
                "idempotency conflict",
            )
            return self.poll(key)
        try:
            result, terminal = self._run(key, request, manifest)
            record.update(result=result, terminal=terminal)
        except (ValueError, OSError, KeyError, TypeError) as error:
            record["diagnostic"] = str(error)
            record["terminal"] = self.snapshot(key, "failed", error="garment_split_failed")
        return self._store(key, record)["terminal"]

    def poll(self, key):
        record = self.read(key)
        if "terminal" not in record:
            # submit is synchronous. An unteminated record therefore belongs to
            # an interrupted local process and is never blindly replayed.
            record["terminal"] = self.snapshot(key, "failed", error="garment_split_interrupted")
            self._store(key, record)
        return record["terminal"]

    def lookup(self, key):
        return self.poll(key)

    def cancel(self, key):
        record = self.read(key)
        if "terminal" not in record:
            record["terminal"] = self.snapshot(key, "cancelled")
            self._store(key, record)
        return record["terminal"]

    def result_manifest(self, key):
        record = self.read(key)
        require(record.get("terminal", {}).get("state") == "succeeded", "result not available")
        return record["result"]

    def public_failure_message(self, snapshot):
        record = self.read(snapshot["job_id"])
        diagnostic = record.get("diagnostic", "")
        if "api_key_missing" in diagnostic:
            return "AI 衣服识别需要可用的 KIMI_API_KEY。请在本机配置后重启马良，再显式重试；不会要求你手工填写组件 ID。"
        if "review_render_failed" in diagnostic:
            return "无法生成 AI 衣服识别所需的模型与组件视图。请检查模型和当前引擎渲染环境后重试。"
        if "timed out" in diagnostic.lower() or "timeout" in diagnostic.lower():
            return "AI 衣服识别请求超时，未收到有效选择，也未自动重发。请稍后显式重试；原模型未改变。"
        if "garment_complete_no_wearable" in diagnostic:
            return "没有衣服同时通过完整可见表面与封闭拓扑检查，本次未发布换装产物。请查看未解决项和分割证据；不会把碎片加厚冒充完整衣服。"
        if "garment_complete_skin_invalid" in diagnostic:
            return "完整衣服的骨架、关节索引、蒙皮权重或 Inverse Bind 校验失败，本次未发布换装产物。请查看具体过程中的源模型与输出差异。"
        if "garment_segmentation" in diagnostic or "garment_complete_triangle" in diagnostic:
            return "完整衣服的多视角分割或三角面证据不完整，本次未发布换装产物。请查看具体过程并显式重试。"
        if "garment_inventory_no_geometry" in diagnostic:
            return "AI 未能可靠定位可拆分的衣服组件，本次未修改原模型。请换用更清晰的模型或补充视觉证据后重试。"
        if "garment_inventory" in diagnostic or "vision_" in diagnostic or "api_output" in diagnostic:
            return "AI 衣服识别结果不完整或缺少组件图像证据，本次未执行拆分。请查看具体过程并显式重试。"
        if "cloth_rigged_source" in diagnostic:
            return "衣服及原骨架、蒙皮已保留，但当前布料准备器尚不接受带 Skin 的输入；本次只完成已绑骨表面拆分，未宣称布料动态通过。"
        if "skin_invalid" in diagnostic:
            return "已绑骨 GLB 的 Skin、关节索引或蒙皮权重无效。请检查 JOINTS_0、WEIGHTS_0、骨架节点和 Inverse Bind Matrices。"
        if "rigged_source" in diagnostic:
            return "当前操作不支持该已绑骨输入形式；请确认 GLB 的 Skin 和网格结构符合首版约束。"
        if any(
            code in diagnostic
            for code in ("unknown_component", "triangle_out_of_range", "selection_", "duplicate", "spec_invalid")
        ):
            return "衣服清单或几何选择无效。请核对每件衣服的 component_id、源三角面和重复选择；原模型未改变。"
        if "source" in diagnostic:
            return "衣服拆分源模型无效或已变化。请重新选择原始静态 GLB，并保留其内嵌依赖。"
        return "衣服拆分未完成，未发布不完整结果。请查看“具体过程”中的 AI 识别与本地运行记录后显式重试。"
