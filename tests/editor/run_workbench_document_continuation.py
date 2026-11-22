"""Drive an author, paragraph model and revision comparison through one native editor window."""

import argparse
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

import httpx
from run_workbench_issue_detail import Tianxuan, copy_editor, create_app, sanitized_environment
from run_workbench_offline_document import serve
from run_workbench_paragraph_suggestion import ModelGateway


def exercise(base, binary):
    store = Tianxuan(str(base / "documents.db"))
    account = store.register("Studio", "writer@example.invalid", secrets.token_urlsafe())
    actor = account["user_id"]
    token = store.issue_session(actor)
    inputs = []

    def model(request):
        inputs.append(json.loads(json.loads(request.content)["messages"][-1]["content"]))
        return httpx.Response(
            200,
            json={
                "model": "fixture",
                "usage": {"prompt_tokens": 4, "completion_tokens": 2},
                "choices": [{"message": {"content": "步伐：两拍，第二拍落在桥面中心"}}],
            },
        )

    gateway = ModelGateway(":memory:", transport=httpx.MockTransport(model))
    auth = dict(
        TIANXUAN_AUTH_MODE="accounts",
        TIANXUAN_PUBLIC_ORIGIN="https://fixture.invalid",
        TIANXUAN_TENANT_ID=account["tenant_id"],
        TIANXUAN_CHAT_BASE_URL="https://model.invalid/v1",
        TIANXUAN_CHAT_MODEL="fixture",
        TIANXUAN_CHAT_MODEL_KEY="fixture",
        GONGGONG_WORKSPACE="",
    )
    try:
        with patch.dict(os.environ, auth), serve(create_app(store, gateway=gateway), 0) as port:
            editor = copy_editor(binary, base / "engine")
            project = base / "project"
            project.mkdir()
            (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="Q14"\n')
            for script in ["workbench_issue_detail.gd", "workbench_document_continuation.gd"]:
                shutil.copyfile(Path(__file__).with_name(script), project / script)
            env = sanitized_environment(base) | dict(
                TIANXUAN_TOKEN=token, TIANXUAN_API=f"http://127.0.0.1:{port}", TIANXUAN_PROJECT="studio/design"
            )
            proc = subprocess.run(
                [
                    str(editor),
                    "--headless",
                    "--editor",
                    "--path",
                    str(project),
                    "--script",
                    "res://workbench_document_continuation.gd",
                ],
                cwd=base,
                env=env,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=125,
            )
            output = (proc.stdout + proc.stderr).replace(token, "[redacted]")
            records = [json.loads(line[4:]) for line in output.splitlines() if line.startswith("Q14=")]
            if proc.returncode or "SCRIPT ERROR" in output or len(records) != 1:
                raise AssertionError(output[-6000:])
            seen = records[0]
            versions = [store.version(seen["id"], n) for n in (1, 2, 3)]
            bodies = [v["body_md"].split("\n\n") for v in versions]
            assert all(v["author"] == actor for v in versions)
            assert inputs == [{"paragraph": "步伐：两拍", "instruction": "补充第二拍的落点"}]
            assert bodies == [
                ["目标：保持剪影", b, c]
                for b, c in [
                    ("步伐：两拍", "镜头不动"),
                    ("步伐：两拍，第二拍落在桥面中心", "镜头不动"),
                    ("步伐：两拍，第二拍落在桥面中心", "镜头保持三秒"),
                ]
            ]
            assert seen["final"] == versions[-1]["body_md"]
            for d, old, new in zip(seen["diffs"], bodies[:-1], bodies[1:], strict=True):
                before, after = next((a, b) for a, b in zip(old, new, strict=True) if a != b)
                assert "-" + before in d["diff"].splitlines() and "+" + after in d["diff"].splitlines()
            return dict(
                editor_sha256=hashlib.file_digest(binary.open("rb"), "sha256").hexdigest(),
                model_transport="deterministic HTTP fixture",
                model_inputs=inputs,
                versions=versions,
                window=seen,
            )
    finally:
        gateway.close()
        store.db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="workbench-q14-") as directory:
        result = exercise(Path(directory), args.godot.resolve(strict=True))
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
