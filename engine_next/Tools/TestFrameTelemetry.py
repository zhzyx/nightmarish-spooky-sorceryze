"""Tests of the real streaming analyzer and its exact statistics contract."""

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import AnalyzeFrameTelemetry as telemetry


def frame(index):
    return {
        "record": "frame",
        "record_id": str(index),
        "frame_id": index,
        "graph_epoch": "1",
        "frame_begin_qpc": str(1000 + index * 10),
        "present_end_qpc": str(1010 + index * 10),
        "cpu_frame_msec": index + 1,
        "gpu_ready": True,
        "graphics_msec": (index + 1) / 2,
        "compute_msec": 0.5,
        "present_msec": 1,
        "retirement_readback_msec": 0.1,
        "animation_upload_msec": 0.2,
        "page_prepare_msec": 0.3,
        "new_input": False,
        "input_receipts_since_previous_frame": "0",
        "input_revision": "0",
        "input_received_qpc": "0",
        "input_observed_qpc": "0",
        "fence_wait_msec": 2,
        "prepare_msec": 3,
        "record_submit_msec": 4,
        "upload_copy_bytes": "60",
        "synchronous_page_read_bytes": "52",
        "memory_ready": True,
        "process_ready": True,
        "dedicated_usage_bytes": str(100 + index),
        "dedicated_budget_bytes": "200",
        "process_private_bytes": str(300 + index),
        "process_working_set_bytes": "400",
        "process_handles": "10",
        "graph_resources": "30",
        "descriptor_capacity": "232",
        "allocated_mesh_pages": "8",
        "page_evictions": "0",
        "page_stalls": "0",
        "passes": [{"pass_id": 7, "gpu_msec": index + 1}],
    }


class FrameTelemetryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.path = self.root / "frames.jsonl"

    def write(self, samples, complete=True):
        rows = [
            {"record": "header", "schema_version": 1, "qpc_frequency": "1000"},
            {"record": "graph", "graph_epoch": "1", "passes": []},
            *samples,
        ]
        if complete is not None:
            rows.append({
                "record": "footer",
                "complete": complete,
                "frames": str(len(samples)),
                "expected_frames": str(len(samples)),
            })
        self.path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    def test_exact_nearest_rank_and_slowest_one_percent(self):
        self.write([frame(index) for index in range(101)])
        result = telemetry.analyze(self.path, series_path=self.root / "series.csv")
        stats = result["timings"]["cpu"]
        self.assertEqual(stats["p95_msec"], 96)
        self.assertEqual(stats["p99_msec"], 100)
        self.assertEqual(stats["slowest_one_percent_samples"], 2)
        self.assertEqual(stats["slowest_one_percent_mean_msec"], 100.5)
        self.assertAlmostEqual(stats["one_percent_low_fps"], 1000 / 100.5)
        self.assertEqual(result["passes"]["1:7"], stats)
        self.assertAlmostEqual(result["average_fps"], 100)
        self.assertEqual(result["resources"]["private_bytes"]["delta"], 100)
        self.assertEqual(len((self.root / "series.csv").read_text().splitlines()), 102)

    def test_retired_records_are_sorted_by_frame_and_ranges_are_explicit(self):
        samples = [frame(index) for index in [2, 0, 1]]
        for record, sample in enumerate(samples):
            sample["record_id"] = str(record)
        self.write(samples)
        result = telemetry.analyze(self.path, first_frame=1)
        self.assertEqual(result["selected_frames"], 2)
        self.assertEqual(result["timings"]["present_interval"]["mean_msec"], 10)
        self.assertEqual(result["timings"]["cpu"]["mean_msec"], 2.5)

    def test_missing_footer_and_truncated_line_are_not_complete(self):
        self.write([frame(0)], complete=None)
        with self.assertRaises(ValueError):
            telemetry.analyze(self.path)
        self.assertFalse(telemetry.analyze(self.path, allow_partial=True)["complete"])
        self.path.write_bytes(self.path.read_bytes()[:-1])
        with self.assertRaisesRegex(ValueError, "truncated"):
            telemetry.analyze(self.path, allow_partial=True)

    def test_duplicate_and_missing_ids_do_not_pass_as_full_run(self):
        samples = [frame(0), frame(0)]
        samples[1]["record_id"] = "1"
        self.write(samples)
        with self.assertRaises(sqlite3.IntegrityError):
            telemetry.analyze(self.path)
        samples = [frame(0), frame(2)]
        samples[1]["record_id"] = "1"
        self.write(samples)
        with self.assertRaises(ValueError):
            telemetry.analyze(self.path)

    def test_input_api_latency_counts_new_revision_once(self):
        samples = [frame(0), frame(1)]
        samples[0].update(
            new_input=True,
            input_revision="2",
            input_receipts_since_previous_frame="2",
            input_received_qpc="1001",
            input_observed_qpc="1002",
        )
        self.write(samples)
        result = telemetry.analyze(self.path)
        metric = result["timings"]["input_receipt_to_present_api"]
        self.assertEqual(metric["samples"], 1)
        self.assertEqual(metric["mean_msec"], 9)
        samples[0]["input_observed_qpc"] = "999"
        self.write(samples)
        with self.assertRaises(ValueError):
            telemetry.analyze(self.path)

    def test_pass_ids_from_distinct_graph_epochs_are_not_combined(self):
        samples = [frame(0), frame(1)]
        samples[1]["graph_epoch"] = "2"
        self.write(samples)
        lines = self.path.read_text().splitlines()
        lines.insert(3, json.dumps({"record": "graph", "graph_epoch": "2", "passes": []}))
        self.path.write_text("\n".join(lines) + "\n")
        result = telemetry.analyze(self.path)
        self.assertEqual(result["passes"]["1:7"]["mean_msec"], 1)
        self.assertEqual(result["passes"]["2:7"]["mean_msec"], 2)

    def test_summary_budget_and_renderer_pass_bound(self):
        sample = frame(0)
        sample["passes"] = [{"pass_id": index, "gpu_msec": 1} for index in range(300)]
        self.write([sample])
        with self.assertRaisesRegex(ValueError, "budget exceeded"):
            telemetry.analyze(self.path, max_pass_groups=10)
        self.assertEqual(len(telemetry.analyze(self.path)["passes"]), 300)
        sample["passes"] = [{"pass_id": index, "gpu_msec": 1} for index in range(1025)]
        self.write([sample])
        with self.assertRaises(ValueError):
            telemetry.analyze(self.path)

    def test_nonfinite_and_unknown_graph_are_rejected(self):
        sample = frame(0)
        sample["graphics_msec"] = float("nan")
        self.write([sample])
        with self.assertRaises(ValueError):
            telemetry.analyze(self.path)
        sample = frame(0)
        sample["graph_epoch"] = "2"
        self.write([sample])
        with self.assertRaises(ValueError):
            telemetry.analyze(self.path)


if __name__ == "__main__":
    unittest.main()
