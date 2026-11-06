"""Check the registered GongGong snapshot offline without executing framework code.

This is byte integrity and recorded-evidence consistency, not live upstream
verification, authenticated approval, or permission to execute an Agent.
The registration file must be independently reviewed when the snapshot changes.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any

DITING_EXTENSION = "extensions/diting-files/"
PLATFORM_PACKAGES = (
    "customizations/platforms/data-collection/git-files/storage",
    "customizations/platforms/development/git/delivery",
)
REGISTRATION = "integrations/gonggong/frozen-distribution.json"
SCOPE = "offline_registered_snapshot_consistency_only"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def safe_name(value: Any) -> str:
    require(isinstance(value, str) and bool(value), "Expected a nonempty relative path")
    require(not any(c in value for c in "\\:\x00"), f"Unsafe path: {value!r}")
    parts = value.split("/")
    require(all(p and p not in (".", "..") and p == p.rstrip(" .") for p in parts), f"Unsafe path: {value!r}")
    require(not PurePosixPath(value).is_absolute(), f"Absolute path: {value!r}")
    return str(value)


def no_link(path: Path) -> None:
    info = path.lstat()
    require(not stat.S_ISLNK(info.st_mode), f"Linked path: {path}")
    require(not getattr(info, "st_file_attributes", 0) & 0x400, f"Reparse point: {path}")


def inventory(root: Path) -> dict[str, bytes]:
    no_link(root)
    require(root.is_dir(), "Framework directory missing")
    result: dict[str, bytes] = {}
    names: set[str] = set()

    def walk(folder: Path) -> None:
        for path in sorted(folder.iterdir()):
            if path.name == "__pycache__" or path.suffix == ".pyc":
                continue
            name = safe_name(path.relative_to(root).as_posix())
            require(name.casefold() not in names, f"Case-colliding path: {name}")
            names.add(name.casefold())
            no_link(path)
            if path.is_dir():
                walk(path)
            else:
                require(stat.S_ISREG(path.stat().st_mode), f"Nonregular file: {name}")
                result[name] = path.read_bytes()

    walk(root)
    return result


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def invalid_constant(value: str) -> None:
    raise ValueError(f"Nonfinite JSON value: {value}")


def parse_json(raw: bytes) -> Any:
    return json.loads(raw.decode("utf-8"), object_pairs_hook=unique_object, parse_constant=invalid_constant)


def candidate_checks(files: dict[str, bytes], require_admission=True) -> None:
    manifest = parse_json(files["framework-manifest.json"])
    agents = manifest["agents"]
    require(isinstance(agents, list) and bool(agents), "Empty Agent set")
    ids = [agent["id"] for agent in agents]
    require(
        all(isinstance(agent_id, str) and agent_id for agent_id in ids) and len(ids) == len(set(ids)),
        "Invalid Agent set",
    )
    for agent in agents:
        paths = agent["candidate_files"]
        require(isinstance(paths, list) and paths == sorted(set(paths)) and bool(paths), "Invalid candidate file list")
        records = []
        for value in paths:
            path = safe_name(value)
            require(path in files, f"Missing candidate file: {path}")
            records.append({"path": path, "sha256": digest(files[path])})
        candidate = digest("".join(r["path"] + "\0" + r["sha256"] + "\n" for r in records).encode())
        require(candidate == agent["candidate_digest"], f"Candidate digest mismatch: {agent['id']}")
        if not require_admission:
            continue
        permit_path = safe_name(agent["admission_pass"])
        require(permit_path in files, f"Missing pinned permit: {permit_path}")
        permit = parse_json(files[permit_path])
        require(permit["template"] is False and permit["status"] == "approved", "Recorded permit is not approved")
        subject = permit["subject"]
        require(subject["id"] == agent["id"], "Permit subject mismatch")
        require(
            subject["version_or_digest"]
            == {"version": agent["version"], "candidate_digest": candidate, "candidate_files": records},
            "Permit candidate/version/files mismatch",
        )
        review = permit["review"]
        approval = permit["approval"]
        require(bool(review["evaluator_id"]) and bool(review["independence"]), "Missing recorded review identity")
        require(
            bool(approval["approver_id"]) and bool(approval["authority_ref"]), "Missing recorded approval reference"
        )
        refs = review["evidence_refs"]
        require(isinstance(refs, list) and bool(refs), "Missing review evidence references")
        for value in [*refs, approval["decision_evidence_ref"]]:
            path = safe_name(value)
            require(path in files and bool(files[path]), f"Missing pinned evidence: {path}")


def platform_inventory(root, directory, expected):
    folder = root
    for component in directory.split("/"):
        folder = folder / component
        no_link(folder)
    actual = inventory(folder)
    require(
        {name: digest(raw) for name, raw in actual.items()} == expected,
        "Platform file set or digest mismatch: " + directory,
    )
    return actual


def check(root: Path, node: str | None = None, candidate=False) -> dict[str, Any]:
    root = root.absolute()
    # Check every ancestor before resolution: resolve() alone would hide junctions.
    for parent in [*reversed(root.parents), root]:
        no_link(parent)
    registration = root / REGISTRATION
    for parent in [registration.parent.parent, registration.parent, registration]:
        no_link(parent)
    lock = parse_json(registration.read_bytes())
    require(lock["schema_version"] in (1, 2) and lock["scope"] == SCOPE, "Unexpected registration format")
    require(lock["exemption"] is None, "Unexpected exemption")
    expected = lock["files"]
    require(isinstance(expected, dict) and bool(expected), "Empty file registration")
    folded: set[str] = set()
    for name, sha in expected.items():
        safe_name(name)
        require(name.casefold() not in folded, "Case-colliding registered path")
        folded.add(name.casefold())
        require(isinstance(sha, str) and re.fullmatch(r"[0-9a-f]{64}", sha) is not None, "Invalid file digest")
    files = inventory(root / "framework")
    frozen = files
    require(
        set(frozen) == set(expected),
        f"File set mismatch; missing={sorted(set(expected) - set(frozen))}, extra={sorted(set(frozen) - set(expected))}",
    )
    for name, data in frozen.items():
        require(digest(data) == expected[name], f"Frozen byte mismatch: {name}")
    candidate_checks(files, require_admission=not candidate)
    syntax_files = {"framework/" + name: raw for name, raw in files.items()}
    if lock["schema_version"] == 1:
        require(
            {DITING_EXTENSION + name for name in ("README.md", "diting_files.py", "event.schema.json")} <= files.keys(),
            "Pinned Diting extension missing",
        )
    else:
        packages = lock["platform_files"]
        require(set(packages) == set(PLATFORM_PACKAGES), "Missing platform package registration")
        for directory in PLATFORM_PACKAGES:
            actual = platform_inventory(root, directory, packages[directory])
            syntax_files.update({directory + "/" + name: raw for name, raw in actual.items()})
        require(
            PLATFORM_PACKAGES[0] + "/diting_files.py" in syntax_files
            and PLATFORM_PACKAGES[0] + "/event.schema.json" in syntax_files
            and PLATFORM_PACKAGES[1] + "/check_delivery.py" in syntax_files,
            "Missing registered platform entry",
        )
    node_path = node or shutil.which("node")
    if not node_path:
        bundled = root / "project/runtime/node/node.exe"
        node_path = str(bundled) if bundled.is_file() else None
    environment = {k: v for k, v in os.environ.items() if k.upper() not in {"NODE_OPTIONS", "NODE_PATH"}}
    checked = {"python": 0, "javascript": 0, "json": 0}
    for name, raw in syntax_files.items():
        suffix = PurePosixPath(name).suffix
        if suffix == ".py":
            # Compile in memory; never import, execute or write bytecode.
            compile(raw, name, "exec", dont_inherit=True)
            checked["python"] += 1
        elif suffix == ".json":
            parse_json(raw)
            checked["json"] += 1
        elif suffix in (".js", ".mjs", ".cjs"):
            require(bool(node_path), "Node is required for JavaScript syntax checks")
            result = subprocess.run(
                [str(node_path), "--check", str(root / name)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=environment,
                timeout=30,
            )
            require(result.returncode == 0, f"JavaScript syntax error: {name}: {result.stderr.strip()}")
            checked["javascript"] += 1
    return {
        "ok": True,
        "scope": SCOPE,
        "frozen_files": len(frozen),
        "syntax": checked,
        "diting_extension_syntax_checked": True,
        "live_upstream_verified": False,
        "authority_authenticated": False,
        "agent_execution_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--candidate", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(check(args.repo, candidate=args.candidate), sort_keys=True))
    except (ValueError, OSError, KeyError, TypeError, SyntaxError, subprocess.TimeoutExpired) as error:
        parser.exit(1, f"GongGong offline snapshot check failed: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
