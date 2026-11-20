#!/usr/bin/env python3
"""Fail the aggregate check unless every selected module really succeeded."""

from __future__ import annotations

import argparse
import json
from typing import Any

SPECIAL_JOBS = {
    "engine-next": ("engine-next",),
    "gameplay": ("gameplay",),
    "editor": ("editor-native",),
    "maliang": ("maliang-offline", "blender-geometry"),
    "web": ("web",),
    "tianxuan": ("tianxuan-tests", "tianxuan-deploy"),
    "integration": ("integration",),
    "build": ("build-scope", "native-cache"),
}
SUCCESS = "success"
INACTIVE = {"skipped"}


def validate_results(selection: dict[str, Any], needs: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if needs.get("select", {}).get("result") != SUCCESS:
        errors.append("module selection did not succeed")
    for job, observation in needs.items():
        result = observation.get("result") if isinstance(observation, dict) else None
        if result not in {SUCCESS, *INACTIVE}:
            errors.append(f"job {job} ended as {result!r}")
    if selection.get("mode") == "full" and needs.get("static-checks", {}).get("result") != SUCCESS:
        errors.append("full regression requires successful static checks")
    selected = selection.get("modules")
    if not isinstance(selected, list):
        return errors + ["selection has no module list"]
    generic = selection.get("generic_matrix")
    if not isinstance(generic, list):
        errors.append("selection has no generic matrix")
    elif generic and needs.get("module-tests", {}).get("result") != SUCCESS:
        errors.append("selected generic module tests did not all succeed")
    elif not generic and needs.get("module-tests", {}).get("result") not in INACTIVE:
        errors.append("empty generic matrix must leave module-tests skipped")
    for module in selected:
        for job in SPECIAL_JOBS.get(module, ()):
            if needs.get(job, {}).get("result") != SUCCESS:
                errors.append(f"selected module {module} required successful job {job}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection-json", required=True)
    parser.add_argument("--needs-json", required=True)
    args = parser.parse_args()
    try:
        selection = json.loads(args.selection_json)
        needs = json.loads(args.needs_json)
        errors = validate_results(selection, needs)
    except (json.JSONDecodeError, AttributeError) as error:
        print(f"Invalid CI summary inputs: {error}")
        return 2
    if errors:
        for error in errors:
            print(f"::error::{error}")
        return 1
    print("All selected module checks succeeded; unselected jobs were not counted as test passes.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
