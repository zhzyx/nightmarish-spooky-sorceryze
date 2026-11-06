"""Seal current candidate bytes. Never grants admission or changes a permit."""

import hashlib
import json
import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    root = ROOT / "framework"
    manifest = json.loads((root / "framework-manifest.json").read_text(encoding="utf-8"))
    # Refuse before any write: this tool prepares isolated pending candidates only.
    for agent in manifest["agents"]:
        permit = json.loads((root / agent["admission_pass"]).read_text(encoding="utf-8"))
        if permit.get("status") == "approved":
            raise ValueError("Use a new isolated pending candidate; approved releases cannot be resealed")
    for record in [*manifest["agents"], *manifest["skills"], manifest["upstream_skill_reporting"]]:
        profile_path = root / record["reporting"]
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        profile["component"]["entry_sha256"] = hashlib.sha256(
            (root / profile["component"]["entry"]).read_bytes()
        ).hexdigest()
        for dep in profile["dependencies"]:
            profile["dependencies"][dep] = hashlib.sha256((root / dep).read_bytes()).hexdigest()
        write(profile_path, profile)
    fp = runpy.run_path(str(root / "tools/verify_framework.py"))["fingerprint"]
    for a in manifest["agents"]:
        digest, _ = fp(root, a["candidate_files"])
        permit = json.loads((root / a["admission_pass"]).read_text(encoding="utf-8"))
        if permit.get("status") == "approved" and digest != a["candidate_digest"]:
            raise ValueError("Approved candidate changed; create a new pending candidate first")
        a["candidate_digest"] = digest
        if permit.get("status") != "approved":
            _, records = fp(root, a["candidate_files"])
            permit["subject"]["version_or_digest"] = {
                "version": a["version"],
                "candidate_digest": digest,
                "candidate_files": records,
            }
            write(root / a["admission_pass"], permit)
    write(root / "framework-manifest.json", manifest)
    inventory = runpy.run_path(str(root / "tools/package_integrity.py"))["inventory"](root)
    write(root / "package-lock.json", {"schema_version": 1, "path_base": "framework_root", "files": inventory})
    files = {**inventory, "package-lock.json": hashlib.sha256((root / "package-lock.json").read_bytes()).hexdigest()}
    registration = ROOT / "integrations/gonggong/frozen-distribution.json"
    snapshot = json.loads(registration.read_text(encoding="utf-8"))
    snapshot["files"] = files
    # Host platform byte registrations have a separate review boundary.
    write(registration, snapshot)
    print(json.dumps({a["id"]: a["candidate_digest"] for a in manifest["agents"]}))


if __name__ == "__main__":
    main()
