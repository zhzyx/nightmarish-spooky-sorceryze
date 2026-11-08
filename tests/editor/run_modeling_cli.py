"""Explicit opt-in real GPT CLI modeling acceptance in an isolated native editor."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from editor_test_isolation import copy_editor


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--godot", required=True, type=Path)
    parser.add_argument("--cli", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--proxy")
    parser.add_argument("--capture", action="store_true")
    parser.add_argument("--real-cli", action="store_true", help="Authorize one real CLI modeling request")
    args = parser.parse_args()
    if not args.real_cli:
        parser.error("--real-cli is required; this check consumes the existing CLI account's model usage")
    base = args.output.resolve()
    base.mkdir(parents=True, exist_ok=False)
    engine = copy_editor(args.godot.resolve(strict=True), base / "engine")
    project = base / "project"
    project.mkdir()
    (project / "project.godot").write_text(
        'config_version=5\n[application]\nconfig/name="Maliang GPT Modeling Acceptance"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n',
        encoding="utf-8",
    )
    output = base / "output"
    output.mkdir()
    config = base / "config.json"
    config.write_text(
        json.dumps(
            dict(
                real_cli_authorized=True,
                python=sys.executable,
                cli=str(args.cli.resolve(strict=True)),
                output=str(output),
                capture=args.capture,
            )
        ),
        encoding="utf-8",
    )
    environment = os.environ.copy()
    environment.pop("AINATIVE_PYTHON", None)
    environment.pop("AINATIVE_PROVIDER_FACTORY", None)
    environment["MALIANG_MODELING_ACCEPTANCE"] = str(config)
    if args.proxy:
        environment.update(HTTP_PROXY=args.proxy, HTTPS_PROXY=args.proxy, NO_PROXY="localhost,127.0.0.1,::1")
    command = [str(engine)]
    command += ["--position", "-20000,-20000", "--resolution", "1440x1000"] if args.capture else ["--headless"]
    command += [
        "--editor",
        "--path",
        str(project),
        "--script",
        str(Path(__file__).with_name("modeling_cli_acceptance.gd").resolve()),
    ]
    with (base / "editor.log").open("wb") as log:
        process = subprocess.run(command, env=environment, stdout=log, stderr=subprocess.STDOUT, timeout=1200)
    report = (
        json.loads((output / "acceptance.json").read_text(encoding="utf-8"))
        if (output / "acceptance.json").is_file()
        else {}
    )
    log = (base / "editor.log").read_text(encoding="utf-8", errors="replace")
    passed = process.returncode == 0 and report.get("ok") is True and "SCRIPT ERROR:" not in log
    print(json.dumps(dict(passed=passed, output=str(output), returncode=process.returncode)))
    if not passed:
        print(log[-10000:])
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
