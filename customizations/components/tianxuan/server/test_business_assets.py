"""Module-scoped model opens, independent unlink and current native source ACLs."""

import base64
import hashlib
import json
from contextlib import closing
from pathlib import Path

from api import create_app
from fastapi.testclient import TestClient
from native_store import NativeStore
from tianxuan_core import Tianxuan

ROOT = Path(__file__).resolve().parents[4]
MODULES = "/api/v1/business-modules"
NATIVE = "/api/v1/native"
PROJECT = {"project": "studio/game"}


def asset_list(module):
    return f"{NATIVE}/business-modules/{module}/assets"


def auth(store, user):
    return {"Authorization": "Bearer " + store.issue_session(user["user_id"])}


def b05_readback(directory):
    spec = json.loads((ROOT / "samples/gonggong-workbench/fixtures/b05/sample.json").read_text(encoding="utf-8"))
    model = spec["asset"]
    content = (ROOT / model["repo_source"]).read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    assert digest == model["sha256"]
    db = str(directory / "domain.db")
    native_db = directory / "native.db"
    domain = Tianxuan(db)
    with (
        closing(domain.db),
        TestClient(create_app(domain, native_store=NativeStore(native_db), native_only=True)) as client,
    ):
        owner = domain.register("studio", "owner@example.invalid", "fixture-pass")
        editor = domain.add_member(owner["user_id"], "editor@example.invalid", "fixture-pass")
        headers = [auth(domain, owner), auth(domain, editor)]
        edits = {model["path"]: base64.b64encode(content).decode("ascii")}
        batch = {"module": model["module"], "base": None, "reads": None, "edits": edits, "dependencies": {}}
        published = client.post(
            NATIVE + "/batches", headers=headers[0], json={"request_key": "seed", "changes": [batch]}
        )
        assert published.status_code == 200, published.text
        revision = published.json()["revisions"][model["module"]]
        reference = {"source_module": model["module"], "revision": revision, "path": model["path"]}
        modules = []
        assets = []
        for entry, identity in zip(spec["modules"], headers, strict=True):
            module = client.post(
                MODULES, params=PROJECT, headers=identity, json={"name": entry["title"], "call_id": entry["id"]}
            )
            assert module.status_code == 200, module.text
            modules.append(module.json()["id"])
            url = asset_list(modules[-1])
            link = client.post(url, params=PROJECT, headers=identity, json=reference)
            assert link.status_code == 200, link.text
            linked = link.json()
            assert linked == {**reference, "asset_id": linked["asset_id"]}
            assert client.post(url, params=PROJECT, headers=identity, json=reference).json() == linked
            assert client.get(url, params=PROJECT, headers=identity).json()["assets"] == [linked]
            opened = client.get(url + "/" + linked["asset_id"], params=PROJECT, headers=identity)
            assert opened.status_code == 200 and opened.content == content
            assets.append(linked["asset_id"])
        assert assets[0] == assets[1] and modules[0] != modules[1]
        reverse = NATIVE + "/assets/" + assets[0] + "/business-modules"
        before = client.get(reverse, params=PROJECT, headers=headers[0]).json()["module_ids"]
        assert before == sorted(modules)
        urls = [asset_list(module) + "/" + assets[0] for module in modules]
        unlinked = client.delete(urls[0], params=PROJECT, headers=headers[0])
        assert unlinked.status_code == 204

    reopened = Tianxuan(db)
    with (
        closing(reopened.db),
        TestClient(create_app(reopened, native_store=NativeStore(native_db), native_only=True)) as client,
    ):
        removed = client.get(urls[0], params=PROJECT, headers=headers[0])
        assert removed.status_code == 404
        assert client.get(asset_list(modules[0]), params=PROJECT, headers=headers[0]).json()["assets"] == []
        assert client.get(asset_list(modules[1]), params=PROJECT, headers=headers[1]).json()["assets"] == [linked]
        after = client.get(reverse, params=PROJECT, headers=headers[1]).json()["module_ids"]
        assert after == modules[1:]
        kept = client.get(urls[1], params=PROJECT, headers=headers[1])
        assert kept.status_code == 200 and kept.content == content
        return {
            **reference,
            "asset_id": assets[0],
            "model_bytes": len(content),
            "project": PROJECT["project"],
            "opened_sha256_by_module": dict.fromkeys(modules, digest),
            "reverse_index_before": before,
            "removed_module": modules[0],
            "unlink_status": unlinked.status_code,
            "restart_removed_open_status": removed.status_code,
            "restart_reverse_index": after,
            "restart_kept_open_status": kept.status_code,
            "restart_kept_sha256": hashlib.sha256(kept.content).hexdigest(),
        }


def test_b05_model_across_modules_after_reopen(tmp_path):
    b05_readback(tmp_path)


def test_scope_and_source_acl_on_every_operation(tmp_path):
    domain = Tianxuan()
    native = NativeStore(tmp_path / "native.db")
    with closing(domain.db), TestClient(create_app(domain, native_store=native, native_only=True)) as client:
        owner = domain.register("studio", "owner@example.invalid", "fixture-pass")
        editor = domain.add_member(owner["user_id"], "editor@example.invalid", "fixture-pass")
        viewer = domain.add_member(owner["user_id"], "viewer@example.invalid", "fixture-pass", role="viewer")
        other = domain.register("other", "other@example.invalid", "fixture-pass")
        owner_auth, editor_auth, viewer_auth, other_auth = (
            auth(domain, account) for account in (owner, editor, viewer, other)
        )
        tenant, actor = owner["tenant_id"], owner["user_id"]
        doc = domain.create_requirement(actor, "source", "Source", "outcome", "scope", "acceptance")
        source = domain.bind_native_requirement(actor, doc["id"])
        revision = native.submit(
            tenant, actor, "seed", [{"module": source, "base": None, "reads": None, "edits": {"model": b"model"}}]
        )["revisions"][source]
        reference = {"source_module": source, "revision": revision, "path": "model"}
        context = f"{NATIVE}/asset-context/{source}/{revision}/model"
        independent = client.get(context, params=PROJECT, headers=viewer_auth)
        assert independent.status_code == 200
        assert independent.json()["modules"] == []
        assert independent.json()["sha256"] == hashlib.sha256(b"model").hexdigest()
        assert client.get(context + "-missing", params=PROJECT, headers=owner_auth).status_code == 422
        url = asset_list("default")
        assert (
            client.post(url, params=PROJECT, headers=owner_auth, json={**reference, "path": "missing"}).status_code
            == 422
        )
        assert client.get(url, params=PROJECT, headers=owner_auth).json()["assets"] == []
        link = client.post(url, params=PROJECT, headers=owner_auth, json=reference)
        assert link.status_code == 200, link.text
        row = link.json()
        resolved = client.get(context, params=PROJECT, headers=viewer_auth).json()
        assert resolved["modules"] == [{"id": "default", "name": "默认模块"}]
        assert resolved["asset_id"] == row["asset_id"]
        assert client.get(context, params={"project": "other"}, headers=viewer_auth).json()["modules"] == []
        item = url + "/" + row["asset_id"]
        reverse = NATIVE + "/assets/" + row["asset_id"] + "/business-modules"
        for identity, project in ((other_auth, PROJECT), (owner_auth, {"project": "another"})):
            assert client.get(url, params=project, headers=identity).json()["assets"] == []
            assert client.get(item, params=project, headers=identity).status_code == 404
            assert client.delete(item, params=project, headers=identity).status_code == 404
            assert client.get(reverse, params=project, headers=identity).json()["module_ids"] == []
        assert client.get(item, params=PROJECT, headers=viewer_auth).content == b"model"
        assert client.post(url, params=PROJECT, headers=viewer_auth, json=reference).status_code == 403
        assert client.delete(item, params=PROJECT, headers=viewer_auth).status_code == 403
        assert client.get(item, params=PROJECT).status_code == 401
        assert client.get(item, params={**PROJECT, "tenant": tenant}, headers=editor_auth).status_code == 422
        domain.set_visibility(actor, doc["id"], "private")
        assert client.get(context, params=PROJECT, headers=editor_auth).status_code == 403
        assert client.get(context, params=PROJECT, headers=owner_auth).json() == resolved
        assert client.get(url, params=PROJECT, headers=editor_auth).json()["assets"] == []
        assert client.get(reverse, params=PROJECT, headers=editor_auth).json()["module_ids"] == []
        assert client.post(url, params=PROJECT, headers=editor_auth, json=reference).status_code == 403
        assert client.get(item, params=PROJECT, headers=editor_auth).status_code == 403
        assert client.delete(item, params=PROJECT, headers=editor_auth).status_code == 403
        assert client.get(item, params=PROJECT, headers=owner_auth).content == b"model"
