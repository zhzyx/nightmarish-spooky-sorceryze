"""Import freshly authorized issue inputs with the installed local Godot editor."""

import hashlib
import io
import json
import os
import re
import struct
import subprocess
import tempfile
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from native_store import NativeStoreError
from native_workspace import Limits, _capture_stage_owner, _cleanup_owned_stage, _rename_prepared, absolute

ASSETS = {"assets/model.glb", "assets/concept.png"}
MAX_ARCHIVE = 17 * 1024 * 1024


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise NativeStoreError("Godot input service redirect refused")


def fetch_inputs(issue):
    origin = urllib.parse.urlsplit(os.environ.get("TIANXUAN_PUBLIC_ORIGIN", ""))
    if (
        not origin.hostname
        or origin.username is not None
        or origin.password is not None
        or origin.query
        or origin.fragment
        or origin.path not in ("", "/")
        or not (origin.scheme == "https" or origin.scheme == "http" and origin.hostname in {"127.0.0.1", "::1"})
    ):
        raise NativeStoreError("Trusted Tianxuan service origin required")
    token = os.environ.get("TIANXUAN_TOKEN")
    if not token:
        raise NativeStoreError("Authenticated Tianxuan token required")
    url = f"{origin.scheme}://{origin.netloc}/api/v1/issues/{issue}/work/godot-inputs"
    request = urllib.request.Request(url, headers={"Authorization": "Bearer " + token, "Cache-Control": "no-cache"})
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=30) as response:
        if response.headers.get_content_type() != "application/zip":
            raise NativeStoreError("Expected approved input archive")
        data = response.read(MAX_ARCHIVE + 1)
    if len(data) > MAX_ARCHIVE:
        raise NativeStoreError("Approved input archive exceeds limit")
    return data


def validate_model(content):
    # This operation supplies self-contained GLB files. External files have no
    # issue approval and cannot participate in this import.
    if len(content) < 20:
        raise NativeStoreError("Incomplete GLB header")
    magic, version, size, json_size, chunk_type = struct.unpack_from("<4sIII4s", content)
    if magic != b"glTF" or version != 2 or size != len(content) or json_size > size - 20 or chunk_type != b"JSON":
        raise NativeStoreError("Invalid GLB header")
    document = json.loads(content[20 : 20 + json_size])
    pending = [document]
    while pending:
        value = pending.pop()
        if isinstance(value, dict):
            if "uri" in value and not (isinstance(value["uri"], str) and value["uri"].startswith("data:")):
                raise NativeStoreError("External GLB inputs have no issue approval")
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)


def unpack_inputs(packed, stage):
    with zipfile.ZipFile(io.BytesIO(packed)) as archive:
        files = archive.infolist()
        names = {f.filename for f in files}
        if (
            len(names) != len(files)
            or "project.godot" not in names
            or not names & ASSETS
            or names - ASSETS - {"project.godot"}
        ):
            raise NativeStoreError("Unexpected Godot input project")
        (stage / "assets").mkdir()
        digests = {}
        for f in files:
            if f.compress_type != zipfile.ZIP_STORED or f.file_size > Limits().file_bytes:
                raise NativeStoreError("Unexpected input encoding or size")
            content = archive.read(f)
            if f.filename == "assets/model.glb":
                validate_model(content)
            if f.filename in ASSETS:
                digests[f.filename] = hashlib.sha256(content).hexdigest()
            (stage / f.filename).write_bytes(content)
        return digests


def check_import(stage, assets):
    for name, digest in assets.items():
        source = absolute(stage / name)
        if hashlib.sha256(source.read_bytes()).hexdigest() != digest:
            raise NativeStoreError("Approved import source changed")
        description = absolute(stage / (name + ".import")).read_text(encoding="utf8")
        # Godot records platform-specific texture paths as path.<feature>.
        outputs = re.findall(r'^path(?:\.[^=\r\n]+)?="res://(\.godot/imported/[^/"\\\r\n]+)"\s*$', description, re.M)
        artifacts = [absolute(stage / path) for path in outputs]
        if not artifacts or any(not path.is_file() or not path.stat().st_size for path in artifacts):
            raise NativeStoreError("Godot import output missing")


def import_issue(issue_id, destination):
    if not isinstance(issue_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,256}", issue_id):
        raise NativeStoreError("Invalid issue identifier")
    destination = absolute(destination, missing=True)
    if os.path.lexists(destination):
        raise NativeStoreError("Destination already exists")
    executable = absolute(os.environ.get("TIANXUAN_GODOT_EXECUTABLE", ""))
    if not executable.is_file():
        raise NativeStoreError("Installed Godot executable required")
    packed = fetch_inputs(issue_id)
    stage = Path(tempfile.mkdtemp(prefix=".godot-import-", dir=destination.parent))
    owner = _capture_stage_owner(stage)
    try:
        assets = unpack_inputs(packed, stage)
        # Never pass the personal key to the editor or its subprocesses.
        env = {
            key: value
            for key, value in os.environ.items()
            if key.upper()
            in {
                "PATH",
                "SYSTEMROOT",
                "COMSPEC",
                "TEMP",
                "TMP",
                "TMPDIR",
                "HOME",
                "USERPROFILE",
                "APPDATA",
                "LOCALAPPDATA",
                "LANG",
                "LC_ALL",
                "XDG_RUNTIME_DIR",
                "XDG_CONFIG_HOME",
                "XDG_DATA_HOME",
                "XDG_CACHE_HOME",
            }
        }
        subprocess.run(
            [str(executable), "--headless", "--path", str(stage), "--import"],
            env=env,
            cwd=stage,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=180,
            check=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        check_import(stage, assets)
        if fetch_inputs(issue_id) != packed:
            raise NativeStoreError("Current approved inputs changed during import")
        _rename_prepared(stage, destination, Limits(), owner)
    except BaseException as error:
        _cleanup_owned_stage(stage, owner, error)
        raise
    return {"issue_id": issue_id, "destination": str(destination), "assets": assets}
