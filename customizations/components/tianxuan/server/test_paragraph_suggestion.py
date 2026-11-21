import json

import pytest
from api import create_app
from fastapi.testclient import TestClient
from tianxuan_core import Tianxuan


@pytest.fixture()
def preview(tmp_path, monkeypatch):
    store = Tianxuan(str(tmp_path / "preview.db"))
    owner = store.register("Design", "owner@example.invalid", "passwd123")["user_id"]
    source = "  重复  \r\n\t\r\n  重复  \r\n\r\n末段\n\u00a0\n尾  \n"
    doc = store.create_doc(owner, "草案", source)
    requests = []
    result = {"content": "  调整🖊️  \n下一行  \n"}

    def model(gateway, tenant, actor, messages):
        requests.append(json.loads(messages[-1]["content"]))
        if callback := result.get("during_generation"):
            callback()
        return result

    monkeypatch.setattr("paragraph_suggestion.workspace_reply", model)
    client = TestClient(create_app(store))
    url = f"/api/v1/docs/{doc['id']}"
    auth = {"Authorization": "Bearer " + store.issue_access_key(owner, owner, "test")["key"]}
    with client:
        yield store, owner, client, url, auth, doc, requests, result
    store.db.close()


def test_preview_then_accept_only_the_second_identical_paragraph(preview):
    store, _, client, url, auth, doc, requests, _ = preview
    payload = {"expected_version": 1, "paragraph": 2, "instruction": "简化"}
    response = client.post(url + "/paragraph-suggestion", json=payload, headers=auth)
    assert response.status_code == 200, response.text
    candidate = response.json()
    expected = "  重复  \r\n\t\r\n  调整🖊️  \r\n下一行  \r\n\r\n末段\n\u00a0\n尾  \n"
    assert candidate == {
        "document_id": doc["id"],
        "expected_version": 1,
        "paragraph": 2,
        "original": "  重复  ",
        "replacement": "  调整🖊️  \r\n下一行  ",
        "candidate_body": expected,
    }
    assert requests == [{"paragraph": "  重复  ", "instruction": "简化"}]
    assert store.get_doc(doc["id"])["version"] == 1
    patch = {"expected_version": 1, "body_md": candidate["candidate_body"], "call_id": "accept-2"}
    first = client.patch(url, json=patch, headers=auth)
    assert first.status_code == 200, first.text
    assert client.patch(url, json=patch, headers=auth).json() == first.json()
    assert store.version(doc["id"], 1)["body_md"] == doc["body_md"]
    assert store.version(doc["id"], 2)["body_md"].encode() == expected.encode()
    assert len(store.versions(doc["id"])) == 2
    assert client.post(url + "/paragraph-suggestion", json=payload, headers=auth).status_code == 409
    assert len(requests) == 1


def test_rejections_and_edits_during_generation(preview):
    store, owner, client, url, auth, doc, requests, result = preview
    payload = {"expected_version": 1, "paragraph": 2, "instruction": "review"}

    def post(**changes):
        return client.post(url + "/paragraph-suggestion", json=payload | changes, headers=auth)

    assert post(paragraph=8).status_code == 409
    assert post(paragraph=True).status_code == 422
    assert post(instruction=" ").status_code == 422
    assert client.post(url + "/paragraph-suggestion", json=payload).status_code == 401
    editor = store.add_member(owner, "editor@example.invalid", "passwd123", role="editor")["user_id"]
    other_auth = {"Authorization": "Bearer " + store.issue_access_key(owner, editor, "test")["key"]}
    store.set_doc_field_permission(owner, doc["id"], "body_md", "admin")
    assert client.post(url + "/paragraph-suggestion", json=payload, headers=other_auth).status_code == 403
    assert requests == []
    result["content"] = "two\n \nparagraphs"
    assert post().status_code == 502
    result.update(content="one", during_generation=lambda: store.update_doc(owner, doc["id"], "other writer", 1))
    assert post().status_code == 409
    assert store.get_doc(doc["id"])["body_md"] == "other writer"
    assert len(store.versions(doc["id"])) == 2


def test_public_account_cannot_use_private_workspace_model(preview, monkeypatch):
    store, owner, _, url, _, _, requests, _ = preview
    monkeypatch.setenv("TIANXUAN_AUTH_MODE", "accounts")
    monkeypatch.setenv("TIANXUAN_PUBLIC_ORIGIN", "https://docs.example.invalid")
    monkeypatch.setenv("TIANXUAN_TENANT_ID", "another-workspace")
    with TestClient(create_app(store)) as client:
        auth = {"Authorization": "Bearer " + store.issue_session(owner)}
        response = client.post(
            url + "/paragraph-suggestion",
            headers=auth,
            json={"instruction": "edit", "paragraph": 1, "expected_version": 1},
        )
        assert response.status_code == 403
    assert requests == []


def test_multiline_suggestion_inherits_unterminated_final_paragraph_eol(preview):
    store, owner, client, url, auth, doc, _, result = preview
    store.update_doc(owner, doc["id"], "first\r\n\r\nlast", 1)
    result["content"] = "row1\nrow2"
    response = client.post(
        url + "/paragraph-suggestion",
        headers=auth,
        json={"instruction": "expand", "paragraph": 2, "expected_version": 2},
    )
    assert response.status_code == 200
    assert response.json()["candidate_body"] == "first\r\n\r\nrow1\r\nrow2"
