"""Run the complete two-client protocol for at least 10000 real 16 ms ticks."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from RunM2Handshake import run_handshake


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", type=Path, required=True)
    parser.add_argument("--client", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)
    report_path = args.report.resolve()
    try:
        result = run_handshake(
            args.server.resolve(),
            args.client.resolve(),
            report_path,
            duration_ms=175000,
            drain_after_ms=165000,
        )
        bounds = result["server_bounds"][0]
        if bounds["ticks"] < 10000 or result["elapsed_seconds"] < 150:
            raise RuntimeError("Stability run did not cover 10000 real 16 ms ticks: " + json.dumps(result))
        result["soak"] = {
            "ticks": bounds["ticks"],
            "fixed_step_msec": 16,
            "elapsed_seconds": result["elapsed_seconds"],
            "input_high_water": bounds["input_high_water"],
            "server_enet_outgoing_high_water": bounds["enet_outgoing_high_water"],
            "server_poll_event_high_water": bounds["poll_event_high_water"],
        }
        report_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(
            f"ENGINE_NEXT_SOAK ticks={bounds['ticks']} elapsed_seconds={result['elapsed_seconds']} "
            f"input_high_water={bounds['input_high_water']} status=ok"
        )
        return 0
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print(json.dumps({"passed": False, "error": str(error)}, indent=2))
        return 1


if __name__ == "__main__":
    sys.exit(main())
