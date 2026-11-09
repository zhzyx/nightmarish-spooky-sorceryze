"""Measure Godot host steps from one work order's recorded events, without a model login."""

import argparse
import hashlib
import json
import re
from pathlib import Path


def timings(directory):
    starts = {}
    ends = []
    for path in sorted(directory.glob("godot-event-*.json")):
        event = json.loads(path.read_bytes())
        if event.get("kind") != "step":
            continue
        event_id = event["event_id"]
        match = re.fullmatch(r"godot-event-(\d+)-(\d+)", event_id)
        if match is None or path.stem != event_id:
            raise ValueError(f"Invalid Godot event identity in {path.name}")
        checksum = event.pop("sha256")
        body = json.dumps(event, ensure_ascii=False, separators=(",", ":"), sort_keys=True, allow_nan=False)
        if hashlib.sha256(body.encode()).hexdigest() != checksum:
            raise ValueError(f"Receipt checksum mismatch in {path.name}")
        payload = event["payload"]
        key = (event["tenant_id"], event["request_id"], event["source_ref"], match[1], payload["phase"])
        tick = int(match[2])
        if payload["status"] == "running":
            if event_id in starts:
                raise ValueError(f"Duplicate start in {path.name}")
            starts[event_id] = (key, tick)
        elif "supersedes" in event:
            ends.append((event["supersedes"], key, tick, payload["status"]))

    steps = []
    unmatched_ends = 0
    for parent, key, tick, status in ends:
        start = starts.get(parent)
        if start is None or start[0] != key or tick < start[1]:
            unmatched_ends += 1
            continue
        del starts[parent]
        steps.append({"start": parent, "phase": key[-1], "status": status, "elapsed_ms": (tick - start[1]) / 1000})
    return {"steps": steps, "unmatched_starts": len(starts), "unmatched_ends": unmatched_ends}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, help="events/<tenant>/<request> directory")
    folder = parser.parse_args().directory
    if not folder.is_dir():
        parser.error("Work order event directory does not exist")
    print(json.dumps(timings(folder), ensure_ascii=False, indent=2))
