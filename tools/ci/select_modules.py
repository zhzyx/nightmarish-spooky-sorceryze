#!/usr/bin/env python3
"""Select exactly the modules owning changed paths, or an explicit full matrix."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

NAME = re.compile(r"^[a-z][a-z0-9-]*$")
HANDLERS = {"generic", "common-only", "engine-next", "gameplay", "web", "tianxuan", "integration", "build"}
ZERO_SHA = "0" * 40


def _string_list(value: Any, field: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ValueError(f"{field} must be a list of non-empty strings")
    return cast(list[str], value)


def _path(value: str) -> str:
    normalized = value.rstrip("/")
    if not normalized or value.startswith(("/", "~")) or "\\" in value or "\x00" in value:
        raise ValueError(f"Unsafe registry path: {value!r}")
    if any(part in {"", ".", ".."} for part in normalized.split("/")):
        raise ValueError(f"Registry path must be normalized and repository-relative: {value!r}")
    return normalized


def load_registry(path: Path) -> dict[str, Any]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"Cannot load module registry {path}: {error}") from error
    if not isinstance(document, dict):
        raise ValueError("Module registry root must be an object")
    validate_registry(document)
    return cast(dict[str, Any], document)


def validate_registry(document: dict[str, Any]) -> None:
    if not isinstance(document, dict) or document.get("schema_version") != 1:
        raise ValueError("Module registry schema_version must be 1")
    modules = document.get("modules")
    if not isinstance(modules, list) or not modules:
        raise ValueError("Module registry must contain modules")
    names: set[str] = set()
    prefixes: dict[str, str] = {}
    status_checks: set[str] = set()
    for module in modules:
        if not isinstance(module, dict):
            raise ValueError("Every module must be an object")
        name = module.get("name")
        if not isinstance(name, str) or not NAME.fullmatch(name) or name in names:
            raise ValueError(f"Invalid or duplicate module name: {name!r}")
        names.add(name)
        if module.get("handler") not in HANDLERS:
            raise ValueError(f"{name}: unknown or missing handler")
        paths = _string_list(module.get("paths"), f"{name}.paths")
        if not paths:
            raise ValueError(f"{name}: at least one owned path is required")
        for raw_path in paths:
            prefix = _path(raw_path)
            if prefix in prefixes:
                raise ValueError(f"Path {prefix!r} is registered by both {prefixes[prefix]} and {name}")
            prefixes[prefix] = name
        if not isinstance(module.get("runner"), str) or not module["runner"].strip():
            raise ValueError(f"{name}: runner is required")
        for field in ("setup_commands", "build_commands", "test_commands", "status_checks"):
            _string_list(module.get(field), f"{name}.{field}")
        if module["handler"] == "generic" and not module["test_commands"]:
            raise ValueError(f"{name}: generic modules must execute at least one test command")
        if module["handler"] == "common-only" and (module["build_commands"] or module["test_commands"]):
            raise ValueError(f"{name}: common-only modules cannot define module commands")
        for check in module["status_checks"]:
            if check in status_checks:
                raise ValueError(f"Duplicate CI status check: {check!r}")
            status_checks.add(check)
        dependencies = module.get("dependencies", [])
        _string_list(dependencies, f"{name}.dependencies")
        if name in dependencies:
            raise ValueError(f"{name}: a module cannot depend on itself")
    common = document.get("common_checks")
    if not isinstance(common, list) or not common:
        raise ValueError("At least one common check is required")
    for check in common:
        if not isinstance(check, dict):
            raise ValueError("Every common check must be an object")
        _string_list(check.get("commands"), "common_checks.commands")
        name = check.get("name")
        if not isinstance(name, str) or not name.strip() or name in status_checks:
            raise ValueError(f"Invalid or duplicate common check: {name!r}")
        status_checks.add(name)
    for module in modules:
        unknown = set(module.get("dependencies", [])) - names
        if unknown:
            raise ValueError(f"{module['name']}: unknown dependencies: {sorted(unknown)}")


def owning_module(document: dict[str, Any], changed_path: str) -> dict[str, Any]:
    normalized = _path(changed_path)
    matches: list[tuple[int, dict[str, Any]]] = []
    for module in document["modules"]:
        for raw_prefix in module["paths"]:
            prefix = raw_prefix.rstrip("/")
            if normalized == prefix or normalized.startswith(prefix + "/"):
                matches.append((len(prefix), module))
    if not matches:
        raise ValueError(f"Unregistered changed path: {changed_path}; add exactly one module mapping")
    longest = max(length for length, _ in matches)
    winners = [module for length, module in matches if length == longest]
    if len({module["name"] for module in winners}) != 1:
        raise ValueError(f"Ambiguous module ownership for {changed_path}")
    return winners[0]


def select_modules(document: dict[str, Any], files: list[str], full: bool = False) -> list[dict[str, Any]]:
    if full:
        return list(document["modules"])
    selected: dict[str, dict[str, Any]] = {}
    for changed_path in files:
        module = owning_module(document, changed_path)
        selected[module["name"]] = module
    return [module for module in document["modules"] if module["name"] in selected]


def changed_files(repo: Path, base: str, head: str) -> tuple[str, list[str]]:
    resolved_base = base
    if not resolved_base or resolved_base == ZERO_SHA:
        resolved_base = subprocess.check_output(
            ["git", "merge-base", "origin/main", head], cwd=repo, text=True
        ).strip()
    command = ["git", "diff", "--no-renames", "--name-only", "-z", f"{resolved_base}...{head}"]
    result = subprocess.run(command, cwd=repo, check=True, capture_output=True)
    files = [item for item in result.stdout.decode("utf-8").split("\x00") if item]
    return resolved_base, files


def selection_document(
    document: dict[str, Any], modules: list[dict[str, Any]], files: list[str], base: str, head: str, full: bool
) -> dict[str, Any]:
    ownership = {path: owning_module(document, path)["name"] for path in files}
    generic = [
        {"module": module["name"], "runs_on": module["runner"]}
        for module in modules
        if module["handler"] == "generic"
    ]
    return {
        "schema_version": 1,
        "mode": "full" if full else "changed",
        "base": base,
        "head": head,
        "changed_files": files,
        "path_ownership": ownership,
        "modules": [module["name"] for module in modules],
        "generic_matrix": generic,
        "status_checks": {module["name"]: module["status_checks"] for module in modules},
    }


def _write_outputs(path: Path, selection: dict[str, Any]) -> None:
    compact = lambda value: json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    with path.open("a", encoding="utf-8") as stream:
        stream.write(f"modules={compact(selection['modules'])}\n")
        stream.write(f"generic_matrix={compact(selection['generic_matrix'])}\n")
        stream.write(f"generic_count={len(selection['generic_matrix'])}\n")
        stream.write(f"selection={compact(selection)}\n")


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=root)
    parser.add_argument("--registry", type=Path, default=Path(__file__).with_name("modules.json"))
    parser.add_argument("--base", default="")
    parser.add_argument("--head", default="")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--file", action="append", dest="files", default=[])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--github-output", type=Path)
    args = parser.parse_args(argv)
    try:
        registry = load_registry(args.registry)
        full = args.full
        if args.files and (args.base or args.head):
            parser.error("--file cannot be combined with --base or --head")
        if full:
            files = []
            base = args.base
            head = args.head
        elif args.files:
            files = args.files
            base = ""
            head = ""
        else:
            if not args.head:
                parser.error("--head is required unless --full or --file is used")
            base, files = changed_files(args.repo, args.base, args.head)
        modules = select_modules(registry, files, full=full)
        selection = selection_document(registry, modules, files, base, head, full)
        encoded = json.dumps(selection, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(encoded, encoding="utf-8")
        else:
            sys.stdout.write(encoded)
        if args.github_output:
            _write_outputs(args.github_output, selection)
    except (ValueError, subprocess.CalledProcessError, OSError) as error:
        print(f"Module selection failed closed: {error}", file=sys.stderr)
        if os.environ.get("GITHUB_ACTIONS") == "true":
            print(f"::error::{error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
