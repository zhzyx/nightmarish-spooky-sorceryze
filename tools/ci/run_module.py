#!/usr/bin/env python3
"""Execute one generic module's registered setup, build and test commands."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from select_modules import load_registry


def run_module(repo: Path, registry_path: Path, name: str) -> int:
    registry = load_registry(registry_path)
    matches = [module for module in registry["modules"] if module["name"] == name]
    if len(matches) != 1:
        raise ValueError(f"Unknown module: {name!r}")
    module = matches[0]
    if module["handler"] != "generic":
        raise ValueError(f"Module {name!r} is handled by {module['handler']}, not the generic runner")
    commands = [
        (stage, command)
        for stage in ("setup_commands", "build_commands", "test_commands")
        for command in module[stage]
    ]
    if not any(stage == "test_commands" for stage, _ in commands):
        raise ValueError(f"Module {name!r} has no real test command")
    for stage, command in commands:
        print(f"::group::{name} {stage}: {command}", flush=True)
        result = subprocess.run(command, cwd=repo, shell=True, executable="/bin/bash")
        print("::endgroup::", flush=True)
        if result.returncode:
            print(f"Module {name} {stage} failed with exit code {result.returncode}", file=sys.stderr)
            return result.returncode
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--registry", type=Path, default=Path(__file__).with_name("modules.json"))
    parser.add_argument("--module", required=True)
    args = parser.parse_args(argv)
    try:
        return run_module(args.repo, args.registry, args.module)
    except (ValueError, OSError) as error:
        print(f"Module execution failed closed: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
