"""Publish a compatibility copy only after its exclusive report is durable."""

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

from interop_publish import publish


def publish_pair(staged: str, report_path: str, target_path: str) -> dict[str, object]:
    target = Path(target_path)
    artifact_bytes = Path(staged).read_bytes()
    report_target = Path(str(target) + ".report.json")
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    if not isinstance(report, dict) or report.get("schema_version") != 1:
        raise ValueError("A versioned compatibility report is required")
    if report.get("scope") != "body_skin_and_final_body_animation":
        raise ValueError("Unsupported compatibility scope")
    report["artifact_sha256"] = hashlib.sha256(artifact_bytes).hexdigest()
    if target.exists() or report_target.exists():
        raise FileExistsError("Choose a new compatibility copy and report")
    payload = json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8")
    descriptor, temporary_name = tempfile.mkstemp(prefix=".character-report-", dir=target.parent)
    temporary = Path(temporary_name)
    linked = False
    published = False
    snapshot: Path | None = None
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, report_target)
        linked = True
        snapshot_descriptor, snapshot_name = tempfile.mkstemp(prefix=".character-snapshot-", dir=target.parent)
        snapshot = Path(snapshot_name)
        with os.fdopen(snapshot_descriptor, "wb") as stream:
            stream.write(artifact_bytes)
            stream.flush()
            os.fsync(stream.fileno())
        # The caller's stage is never read again. Validation and publication
        # consume this private byte snapshot, whose digest is in the report.
        artifact = publish(snapshot, target)
        published = True
        return {"artifact": artifact, "report_sha256": hashlib.sha256(payload).hexdigest()}
    finally:
        if linked and not published and report_target.exists():
            # Remove only our hard link, never a concurrently replaced report.
            if os.path.samestat(temporary.stat(), report_target.stat()):
                report_target.unlink()
        temporary.unlink(missing_ok=True)
        if snapshot is not None:
            snapshot.unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        print(json.dumps(publish_pair(*sys.argv[1:])))
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
