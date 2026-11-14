"""Risk-tiered submission audit, CI rollup deduplication, and multi-account queue planner.

Pure Python standard library; used by writer_submit, editor_delivery_finalize, and yanluo_host
to avoid uniform full-repo bottlenecks while preserving exact candidate and governance gates.
"""

from __future__ import annotations

import hashlib
import re
from bisect import bisect_left
from collections import Counter
from collections.abc import Collection, Iterable, Mapping, Sequence
from pathlib import PurePosixPath
from typing import Any

_ENGINE_IMPL_ROOTS = frozenset({"core", "drivers", "editor", "modules", "scene", "servers"})
_ENGINE_ALL_ROOTS = frozenset({
    "core",
    "drivers",
    "editor",
    "engine_next",
    "main",
    "modules",
    "platform",
    "scene",
    "servers",
})
_ENGINE_ROOT_FILES = frozenset({
    "SConstruct",
    "cpp.hint",
    "custom.py",
    "gles3_builders.py",
    "glsl_builders.py",
    "methods.py",
    "platform_methods.py",
    "scu_builders.py",
    "version.py",
})
_GOVERNANCE_EXACT_PATHS = frozenset({
    "CURRENT_FRAMEWORK.json",
    "customizations/host-agents.json",
    "customizations/platforms/components.json",
    "integrations/gonggong/frozen-distribution.json",
})
_GOVERNANCE_FILENAMES = frozenset({
    "AGENT.md",
    "SKILL.md",
    "admission.json",
    "agent.json",
    "build-impact.json",
    "component.json",
})
_HEQI_AUDITED_PATHS = frozenset({
    "customizations/platforms/development/git/heqi/concurrent-issue.md",
    "customizations/platforms/development/git/heqi/git-workflow.md",
    "customizations/platforms/development/git/heqi/integration_plan.py",
    "customizations/platforms/development/git/heqi/test_integration_plan.py",
    ".github/workflows/integration-plan.yml",
})
_TIER_ORDER = (
    "tier0_docs_telemetry",
    "tier1_isolated_host",
    "tier2_scoped_engine_impl",
    "tier3_shared_engine_or_ci",
    "tier4_governance_or_admission",
)


def path_overlap(left: Iterable[str], right: Iterable[str]) -> list[str]:
    """Return sorted paths in ``left`` that overlap ``right`` (including file/dir prefixes)."""
    ordered_right = sorted(set(right))
    members = set(ordered_right)
    matches: set[str] = set()
    for name in set(left):
        parts = name.split("/")
        if any("/".join(parts[:end]) in members for end in range(1, len(parts) + 1)):
            matches.add(name)
            continue
        position = bisect_left(ordered_right, name + "/")
        if position < len(ordered_right) and ordered_right[position].startswith(name + "/"):
            matches.add(name)
    return sorted(matches)


def classify_boundary(path: str) -> str:
    parts = PurePosixPath(path).parts
    first = parts[0]
    if len(parts) == 1:
        if first in _ENGINE_ROOT_FILES:
            return "engine_native"
        if first == "CURRENT_FRAMEWORK.json":
            return "framework_governance"
        if first in {"gonggong-workspace.json", "work-items.json", ".gonggong-local.example.json"}:
            return "host_adapters_and_apps"
        if PurePosixPath(first).suffix in {".md", ".txt"}:
            return "documentation_and_specs"
        return "ci_and_repo_config"
    if first == "thirdparty":
        return "thirdparty"
    if first == "framework" or parts[:2] == ("integrations", "gonggong") or path in _GOVERNANCE_EXACT_PATHS:
        return "framework_governance"
    if first in _ENGINE_ALL_ROOTS:
        return "engine_native"
    if first in {
        "archive",
        "data-collection",
        "distribution",
        "gonggong-diting-data",
        "olympus-hermes-data",
        "releases",
    }:
        return "telemetry_and_evidence"
    if first in {"Markdown", "design-docs", "doc"}:
        return "documentation_and_specs"
    if first in {"apps", "customizations", "deploy", "integrations", "tools"}:
        return "host_adapters_and_apps"
    if first in {"project", "samples", "tests"}:
        return "tests_and_samples"
    return "ci_and_repo_config"


def _is_governance_path(path: str) -> bool:
    if path in _GOVERNANCE_EXACT_PATHS or path.startswith("framework/"):
        return True
    p = PurePosixPath(path)
    if p.parts[:2] in {("archive", "olympus-retired-20261104"), ("data-collection", "requests")}:
        return False
    return p.name in _GOVERNANCE_FILENAMES


def _is_tier0_doc_or_telemetry(path: str) -> bool:
    if path in {"README.md", "AGENTS.md", "CONTRIBUTING.md"}:
        return True
    p = PurePosixPath(path)
    if p.parts[0] in {"design-docs", "Markdown"} and p.suffix == ".md":
        return True
    return p.parts[0] in {"data-collection", "gonggong-diting-data"} and p.suffix in {".json", ".jsonl", ".md"}


def _is_scoped_engine_impl(path: str, modified_regular: bool) -> bool:
    if not modified_regular:
        return False
    p = PurePosixPath(path)
    return (
        (p.parts[0] in _ENGINE_IMPL_ROOTS or p.parts[:2] == ("thirdparty", "metal-cpp"))
        and p.suffix in {".c", ".cc", ".cpp", ".cxx", ".m", ".mm"}
        and not p.stem.startswith("register_")
        and "tests" not in p.parts
    )


def classify_submission_diff(
    entries: Sequence[tuple[str, bool]] | Sequence[str],
    reviewed_host_inputs: Collection[str] = (),
) -> dict[str, Any]:
    """Compute a deterministic 5-tier review & Yanluo audit profile from changed paths.

    ``entries`` accepts either ``(path, modified_regular_file)`` pairs or plain path strings
    (plain strings are conservatively treated as ``modified_regular=False`` for C++ files).
    """
    host_set = set(reviewed_host_inputs)
    normalized: list[tuple[str, bool]] = []
    for item in entries:
        if isinstance(item, tuple):
            normalized.append((str(item[0]), bool(item[1])))
        else:
            normalized.append((str(item), False))

    max_level = 0
    trigger_paths: dict[str, list[str]] = {tier: [] for tier in _TIER_ORDER}
    boundaries: Counter[str] = Counter()
    touches_tianxuan = False
    touches_heqi = False
    touches_native_cache = False
    touches_routing = False
    touches_engine_next = False

    for path, modified in sorted(normalized):
        boundaries[classify_boundary(path)] += 1
        if path.startswith(("customizations/components/tianxuan/", "apps/tianxuan/", "deploy/")) or (
            path == ".github/workflows/tianxuan-tests.yml"
        ):
            touches_tianxuan = True
        if path.startswith("customizations/platforms/development/git/heqi/") or (
            path == ".github/workflows/integration-plan.yml"
        ):
            touches_heqi = True
        if path in {
            "tools/build_engine_modules.py",
            "tools/editor_native_cache.py",
            "tools/native_host_inputs.json",
            "tools/test_build_engine_modules.py",
            "tools/test_windows_editor_artifact.py",
            "tests/editor/test_editor_native_cache.py",
            "tests/editor/test_native_host_inputs.py",
            ".github/scripts/windows_editor_artifact.py",
            ".github/workflows/native-cache.yml",
            "SConstruct",
            "editor/SCsub",
        }:
            touches_native_cache = True
        if path in {
            ".github/workflows/engine_build_scope.yml",
            ".github/workflows/runner.yml",
            ".github/workflows/static_checks.yml",
            "modules/SCsub",
            "tools/build_engine_modules.py",
            "tests/python_build/check_engine_build_scope.py",
        }:
            touches_routing = True
        if path.startswith(("engine_next/", "modules/gameplay/")) or path in {
            ".github/workflows/engine_next_contract.yml",
            "tools/check_engine_next_contract.py",
            "tools/engine_next_contract.json",
            "tools/test_check_engine_next_contract.py",
        }:
            touches_engine_next = True

        if _is_governance_path(path):
            level = 4
        elif _is_tier0_doc_or_telemetry(path):
            level = 0
        elif path in _HEQI_AUDITED_PATHS or (modified and path in host_set):
            level = 1
        elif _is_scoped_engine_impl(path, modified):
            level = 2
        else:
            level = 3
        max_level = max(max_level, level)
        trigger_paths[_TIER_ORDER[level]].append(path)

    tier = _TIER_ORDER[max_level]
    mandatory_ci = {
        "issue-association",
        "📊 Static checks / Code style, file formatting, and docs",
    }
    if touches_tianxuan:
        mandatory_ci.add("Module and web tests")
    if touches_heqi:
        mandatory_ci.update({"planner-tests (ubuntu-latest)", "planner-tests (windows-latest)"})
    if touches_native_cache:
        mandatory_ci.update({"cache-tests (ubuntu-latest)", "cache-tests (windows-latest)"})
    if touches_routing:
        mandatory_ci.update({
            "verify-routing (windows-latest, windows, x64, platform=windows target=editor d3d12=no)",
            "verify-routing (macos-26, metal, arm64, platform=macos target=editor arch=arm64 metal=yes vulkan=no)",
        })
    if touches_engine_next:
        mandatory_ci.update({
            "No Godot source or link dependencies (windows-latest)",
            "No Godot source or link dependencies (macos-26)",
        })
    if max_level >= 3:
        mandatory_ci.add("🏁 Windows / Editor (target=editor)")

    return {
        "schema_version": 1,
        "tier": tier,
        "tier_level": max_level,
        "changed_count": len(normalized),
        "boundaries": dict(sorted(boundaries.items())),
        "tier_triggers": {k: v for k, v in trigger_paths.items() if v},
        "yanluo_requirements": {
            "formal_issue_gate": True,
            "diting_committed_check": True,
            "independent_review_required": max_level >= 1,
            "review_scope": "changed_paths_and_bound_criteria_only",
            "governance_admission_required": max_level == 4,
            "module_impact_check_required": max_level == 4,
            "scoped_engine_ci_required": max_level == 2,
            "full_windows_editor_ci_required": max_level >= 3,
            "allow_slice_delivery_keep_issue_open": True,
            "zero_overlap_main_drift_policy": (
                "merge_or_rebind_without_full_rebuild"
                if max_level <= 2
                else "merge_if_disjoint_and_ci_green_else_reverify"
            ),
            "mandatory_ci_checks": sorted(mandatory_ci),
        },
    }


def _check_sort_key(entry: Mapping[str, Any], index: int) -> tuple[int, str, int]:
    run_id = entry.get("id")
    numeric_id = run_id if type(run_id) is int else -1
    timestamp = str(
        entry.get("completedAt") or entry.get("completed_at") or entry.get("startedAt") or entry.get("started_at") or ""
    )
    return (numeric_id, timestamp, index)


def deduplicate_check_runs(checks: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate StatusContext / CheckRun entries by ``(workflow, name)`` keeping the latest run."""
    selected: dict[tuple[str, str], tuple[tuple[int, str, int], dict[str, Any]]] = {}
    for index, check in enumerate(checks):
        typename = check.get("__typename")
        if typename == "StatusContext" or ("context" in check and "name" not in check):
            name = str(check.get("context") or "")
            workflow = "status_context"
            raw_state = str(check.get("state") or "").upper()
            completed = raw_state in {"SUCCESS", "FAILURE", "ERROR"}
            conclusion = "SUCCESS" if raw_state == "SUCCESS" else raw_state or "PENDING"
        else:
            name = str(check.get("name") or "")
            workflow = str(check.get("workflowName") or check.get("app", {}).get("slug") or "")
            status = str(check.get("status") or "").upper()
            completed = status == "COMPLETED"
            conclusion = str(check.get("conclusion") or "").upper() if completed else (status or "PENDING")
        normalized = {
            "name": name[:256],
            "workflow": workflow[:256],
            "completed": completed,
            "state": conclusion,
        }
        key = (workflow, name)
        rank = _check_sort_key(check, index)
        if key not in selected or rank >= selected[key][0]:
            selected[key] = (rank, normalized)
    return [item[1] for item in selected.values()]


def verify_ci_rollup(
    checks: Sequence[Mapping[str, Any]],
    *,
    audit_profile: Mapping[str, Any] | None = None,
) -> list[dict[str, str]]:
    """Verify deduplicated CI checks and optional tier-mandatory check outcomes."""
    if not isinstance(checks, Sequence) or not checks:
        raise ValueError("CI readback is missing")
    deduped = deduplicate_check_runs(checks)
    by_name: dict[str, list[dict[str, Any]]] = {}
    summary: list[dict[str, str]] = []
    for item in deduped:
        if not item["completed"] or item["state"] not in {"SUCCESS", "SKIPPED"}:
            raise ValueError(f"CI is pending or failed: {item['name']} ({item['state']})")
        by_name.setdefault(item["name"], []).append(item)
        summary.append({"name": item["name"], "state": item["state"]})

    if audit_profile is not None:
        mandatory = audit_profile.get("yanluo_requirements", {}).get("mandatory_ci_checks", ())
        for required_name in mandatory:
            observed = by_name.get(required_name, [])
            if observed and not any(entry["state"] == "SUCCESS" for entry in observed):
                raise ValueError(f"Mandatory tier CI check was skipped instead of executed: {required_name}")
    return summary


def normalize_issue_scope(body: str | None) -> str:
    """Extract canonical requirement body below ephemeral Yanluo/Kuafu coordination headers."""
    text = (body or "").replace("\r\n", "\n")
    marker = re.search(r"<!--\s*(?:gonggong|olympus)-request:[a-z0-9]+(?:-[a-z0-9]+)*\s*-->", text)
    if marker:
        text = text[marker.start() :]
    text = re.sub(r"\n*<!--\s*gonggong-host-git:[A-Za-z0-9-]+\s*-->\s*$", "", text)
    return text.strip()


def scope_digest(body: str | None, *, normalized: bool = False) -> str:
    raw = normalize_issue_scope(body) if normalized else (body or "")
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def scope_digest_matches(body: str | None, expected_digest: str) -> bool:
    return expected_digest in {
        scope_digest(body, normalized=False),
        scope_digest(body, normalized=True),
    }


def summarize_ci_state(checks: Sequence[Mapping[str, Any]]) -> str:
    if not checks:
        return "PENDING"
    deduped = deduplicate_check_runs(checks)
    if any(item["completed"] and item["state"] not in {"SUCCESS", "SKIPPED"} for item in deduped):
        return "FAILED"
    if any(not item["completed"] for item in deduped):
        return "PENDING"
    return "SUCCESS"


def plan_submission_queue(
    submissions: Sequence[Mapping[str, Any]],
    main_sha: str,
) -> dict[str, Any]:
    """Coordinate multi-account open signed PRs into superseded sets and conflict-free merge waves."""
    grouped: dict[tuple[str, int, str], list[dict[str, Any]]] = {}
    items = [dict(entry) for entry in submissions]
    for item in items:
        key = (str(item["writer"]).lower(), int(item["issue"]), str(item["request_id"]))
        grouped.setdefault(key, []).append(item)

    superseded_map: dict[int, int] = {}
    for group in grouped.values():
        if len(group) <= 1:
            continue
        ordered = sorted(group, key=lambda x: (str(x.get("updated_at") or ""), int(x["number"])), reverse=True)
        newest = int(ordered[0]["number"])
        for older in ordered[1:]:
            superseded_map[int(older["number"])] = newest

    active: list[dict[str, Any]] = []
    decorated: list[dict[str, Any]] = []
    for item in sorted(items, key=lambda x: int(x["number"])):
        number = int(item["number"])
        writes = sorted(set(item.get("write_paths") or ()))
        upstream_overlap = sorted(set(item.get("overlapping_write_paths") or ()))
        ci_state = str(item.get("ci_state") or "PENDING")
        mergeable = str(item.get("mergeable") or "UNKNOWN")
        superseded_by = superseded_map.get(number)

        if superseded_by is not None:
            queue_state = "superseded_duplicate"
        elif upstream_overlap or mergeable == "CONFLICTING":
            queue_state = "conflict_requires_heqi"
        elif ci_state == "FAILED":
            queue_state = "ci_failed"
        elif ci_state != "SUCCESS":
            queue_state = "waiting_ci"
        elif item.get("base") != main_sha and mergeable not in {"MERGEABLE", "UNKNOWN"}:
            queue_state = "needs_rebind"
        else:
            queue_state = "ready_to_merge"

        record = {
            **item,
            "write_paths": writes,
            "overlapping_write_paths": upstream_overlap,
            "ci_state": ci_state,
            "queue_state": queue_state,
            "superseded_by": superseded_by,
        }
        decorated.append(record)
        if queue_state in {"ready_to_merge", "waiting_ci", "needs_rebind"}:
            active.append(record)

    pairwise_conflicts: list[dict[str, Any]] = []
    conflict_pairs: set[frozenset[int]] = set()
    for idx, left in enumerate(active):
        for right in active[idx + 1 :]:
            shared = path_overlap(left["write_paths"], right["write_paths"])
            if shared:
                left_num, right_num = int(left["number"]), int(right["number"])
                conflict_pairs.add(frozenset((left_num, right_num)))
                pairwise_conflicts.append({
                    "left_pr": left_num,
                    "left_writer": left["writer"],
                    "right_pr": right_num,
                    "right_writer": right["writer"],
                    "paths": shared,
                })

    # Prioritize ready_to_merge PRs first, then smallest diff footprint, then PR number.
    remaining = sorted(
        active,
        key=lambda x: (0 if x["queue_state"] == "ready_to_merge" else 1, len(x["write_paths"]), int(x["number"])),
    )
    waves: list[list[int]] = []
    while remaining:
        wave: list[int] = []
        next_remaining: list[dict[str, Any]] = []
        for candidate in remaining:
            num = int(candidate["number"])
            if all(frozenset((num, chosen)) not in conflict_pairs for chosen in wave):
                wave.append(num)
            else:
                next_remaining.append(candidate)
        waves.append(wave)
        remaining = next_remaining

    accounts = sorted({str(x["writer"]) for x in decorated})
    return {
        "schema_version": 1,
        "main_sha": main_sha,
        "total_open_signed_prs": len(decorated),
        "accounts": accounts,
        "ready_to_merge": [int(x["number"]) for x in decorated if x["queue_state"] == "ready_to_merge"],
        "superseded_prs": [
            {"pr": int(x["number"]), "writer": x["writer"], "issue": x["issue"], "superseded_by": x["superseded_by"]}
            for x in decorated
            if x["superseded_by"] is not None
        ],
        "pairwise_conflicts": pairwise_conflicts,
        "merge_waves": waves,
        "submissions": decorated,
    }
