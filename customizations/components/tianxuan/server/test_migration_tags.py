"""Recover source tag identities and signed object bytes through both published-history transports."""

import base64
import hashlib
import json
import os
import subprocess

from api import create_app
from fastapi.testclient import TestClient
from native_store import NativeStore
from tianxuan_core import Tianxuan


def test_import_tag_targets_and_signed_bytes(tmp_path, record_property):
    store = Tianxuan(":memory:")
    db = tmp_path / "native.sqlite"
    client = TestClient(create_app(store, native_store=NativeStore(db)))
    from git_archive import capture
    from import_git_history import import_git_history

    actor = store.register("owners", "owner@example.invalid", "test-password")["user_id"]
    tenant = store.actor_context(actor)["tenant"]
    repo = tmp_path / "source"
    repo.mkdir()
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    env.update(
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_CONFIG_NOSYSTEM="1",
        GIT_AUTHOR_NAME="Release",
        GIT_AUTHOR_EMAIL="release@example.invalid",
        GIT_COMMITTER_NAME="Release",
        GIT_COMMITTER_EMAIL="release@example.invalid",
        GIT_AUTHOR_DATE="2026-11-18T08:00:00+08:00",
        GIT_COMMITTER_DATE="2026-11-18T08:00:00+08:00",
    )

    def git(*args, data=None):
        return subprocess.check_output(["git", "-C", str(repo), *args], input=data, env=env)

    git("init", "-q", "-b", "main", "--object-format=sha1")
    git("commit", "--allow-empty", "-qm", "initial")
    head = git("rev-parse", "HEAD").decode().strip()
    blob = git("hash-object", "-w", "--stdin", data=b"tagged blob").decode().strip()
    git("tag", "light", blob)
    key = tmp_path / "signing-key"
    subprocess.run(
        ["ssh-keygen", "-q", "-t", "ed25519", "-C", "release@example.invalid", "-f", str(key), "-N", ""], check=True
    )
    signers = tmp_path / "allowed-signers"
    signers.write_bytes(b"release@example.invalid " + key.with_suffix(".pub").read_bytes().strip() + b"\n")
    git(
        "-c",
        "gpg.format=ssh",
        "-c",
        f"user.signingkey={key}",
        "tag",
        "-s",
        "-F",
        "-",
        "signed",
        data=b"release notes\n" * 4100,
    )
    key.unlink()
    signature_verification = (
        git("-c", f"gpg.ssh.allowedSignersFile={signers}", "verify-tag", "--format=%(objectname)", "signed")
        .decode()
        .strip()
    )
    signed = git("rev-parse", "refs/tags/signed").decode().strip()
    raw = git("cat-file", "tag", signed)
    assert signature_verification == signed and b"-----BEGIN SSH SIGNATURE-----" in raw
    git("-c", "advice.nestedTag=false", "tag", "-am", "outer annotation", "release/outer", signed)
    outer = git("rev-parse", "refs/tags/release/outer").decode().strip()
    snapshot = tmp_path / "snapshot"
    snapshot.mkdir()
    mirror = snapshot / "archive.git"
    git("clone", "--quiet", "--mirror", "--", str(repo), str(mirror))
    git("-C", str(mirror), "remote", "set-url", "origin", "https://github.com/sample/repo.git")
    report = json.loads(capture("sample/repo", snapshot).read_bytes())
    sample_bundle = (snapshot / "history.bundle").read_bytes()
    assert hashlib.sha256(sample_bundle).hexdigest() == report["bundle_sha256"]
    receipt = import_git_history(snapshot, db, tenant, actor, "isolated")
    # After publication the product must use the native catalog alone.
    snapshot.rename(tmp_path / "offline-capture")
    repo.rename(tmp_path / "offline-source")
    query = {"project": "isolated", "revision": receipt["revision"]}
    headers = {"X-Actor": actor}

    def read(name, **params):
        return client.get("/api/v1/migration/history/" + name, params={**query, **params}, headers=headers)

    def tool(name, **params):
        return client.post(
            "/api/v1/tools", headers=headers, json={"name": "migration.history." + name, "payload": {**query, **params}}
        )

    first = read("tags", limit=2).json()
    assert first == tool("tags", limit=2).json() and first["next_offset"] == 2
    last = read("tags", offset=first["next_offset"], limit=2).json()
    assert last["next_offset"] is None
    tags = first["items"] + last["items"]
    assert tags == [
        dict(
            ref="refs/tags/light",
            kind="lightweight",
            oid=blob,
            target_oid=blob,
            target_type="blob",
            peeled_oid=blob,
            peeled_type="blob",
        ),
        dict(
            ref="refs/tags/release/outer",
            kind="annotated",
            oid=outer,
            target_oid=signed,
            target_type="tag",
            peeled_oid=head,
            peeled_type="commit",
        ),
        dict(
            ref="refs/tags/signed",
            kind="annotated",
            oid=signed,
            target_oid=head,
            target_type="commit",
            peeled_oid=head,
            peeled_type="commit",
        ),
    ]
    first = read("tag_object", oid=signed).json()
    assert first == tool("tag_object", oid=signed).json() and first["next_offset"] == 49152
    last = tool("tag_object", oid=signed, byte_offset=first["next_offset"]).json()
    assert last["oid"] == first["oid"] == signed and last["next_offset"] is None
    recovered = base64.b64decode(first["data"]) + base64.b64decode(last["data"])
    assert recovered == raw and first["size"] == len(raw)
    assert hashlib.sha1(f"tag {len(raw)}\0".encode() + recovered).hexdigest() == signed
    assert read("tag_object", oid=head).status_code == 404
    assert read("tag_object", oid="signed").status_code == 422
    assert tool("tag_object", oid=signed, byte_offset=len(raw) + 1).status_code == 422
    assert read("tags", revision="0" * 64).status_code == 404
    outsider = store.register("others", "other@example.invalid", "test-password")["user_id"]
    assert (
        client.get(
            "/api/v1/migration/history/tag_object", params={**query, "oid": signed}, headers={"X-Actor": outsider}
        ).status_code
        == 404
    )
    record_property(
        "tag_receipt",
        json.dumps(
            dict(
                publication=receipt["publication"],
                capture=report,
                tags=tags,
                verified_signed_oid=signature_verification,
                source_tag_sha256=hashlib.sha256(raw).hexdigest(),
                received_tag_sha256=hashlib.sha256(recovered).hexdigest(),
                signed_size=len(raw),
                page_bytes=[first["next_offset"], len(raw) - first["next_offset"]],
                allowed_signer=signers.read_text(encoding="utf-8").strip(),
                source_bundle_base64=base64.b64encode(sample_bundle).decode("ascii"),
            )
        ),
    )
