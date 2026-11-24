#!/usr/bin/env python3
"""Recompute full-session frame statistics with disk-backed, bounded-cache storage."""

import argparse
import csv
import hashlib
import json
import math
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

MAX_LINE_BYTES = 1024 * 1024
MAX_GRAPH_PASSES = 1024
DEFAULT_PASS_GROUPS = 4096


def number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
        raise ValueError("Timing samples must be finite and nonnegative")
    return value


def integer(value):
    if isinstance(value, bool) or str(value) != str(int(value)) or not 0 <= int(value) <= (1 << 63) - 1:
        raise ValueError("Expected a nonnegative signed-64-bit counter")
    return int(value)


def statistics(connection, column, table="measured"):
    count, total, maximum, over16, over33 = connection.execute(
        f"SELECT COUNT({column}), SUM({column}), MAX({column}), "
        f"SUM({column}>16.666666666666668), SUM({column}>33.333333333333336) FROM {table}"
    ).fetchone()
    if count == 0:
        return {"samples": 0}
    worst = max(1, (count + 99) // 100)
    slow_mean = connection.execute(
        f"SELECT AVG(v) FROM (SELECT {column} AS v FROM {table} WHERE {column} IS NOT NULL ORDER BY v DESC LIMIT ?)",
        (worst,),
    ).fetchone()[0]
    result = {
        "samples": count,
        "mean_msec": total / count,
        "max_msec": maximum,
        "slowest_one_percent_samples": worst,
        "slowest_one_percent_mean_msec": slow_mean,
        "one_percent_low_fps": 1000 / slow_mean if slow_mean else None,
        "over_16_67_msec": over16 or 0,
        "over_33_33_msec": over33 or 0,
    }
    for key, percentage in (("p95_msec", 95), ("p99_msec", 99)):
        result[key] = connection.execute(
            f"SELECT {column} FROM {table} WHERE {column} IS NOT NULL ORDER BY {column} LIMIT 1 OFFSET ?",
            (max(0, (percentage * count + 99) // 100 - 1),),
        ).fetchone()[0]
    return result


def analyze(
    path,
    *,
    first_frame=0,
    last_frame=None,
    allow_partial=False,
    series_path=None,
    working_directory=None,
    max_pass_groups=DEFAULT_PASS_GROUPS,
):
    if series_path is not None and Path(path).resolve() == Path(series_path).resolve():
        raise ValueError("The resource series cannot replace its source trace")
    max_pass_groups = integer(max_pass_groups)
    if not 1 <= max_pass_groups <= 65536:
        raise ValueError("Pass-group summary budget must be in [1,65536]")
    first_frame = integer(first_frame)
    if last_frame is not None:
        last_frame = integer(last_frame)
        if last_frame < first_frame:
            raise ValueError("The selected frame interval is reversed")
    with tempfile.TemporaryDirectory(prefix="frame-telemetry-", dir=working_directory) as temp:
        with closing(sqlite3.connect(str(Path(temp) / "samples.sqlite"))) as connection:
            connection.execute("PRAGMA cache_size=-8192")
            connection.execute("PRAGMA temp_store=FILE")
            connection.execute("PRAGMA journal_mode=OFF")
            connection.execute(
                "CREATE TABLE frames(id INTEGER PRIMARY KEY, begin_qpc INTEGER, qpc INTEGER, cpu REAL, gpu REAL, compute REAL, present REAL, fence REAL, prepare REAL, recording REAL, upload_bytes INTEGER, page_read_bytes INTEGER, usage INTEGER, budget INTEGER, private_bytes INTEGER, working_set INTEGER, handles INTEGER, graph_resources INTEGER, descriptors INTEGER, pages INTEGER, evictions INTEGER, stalls INTEGER, retirement REAL, animation_upload REAL, page_prepare REAL, input_api_latency REAL, input_receipts INTEGER)"
            )
            connection.execute(
                "CREATE TABLE passes(frame INTEGER, epoch INTEGER, pass INTEGER, milliseconds REAL, PRIMARY KEY(frame,pass))"
            )
            header = footer = None
            connection.execute("CREATE TABLE graphs(epoch INTEGER PRIMARY KEY)")
            count = 0
            digest = hashlib.sha256()
            with Path(path).open("rb") as stream:
                while line := stream.readline(MAX_LINE_BYTES + 1):
                    if len(line) > MAX_LINE_BYTES or not line.endswith(b"\n"):
                        raise ValueError("Oversized or truncated JSONL record")
                    digest.update(line)
                    value = json.loads(line)
                    kind = value.get("record")
                    if header is None:
                        if kind != "header" or value.get("schema_version") != 1:
                            raise ValueError("Missing supported telemetry header")
                        header = value
                        frequency = integer(value["qpc_frequency"])
                        if frequency == 0:
                            raise ValueError("QPC frequency must be positive")
                        continue
                    if footer is not None:
                        raise ValueError("Data after telemetry footer")
                    if kind == "graph":
                        if len(value.get("passes", [])) > MAX_GRAPH_PASSES:
                            raise ValueError("Graph exceeds the renderer pass bound")
                        connection.execute("INSERT INTO graphs VALUES (?)", (integer(value["graph_epoch"]),))
                        continue
                    if kind == "footer":
                        if type(value.get("complete")) is not bool:
                            raise ValueError("Footer completion must be boolean")
                        footer = value
                        continue
                    if (
                        kind != "frame"
                        or integer(value["record_id"]) != count
                        or connection.execute(
                            "SELECT 1 FROM graphs WHERE epoch=?", (integer(value["graph_epoch"]),)
                        ).fetchone()
                        is None
                    ):
                        raise ValueError("Invalid record order or unknown graph epoch")
                    frame = integer(value["frame_id"])
                    begin = integer(value["frame_begin_qpc"])
                    present = integer(value["present_end_qpc"])
                    if begin == 0 or present < begin:
                        raise ValueError("Invalid CPU observation interval")
                    memory_ready = value.get("memory_ready", False)
                    process_ready = value.get("process_ready", False)
                    if any(type(flag) is not bool for flag in (memory_ready, process_ready, value.get("gpu_ready"))):
                        raise ValueError("Readiness flags must be boolean")
                    row = [frame, begin, present, number(value["cpu_frame_msec"])]
                    row += [
                        number(value[field]) if value.get("gpu_ready") else None
                        for field in ("graphics_msec", "compute_msec")
                    ]
                    row += [
                        number(value[field])
                        for field in ("present_msec", "fence_wait_msec", "prepare_msec", "record_submit_msec")
                    ]
                    row += [integer(value[field]) for field in ("upload_copy_bytes", "synchronous_page_read_bytes")]
                    row += [
                        integer(value[field]) if memory_ready else None
                        for field in ("dedicated_usage_bytes", "dedicated_budget_bytes")
                    ]
                    row += [
                        integer(value[field]) if process_ready else None
                        for field in ("process_private_bytes", "process_working_set_bytes", "process_handles")
                    ]
                    row += [
                        integer(value[field])
                        for field in (
                            "graph_resources",
                            "descriptor_capacity",
                            "allocated_mesh_pages",
                            "page_evictions",
                            "page_stalls",
                        )
                    ]
                    row += [
                        number(value[field])
                        for field in ("retirement_readback_msec", "animation_upload_msec", "page_prepare_msec")
                    ]
                    receipts = integer(value["input_receipts_since_previous_frame"])
                    latency = None
                    if value["new_input"]:
                        received = integer(value["input_received_qpc"])
                        consumed = integer(value["input_observed_qpc"])
                        if (
                            integer(value["input_revision"]) == 0
                            or receipts == 0
                            or not 0 < received <= consumed <= present
                        ):
                            raise ValueError("Invalid input receipt/consumption/Present timestamps")
                        latency = (present - received) * 1000.0 / frequency
                    row += [latency, receipts]
                    connection.execute("INSERT INTO frames VALUES (" + ",".join("?" for _ in row) + ")", row)
                    if len(value.get("passes", [])) > MAX_GRAPH_PASSES:
                        raise ValueError("Unbounded pass list")
                    for item in value.get("passes", []):
                        duration = number(item["gpu_msec"]) if value.get("gpu_ready") else None
                        connection.execute(
                            "INSERT INTO passes VALUES (?,?,?,?)",
                            (frame, integer(value["graph_epoch"]), integer(item["pass_id"]), duration),
                        )
                    count += 1
                    if count % 1024 == 0:
                        connection.commit()
            if header is None:
                raise ValueError("Empty telemetry input")
            complete = bool(
                footer
                and footer.get("complete")
                and integer(footer["frames"]) == count
                and integer(footer["expected_frames"]) == count
            )
            bounds = connection.execute("SELECT MIN(id), MAX(id) FROM frames").fetchone()
            complete = complete and (count == 0 or bounds == (0, count - 1))
            if not complete and not allow_partial:
                raise ValueError("Missing/incomplete footer or missing frame IDs")
            end = last_frame if last_frame is not None else (bounds[1] or 0)
            connection.execute(
                f"CREATE TEMP VIEW measured AS SELECT *, (qpc-LAG(qpc) OVER (ORDER BY id))*1000.0/{frequency} AS interval FROM frames WHERE id BETWEEN {first_frame} AND {end}"
            )
            selected, begin, end_qpc = connection.execute(
                "SELECT COUNT(*), MIN(begin_qpc), MAX(qpc) FROM measured"
            ).fetchone()
            if selected == 0:
                raise ValueError("No frames in the selected interval")
            if connection.execute("SELECT COUNT(*) FROM measured WHERE interval<0").fetchone()[0]:
                raise ValueError("Present observations do not follow frame order")
            wall_seconds = (end_qpc - begin) / frequency
            result = {
                "schema_version": 1,
                "complete": complete,
                "recorded_frames": count,
                "selected_frames": selected,
                "input_sha256": digest.hexdigest(),
                "first_frame": first_frame,
                "last_frame": end,
                "observed_seconds": wall_seconds,
                "average_fps": selected / wall_seconds if wall_seconds else None,
                "scope": "Frame/Present-return CPU observations. Input API latency uses the latest newly consumed keyboard/mouse receipt revision, which may coalesce older receipts; it is not pixel response, authoritative network tick or scanout latency. GPU timestamps are queue intervals.",
                "header": header,
                "timings": {
                    key: statistics(connection, column)
                    for key, column in (
                        ("present_interval", "interval"),
                        ("cpu", "cpu"),
                        ("graphics", "gpu"),
                        ("compute", "compute"),
                        ("present_call", "present"),
                        ("fence_wait", "fence"),
                        ("prepare", "prepare"),
                        ("record_submit", "recording"),
                        ("retirement_readback", "retirement"),
                        ("animation_upload", "animation_upload"),
                        ("page_prepare", "page_prepare"),
                        ("input_receipt_to_present_api", "input_api_latency"),
                    )
                },
            }
            result["passes"] = {}
            group_query = f"SELECT DISTINCT epoch,pass FROM passes WHERE frame BETWEEN {first_frame} AND {end}"
            group_count = connection.execute("SELECT COUNT(*) FROM (" + group_query + ")").fetchone()[0]
            if group_count > max_pass_groups:
                raise ValueError(
                    "Pass-group summary budget exceeded; choose a frame interval or increase the explicit budget"
                )
            for epoch, pass_id in connection.execute(group_query + " ORDER BY epoch,pass"):
                connection.execute(
                    f"CREATE TEMP VIEW selected_pass AS SELECT milliseconds FROM passes WHERE epoch={epoch} AND pass={pass_id} AND frame BETWEEN {first_frame} AND {end}"
                )
                result["passes"][f"{epoch}:{pass_id}"] = statistics(connection, "milliseconds", "selected_pass")
                connection.execute("DROP VIEW selected_pass")
            result["resources"] = {}
            for column in (
                "usage",
                "budget",
                "private_bytes",
                "working_set",
                "handles",
                "graph_resources",
                "descriptors",
                "pages",
                "evictions",
                "stalls",
            ):
                low, high, first, last = connection.execute(
                    f"SELECT MIN({column}),MAX({column}),(SELECT {column} FROM measured WHERE {column} IS NOT NULL ORDER BY id LIMIT 1),(SELECT {column} FROM measured WHERE {column} IS NOT NULL ORDER BY id DESC LIMIT 1) FROM measured"
                ).fetchone()
                result["resources"][column] = {
                    "minimum": low,
                    "maximum": high,
                    "first": first,
                    "last": last,
                    "delta": last - first if first is not None and last is not None else None,
                }
            if series_path is not None:
                cursor = connection.execute(
                    "SELECT id,(qpc-?)*1.0/?,usage,budget,private_bytes,working_set,handles,graph_resources,descriptors,pages,evictions,stalls,upload_bytes,page_read_bytes FROM measured ORDER BY id",
                    (begin, frequency),
                )
                with Path(series_path).open("w", newline="", encoding="utf-8") as stream:
                    writer = csv.writer(stream)
                    writer.writerow([item[0] for item in cursor.description])
                    writer.writerows(cursor)
            return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--series", type=Path)
    parser.add_argument("--working-directory", type=Path)
    parser.add_argument("--first-frame", type=int, default=0)
    parser.add_argument("--last-frame", type=int)
    parser.add_argument("--allow-partial", action="store_true")
    parser.add_argument("--max-pass-groups", type=int, default=DEFAULT_PASS_GROUPS)
    args = parser.parse_args()
    if args.output.resolve() == args.input.resolve() or (
        args.series and args.output.resolve() == args.series.resolve()
    ):
        parser.error("Telemetry source, summary, and resource series must be separate files")
    try:
        result = analyze(
            args.input,
            first_frame=args.first_frame,
            last_frame=args.last_frame,
            allow_partial=args.allow_partial,
            series_path=args.series,
            working_directory=args.working_directory,
            max_pass_groups=args.max_pass_groups,
        )
    except (ValueError, OSError, sqlite3.Error, KeyError, TypeError, OverflowError) as error:
        parser.exit(1, str(error) + "\n")
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
