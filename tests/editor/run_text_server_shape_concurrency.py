"""Normal concurrent shaped-buffer use in a private self-contained engine copy.

The stable query RID and all independent buffers stay alive until the reader is
joined. Run this only against the repaired candidate; the original crash is the
before evidence. No user editor, project, configuration or model is involved.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from editor_test_isolation import copy_editor


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", type=Path, required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--require-interface", action="append", default=[])
    args = parser.parse_args()
    report = {"ok": False, "scope": "Private normal concurrent shape use on the repaired artifact only"}
    os.environ.pop("GONGGONG_WORKSPACE", None)
    try:
        artifact = args.godot.resolve(strict=True)
        expected = digest(artifact)
        if expected != args.expected_sha:
            raise ValueError("candidate_artifact_hash_mismatch")
        with tempfile.TemporaryDirectory(prefix="private_sc_text_shapes_") as temporary:
            folder = Path(temporary).resolve()
            binary = copy_editor(artifact, folder / "editor")
            if digest(binary) != expected:
                raise ValueError("private_copy_hash_mismatch")
            project = folder / "project"
            project.mkdir()
            (project / "project.godot").write_text(
                'config_version=5\n[application]\nconfig/name="Private Text Shapes"\n'
                '[rendering]\nrenderer/rendering_method="gl_compatibility"\n',
                encoding="utf-8",
            )
            shutil.copyfile(Path(__file__).with_name("text_server_shape_concurrency.gd"), project / "check.gd")
            configuration = binary.parent / "editor_data/gonggong/config.json"
            configuration.parent.mkdir()
            configuration.write_text('{"schema_version":1,"runtimes":{}}\n', encoding="utf-8")
            env = {
                key: value
                for key, value in os.environ.items()
                if not key.startswith(("GONGGONG_", "GODOT_AI_", "CANDIDATE_", "DESIGN_BATCH_"))
            }
            for key in ("APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "TEMP", "TMP"):
                private = folder / key
                private.mkdir()
                env[key] = str(private)
            result_path = folder / "result.json"
            env.update(GONGGONG_RUNTIME_CONFIG=str(configuration), TEXT_SERVER_RESULT=str(result_path))
            process = subprocess.run(
                [str(binary), "--headless", "--path", str(project), "--script", "res://check.gd"],
                cwd=folder,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=90,
            )
            result = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else {}
            tested = {case["class"] for case in result.get("cases", [])}
            missing = sorted(set(args.require_interface) - tested)
            report.update(
                ok=process.returncode == 0 and result.get("ok", False) and not missing,
                artifact_sha256=expected,
                exit_code=process.returncode,
                result=result,
                required_interfaces_missing=missing,
                stdout=process.stdout[-8000:],
                stderr=process.stderr[-8000:],
                self_contained_marker=(binary.parent / "_sc_").is_file(),
            )
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        report["error"] = str(error)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "out": str(args.out)}, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
